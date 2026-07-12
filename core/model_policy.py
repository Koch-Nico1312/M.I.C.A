"""Routing policy for model selection, escalation, and fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SECRET = "secret"


@dataclass(frozen=True)
class ModelDecision:
    intent: str
    profile: str
    model: ModelProfile
    reason: str
    fallback_profiles: tuple[str, ...]
    sensitivity: str = Sensitivity.INTERNAL.value
    cloud_allowed: bool = True
    use_cache: bool = True


class ModelPolicy:
    def __init__(self, registry: ModelRegistry | None = None, config: Any | None = None):
        self.registry = registry or get_model_registry()
        self.config = config or self.registry.config
        self._use_global_privacy_mode = config is None and registry is None

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

    def detect_sensitivity(self, text: str = "", *, explicit: str = "") -> Sensitivity:
        """Classify how conservatively a prompt should be routed."""
        explicit = explicit.lower().strip()
        if explicit in {item.value for item in Sensitivity}:
            return Sensitivity(explicit)

        raw = text.lower()
        secret_markers = (
            "api key",
            "token",
            "password",
            "secret",
            "private key",
            "ssh key",
            "credit card",
            "bank account",
            "social security",
        )
        private_markers = (
            "personal",
            "medical",
            "health",
            "address",
            "email",
            "phone",
            "contacts",
            "calendar",
            "diary",
            "journal",
            "memory",
        )
        internal_markers = ("project", "code", "repo", "workspace", "document", "file")
        if any(marker in raw for marker in secret_markers):
            return Sensitivity.SECRET
        if any(marker in raw for marker in private_markers):
            return Sensitivity.PRIVATE
        if any(marker in raw for marker in internal_markers):
            return Sensitivity.INTERNAL
        return Sensitivity.PUBLIC

    def choose(
        self,
        intent: str | None = None,
        *,
        text: str = "",
        action: str = "",
        has_image: bool = False,
        risk: str = "",
        sensitivity: str = "",
        context_chars: int = 0,
    ) -> ModelDecision:
        resolved_sensitivity = self.detect_sensitivity(text, explicit=sensitivity)
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
        profile = self._maybe_apply_preferred_profile(profile, resolved_intent)
        profile, sensitivity_reason = self._maybe_adjust_for_sensitivity(
            profile,
            resolved_sensitivity,
            resolved_intent,
        )
        profile, privacy_reason = self._maybe_adjust_for_privacy(profile, resolved_sensitivity)
        if sensitivity_reason:
            reason = f"{reason}; {sensitivity_reason}"
        if privacy_reason:
            reason = f"{reason}; {privacy_reason}"
        fallbacks = self.fallback_chain(profile)
        cloud_allowed = self._cloud_allowed(resolved_sensitivity)
        return ModelDecision(
            intent=resolved_intent,
            profile=profile,
            model=self.registry.get(profile),
            reason=reason,
            fallback_profiles=fallbacks,
            sensitivity=resolved_sensitivity.value,
            cloud_allowed=cloud_allowed,
            use_cache=resolved_intent not in {"code_edit", "high_risk_action", "vision"},
        )

    def explain_route(self, text: str, **kwargs: Any) -> dict[str, Any]:
        """Return a JSON-safe routing explanation without making a model call."""
        decision = self.choose(text=text, **kwargs)
        return {
            "intent": decision.intent,
            "sensitivity": decision.sensitivity,
            "profile": decision.profile,
            "model_id": decision.model.model_id,
            "provider": decision.model.provider,
            "cloud_allowed": decision.cloud_allowed,
            "fallback_profiles": list(decision.fallback_profiles),
            "use_cache": decision.use_cache,
            "reason": decision.reason,
        }

    def _maybe_adjust_for_sensitivity(
        self,
        profile: str,
        sensitivity: Sensitivity,
        intent: str,
    ) -> tuple[str, str]:
        local_profiles = ("local_code", "local_review", "local")
        if sensitivity == Sensitivity.SECRET:
            for candidate in local_profiles:
                try:
                    model = self.registry.get(candidate)
                except KeyError:
                    continue
                if model.enabled and model.supports("text"):
                    return candidate, "secret content is routed to a local profile"
            return profile, "secret content detected but no enabled local profile is available"
        if sensitivity == Sensitivity.PRIVATE and intent in {"summary", "chat", "tool_planning"}:
            for candidate in ("local_review", "local"):
                try:
                    model = self.registry.get(candidate)
                except KeyError:
                    continue
                if model.enabled and model.supports("text"):
                    return candidate, "private content prefers local processing"
        return profile, ""

    def _maybe_adjust_for_privacy(
        self, profile: str, sensitivity: Sensitivity
    ) -> tuple[str, str]:
        if not self._use_global_privacy_mode:
            return profile, ""
        try:
            from core.privacy_modes import get_privacy_mode_manager

            privacy = get_privacy_mode_manager()
            if privacy.allows_external_model(sensitivity.value):
                return profile, ""
            model = self.registry.get(profile)
            if model.provider != "ollama":
                for candidate in ("local_code", "local_review", "local"):
                    try:
                        local_model = self.registry.get(candidate)
                    except KeyError:
                        continue
                    if local_model.enabled:
                        return candidate, f"privacy mode {privacy.effective_mode()} requires local routing"
                return profile, f"privacy mode {privacy.effective_mode()} blocks external models but no local model is enabled"
        except Exception:
            return profile, ""
        return profile, ""

    def _cloud_allowed(self, sensitivity: Sensitivity) -> bool:
        if sensitivity == Sensitivity.SECRET:
            return False
        if not self._use_global_privacy_mode:
            return True
        try:
            from core.privacy_modes import get_privacy_mode_manager

            return get_privacy_mode_manager().allows_external_model(sensitivity.value)
        except Exception:
            return True

    def _maybe_adjust_for_budget(self, profile: str, context_chars: int) -> str:
        threshold = int(self.config.get("model_router.long_context_chars", 40_000) or 40_000)
        if context_chars > threshold and profile != "vision":
            return "long_context"
        mode = str(self.config.get("model_router.cost_mode", "balanced")).lower()
        if mode == "economy" and profile in {"reasoning", "long_context"}:
            return "fast"
        return profile

    def _maybe_apply_preferred_profile(self, profile: str, intent: str) -> str:
        if intent in {"vision", "high_risk_action"}:
            return profile
        preferred = str(self.config.get("model_router.preferred_profile", "") or "").strip()
        if not preferred:
            return profile
        try:
            candidate = self.registry.get(preferred)
        except KeyError:
            return profile
        if not candidate.enabled or not candidate.supports("text"):
            return profile
        return candidate.name

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
