"""Local cost, latency and privacy accounting for routed model calls."""

from __future__ import annotations

import threading
from collections import deque
from datetime import date, datetime
from typing import Any

from config.config_loader import get_config


class AIGovernor:
    def __init__(self):
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=1000)

    def record(
        self,
        *,
        provider: str,
        model_id: str,
        intent: str,
        duration_ms: float,
        input_chars: int,
        output_chars: int,
        cache_hit: bool = False,
    ) -> None:
        input_tokens = max(1, int(input_chars / 4)) if input_chars else 0
        output_tokens = max(1, int(output_chars / 4)) if output_chars else 0
        cost = self._estimate_cost(provider, input_tokens, output_tokens)
        event = {
            "timestamp": datetime.now().isoformat(),
            "day": date.today().isoformat(),
            "provider": provider,
            "model_id": model_id,
            "intent": intent,
            "duration_ms": round(float(duration_ms), 2),
            "input_tokens_estimate": input_tokens,
            "output_tokens_estimate": output_tokens,
            "cost_usd_estimate": round(cost, 6),
            "cache_hit": bool(cache_hit),
        }
        with self._lock:
            self._events.append(event)

    def snapshot(self) -> dict[str, Any]:
        config = get_config()
        today = date.today().isoformat()
        with self._lock:
            events = list(self._events)
        daily = [item for item in events if item["day"] == today]
        cost = sum(float(item["cost_usd_estimate"]) for item in daily)
        token_count = sum(
            int(item["input_tokens_estimate"]) + int(item["output_tokens_estimate"])
            for item in daily
        )
        budget = float(config.get("ai_governor.daily_budget_usd", 2.0) or 2.0)
        return {
            "daily_budget_usd": budget,
            "daily_cost_usd_estimate": round(cost, 4),
            "daily_tokens_estimate": token_count,
            "budget_used_percent": round((cost / budget * 100) if budget > 0 else 0.0, 1),
            "budget_exceeded": bool(budget > 0 and cost >= budget),
            "local_first": bool(config.get("personal_mode.local_first", True)),
            "recent_calls": list(reversed(events[-20:])),
        }

    @staticmethod
    def _estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
        if provider.lower() in {"ollama", "local"}:
            return 0.0
        config = get_config()
        input_rate = float(config.get("ai_governor.input_usd_per_million", 0.3) or 0.3)
        output_rate = float(config.get("ai_governor.output_usd_per_million", 2.5) or 2.5)
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


_governor: AIGovernor | None = None
_governor_lock = threading.Lock()


def get_ai_governor() -> AIGovernor:
    global _governor
    if _governor is None:
        with _governor_lock:
            if _governor is None:
                _governor = AIGovernor()
    return _governor
