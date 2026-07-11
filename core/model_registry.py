"""
Central model registry for M.I.C.A.

The registry keeps model metadata and profile aliases in one place while
remaining compatible with the older ``models.text`` / ``models.vision`` config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from config.config_loader import get_config


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model_id: str
    provider: str = "gemini"
    capabilities: tuple[str, ...] = ("text",)
    context_window: int = 1_000_000
    cost_tier: str = "medium"
    latency_tier: str = "medium"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


def _as_tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple, set)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return default


class ModelRegistry:
    """Loads model profiles and routing aliases from config/env."""

    def __init__(self, config: Any | None = None):
        self._use_environment_overrides = config is None
        self.config = config or get_config()
        self.models: dict[str, ModelProfile] = {}
        self.aliases: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        legacy_text = self.config.get("models.text", "gemini-2.5-flash")
        legacy_vision = self.config.get("models.vision", legacy_text)
        legacy_context = int(self.config.get("models.context_window", 1_000_000) or 1_000_000)
        local_model = self.config.get("ollama.model", "llama3.1")

        defaults = {
            "fast": ModelProfile(
                name="fast",
                model_id=legacy_text,
                provider="gemini",
                capabilities=("text", "tools"),
                context_window=legacy_context,
                cost_tier="low",
                latency_tier="low",
            ),
            "reasoning": ModelProfile(
                name="reasoning",
                model_id=legacy_text,
                provider="gemini",
                capabilities=("text", "code", "reasoning", "tools"),
                context_window=legacy_context,
                cost_tier="medium",
                latency_tier="medium",
            ),
            "vision": ModelProfile(
                name="vision",
                model_id=legacy_vision,
                provider="gemini",
                capabilities=("text", "vision", "code"),
                context_window=legacy_context,
                cost_tier="medium",
                latency_tier="medium",
            ),
            "long_context": ModelProfile(
                name="long_context",
                model_id=legacy_text,
                provider="gemini",
                capabilities=("text", "summary", "code", "long_context"),
                context_window=legacy_context,
                cost_tier="medium",
                latency_tier="high",
            ),
            "local": ModelProfile(
                name="local",
                model_id=local_model,
                provider="ollama",
                capabilities=("text", "code", "summary"),
                context_window=int(self.config.get("model_router.local_context_window", 8192) or 8192),
                cost_tier="free",
                latency_tier="medium",
                enabled=bool(self.config.get("ollama.enabled", False)),
            ),
        }

        configured = self.config.get("model_router.models", {}) or {}
        self.models = defaults | self._load_configured_models(configured, defaults)

        self.aliases = {
            "fast": "fast",
            "routine": "fast",
            "reasoning": "reasoning",
            "code": "reasoning",
            "vision": "vision",
            "long_context": "long_context",
            "local": "local",
        }
        configured_aliases = self.config.get("model_router.aliases", {}) or {}
        self.aliases.update({str(k): str(v) for k, v in configured_aliases.items()})
        if self._use_environment_overrides:
            self._apply_env_overrides()

    def _load_configured_models(
        self, configured: dict[str, Any], defaults: dict[str, ModelProfile]
    ) -> dict[str, ModelProfile]:
        loaded = {}
        for name, raw in configured.items():
            if not isinstance(raw, dict):
                continue
            base = defaults.get(name)
            capabilities = _as_tuple(
                raw.get("capabilities"),
                base.capabilities if base else ("text",),
            )
            loaded[name] = ModelProfile(
                name=str(name),
                model_id=str(raw.get("model_id") or raw.get("model") or (base.model_id if base else "")),
                provider=str(raw.get("provider") or (base.provider if base else "gemini")),
                capabilities=capabilities,
                context_window=int(
                    raw.get("context_window")
                    or (base.context_window if base else self.config.get("models.context_window", 8192))
                ),
                cost_tier=str(raw.get("cost_tier") or (base.cost_tier if base else "medium")),
                latency_tier=str(raw.get("latency_tier") or (base.latency_tier if base else "medium")),
                enabled=bool(raw.get("enabled", base.enabled if base else True)),
                metadata={k: v for k, v in raw.items() if k not in {
                    "model_id",
                    "model",
                    "provider",
                    "capabilities",
                    "context_window",
                    "cost_tier",
                    "latency_tier",
                    "enabled",
                }},
            )
        return loaded

    def _apply_env_overrides(self) -> None:
        env_map = {
            "MODEL_ROUTER_FAST_MODEL": "fast",
            "MODEL_ROUTER_REASONING_MODEL": "reasoning",
            "MODEL_ROUTER_VISION_MODEL": "vision",
            "MODEL_ROUTER_LONG_CONTEXT_MODEL": "long_context",
            "MODEL_ROUTER_LOCAL_MODEL": "local",
        }
        for env_name, profile_name in env_map.items():
            value = os.getenv(env_name)
            if value and profile_name in self.models:
                old = self.models[profile_name]
                self.models[profile_name] = ModelProfile(
                    **{**old.__dict__, "model_id": value}
                )

    def get(self, name_or_alias: str) -> ModelProfile:
        key = self.aliases.get(name_or_alias, name_or_alias)
        model = self.models.get(key)
        if not model:
            raise KeyError(f"Unknown model profile: {name_or_alias}")
        return model

    def available(self, capability: str | None = None) -> list[ModelProfile]:
        models = [model for model in self.models.values() if model.enabled]
        if capability:
            models = [model for model in models if model.supports(capability)]
        return models


_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
