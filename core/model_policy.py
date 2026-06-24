"""Routing policy for model selection, escalation, and fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.model_registry import ModelProfile, ModelRegistry, get_model_registry


INTENTS = {
    "chat",
    "code_edit",
    "test_run",
    "test_failure_analysis",
    "vision",
    "summary",
    "tool_planning",
    "high_risk_action",
}


@dataclass(frozen=True)
class ModelDecision:
    intent: str
    profile: str
    model: ModelProfile
    reason: str
    fallback_profiles: tuple[str, ...]
    use_cache: bool = True


class ModelPolicy:
    def __init__(self, registry: ModelRegistry | None = None, config: Any | None = None):
        self.registry = registry or get_model_registry()
        self.config = config or self.registry.config

    def detect_intent(
        self,
        text: str = "",
        *,
        action: str = "",
        has_image: bool = False,
        risk: str = "",
        context_chars: int = 0,
    ) -> str:
        raw = f"{action} {text}".lower()
        if risk.lower() == "high" or any(
            token in raw
            for token in ("delete", "remove files", "format disk", "registry", "admin", "sudo")
        ):
            return "high_risk_action"
        if has_image or any(
            token in raw
            for token in ("screenshot", "screen", "image", "ocr", "vision", "ui element")
        ):
            return "vision"
        if any(token in raw for token in ("test failed", "traceback", "pytest", "failure", "stacktrace")):
            return "test_failure_analysis"
        if any(token in raw for token in ("run tests", "test run", "execute tests")):
            return "test_run"
        if context_chars > int(self.config.get("model_router.long_context_chars", 40_000) or 40_000):
            return "summary"
        if any(token in raw for token in ("summarize", "summary", "analyze document", "tl;dr")):
            return "summary"
        if any(
            token in raw
            for token in (
                "edit",
                "patch",
                "fix code",
                "fix any bugs",
                "refactor",
                "review",
                "optimize",
                "document",
                "write code",
                "unit tests",
                "debug",
            )
        ):
            return "code_edit"
        if any(token in raw for token in ("plan", "tools", "workflow", "steps", "execute task")):
            return "tool_planning"
        return "chat"

    def choose(
        self,
        intent: str | None = None,
        *,
        text: str = "",
        action: str = "",
        has_image: bool = False,
        risk: str = "",
        context_chars: int = 0,
    ) -> ModelDecision:
        resolved_intent = intent or self.detect_intent(
            text,
            action=action,
            has_image=has_image,
            risk=risk,
            context_chars=context_chars,
        )
        matrix = {
            "chat": ("fast", "routine response"),
            "code_edit": ("reasoning", "code generation or patching needs stronger reasoning"),
            "test_run": ("fast", "test execution planning is routine unless failures appear"),
            "test_failure_analysis": (
                "reasoning",
                "test failures need debugging and causal analysis",
            ),
            "vision": ("vision", "request contains image or screen context"),
            "summary": ("long_context", "summary or long input benefits from context budget"),
            "tool_planning": ("reasoning", "tool sequencing benefits from planning"),
            "high_risk_action": ("reasoning", "high-risk actions require conservative reasoning"),
        }
        profile, reason = matrix.get(resolved_intent, ("fast", "default fast route"))
        profile = self._maybe_adjust_for_budget(profile, context_chars)
        fallbacks = self.fallback_chain(profile)
        return ModelDecision(
            intent=resolved_intent,
            profile=profile,
            model=self.registry.get(profile),
            reason=reason,
            fallback_profiles=fallbacks,
            use_cache=resolved_intent not in {"code_edit", "high_risk_action", "vision"},
        )

    def _maybe_adjust_for_budget(self, profile: str, context_chars: int) -> str:
        threshold = int(self.config.get("model_router.long_context_chars", 40_000) or 40_000)
        if context_chars > threshold and profile != "vision":
            return "long_context"
        mode = str(self.config.get("model_router.cost_mode", "balanced")).lower()
        if mode == "economy" and profile in {"reasoning", "long_context"}:
            return "fast"
        return profile

    def fallback_chain(self, profile: str) -> tuple[str, ...]:
        configured = self.config.get(f"model_router.fallbacks.{profile}", None)
        if isinstance(configured, list):
            return tuple(str(item) for item in configured)
        defaults = {
            "fast": ("reasoning", "local"),
            "reasoning": ("fast", "local"),
            "vision": ("reasoning", "fast", "local"),
            "long_context": ("reasoning", "fast", "local"),
            "local": (),
        }
        return defaults.get(profile, ("fast", "local"))

    def should_retry_with_fallback(self, error: Exception) -> bool:
        raw = str(error).lower()
        return any(
            marker in raw
            for marker in (
                "429",
                "rate limit",
                "quota",
                "resource_exhausted",
                "timeout",
                "timed out",
                "connection",
                "network",
                "unavailable",
                "api key",
                "permission denied",
            )
        )


_policy: ModelPolicy | None = None


def get_model_policy() -> ModelPolicy:
    global _policy
    if _policy is None:
        _policy = ModelPolicy()
    return _policy
