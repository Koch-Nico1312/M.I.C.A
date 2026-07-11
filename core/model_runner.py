"""Unified execution path for routed model calls."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from core.api_cache import get_api_cache
from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.model_policy import ModelDecision, ModelPolicy, get_model_policy
from core.model_registry import ModelProfile

logger = get_logger(__name__)

ProviderCallable = Callable[[ModelProfile, "ModelCall"], str]


@dataclass(frozen=True)
class ModelCall:
    prompt: str = ""
    contents: Any = None
    system_instruction: str = ""
    intent: str | None = None
    action: str = ""
    has_image: bool = False
    risk: str = ""
    sensitivity: str = ""
    context_chars: int = 0
    tools: Any = None
    generation_config: dict[str, Any] = field(default_factory=dict)
    use_cache: bool | None = None


@dataclass(frozen=True)
class ModelRunResult:
    text: str
    model_name: str
    model_id: str
    provider: str
    intent: str
    reason: str
    duration_ms: float
    fallback_attempts: tuple[str, ...] = ()
    cache_hit: bool = False


class RoutedResponse:
    """Small compatibility object matching SDK responses used by actions."""

    def __init__(self, result: ModelRunResult):
        self.result = result
        self.text = result.text


class RoutedModel:
    """Compatibility adapter with ``generate_content``."""

    def __init__(
        self,
        runner: "ModelRunner",
        *,
        intent: str | None = None,
        system_instruction: str = "",
        action: str = "",
        risk: str = "",
        use_cache: bool | None = None,
    ):
        self.runner = runner
        self.intent = intent
        self.system_instruction = system_instruction
        self.action = action
        self.risk = risk
        self.use_cache = use_cache

    def generate_content(self, contents: Any, **kwargs: Any) -> RoutedResponse:
        has_image = _contains_non_text_part(contents)
        prompt = _contents_to_prompt(contents)
        result = self.runner.generate(
            ModelCall(
                prompt=prompt,
                contents=contents,
                system_instruction=self.system_instruction,
                intent=self.intent,
                action=self.action,
                has_image=has_image,
                risk=self.risk,
                sensitivity="",
                context_chars=len(prompt),
                generation_config=kwargs,
                use_cache=self.use_cache,
            )
        )
        return RoutedResponse(result)


class CodeVerificationLoop:
    """API hook for plan -> patch -> test -> analyze -> fix workflows."""

    def __init__(self, runner: "ModelRunner" | None = None):
        self.runner = runner or get_model_runner()

    def plan(self, goal: str, context: str = "") -> str:
        return self.runner.generate_text(
            f"Plan a safe code change for this goal:\n{goal}\n\nContext:\n{context}",
            intent="tool_planning",
            use_cache=False,
        )

    def patch(self, goal: str, context: str = "") -> str:
        return self.runner.generate_text(
            f"Create a minimal patch for this goal:\n{goal}\n\nContext:\n{context}",
            intent="code_edit",
            use_cache=False,
        )

    def analyze_failure(self, command: str, output: str, context: str = "") -> str:
        return self.runner.generate_text(
            f"Test command failed: {command}\n\nOutput:\n{output}\n\nContext:\n{context}",
            intent="test_failure_analysis",
            use_cache=False,
        )

    def review(self, diff: str, context: str = "") -> str:
        return self.runner.generate_text(
            f"Review this code change for regressions and missing tests:\n{diff}\n\n{context}",
            intent="code_edit",
            use_cache=False,
        )


class ModelRunner:
    def __init__(
        self,
        policy: ModelPolicy | None = None,
        provider_clients: dict[str, ProviderCallable] | None = None,
        cache: Any | None = None,
    ):
        self.policy = policy or get_model_policy()
        self.provider_clients = provider_clients or {}
        self.cache = cache
        self.telemetry: list[dict[str, Any]] = []

    def routed_model(
        self,
        *,
        intent: str | None = None,
        system_instruction: str = "",
        action: str = "",
        risk: str = "",
        use_cache: bool | None = None,
    ) -> RoutedModel:
        return RoutedModel(
            self,
            intent=intent,
            system_instruction=system_instruction,
            action=action,
            risk=risk,
            use_cache=use_cache,
        )

    def generate_text(
        self,
        prompt: str,
        *,
        intent: str | None = None,
        system_instruction: str = "",
        action: str = "",
        has_image: bool = False,
        risk: str = "",
        sensitivity: str = "",
        context_chars: int | None = None,
        tools: Any = None,
        use_cache: bool | None = None,
    ) -> str:
        return self.generate(
            ModelCall(
                prompt=prompt,
                contents=prompt,
                system_instruction=system_instruction,
                intent=intent,
                action=action,
                has_image=has_image,
                risk=risk,
                sensitivity=sensitivity,
                context_chars=context_chars if context_chars is not None else len(prompt),
                tools=tools,
                use_cache=use_cache,
            )
        ).text

    def generate(self, call: ModelCall) -> ModelRunResult:
        decision = self.policy.choose(
            call.intent,
            text=call.prompt,
            action=call.action,
            has_image=call.has_image,
            risk=call.risk,
            sensitivity=call.sensitivity,
            context_chars=call.context_chars or len(call.prompt),
        )
        call = self._route_call_tools(call)
        cache_allowed = decision.use_cache if call.use_cache is None else call.use_cache
        cache_key_prompt = call.prompt or _contents_to_prompt(call.contents)
        if cache_allowed and _is_cacheable(call.contents, call.tools):
            cached = self._cache_get(cache_key_prompt, decision.model.model_id, decision.intent)
            if cached:
                result = ModelRunResult(
                    text=str(cached.get("text", "")),
                    model_name=decision.model.name,
                    model_id=decision.model.model_id,
                    provider=decision.model.provider,
                    intent=decision.intent,
                    reason=decision.reason,
                    duration_ms=0.0,
                    cache_hit=True,
                )
                self._record_governor(result, call)
                return result

        result = self._attempt_chain(decision, call)
        if cache_allowed and _is_cacheable(call.contents, call.tools):
            self._cache_set(cache_key_prompt, result)
        self._record_governor(result, call)
        return result

    def _route_call_tools(self, call: ModelCall) -> ModelCall:
        tools = call.tools
        if not isinstance(tools, list) or len(tools) != 1 or not isinstance(tools[0], dict):
            return call
        declarations = tools[0].get("function_declarations")
        if not isinstance(declarations, list):
            return call
        from core.tool_router import get_tool_router

        selected = get_tool_router().select(call.prompt, declarations)
        return replace(call, tools=[{"function_declarations": selected}])

    @staticmethod
    def _record_governor(result: ModelRunResult, call: ModelCall) -> None:
        try:
            from core.ai_governor import get_ai_governor

            get_ai_governor().record(
                provider=result.provider,
                model_id=result.model_id,
                intent=result.intent,
                duration_ms=result.duration_ms,
                input_chars=len(call.prompt or _contents_to_prompt(call.contents)),
                output_chars=len(result.text),
                cache_hit=result.cache_hit,
            )
        except Exception as exc:
            logger.debug("AI governor accounting skipped: %s", exc)

    def _attempt_chain(self, decision: ModelDecision, call: ModelCall) -> ModelRunResult:
        chain = (decision.profile,) + tuple(decision.fallback_profiles)
        errors: list[str] = []
        fallback_attempts: list[str] = []

        for index, profile_name in enumerate(chain):
            model = self.policy.registry.get(profile_name)
            if not model.enabled:
                continue
            if index > 0:
                fallback_attempts.append(profile_name)
            started = time.perf_counter()
            metrics = get_metrics_collector()
            metrics.start_operation("model_call")
            try:
                text = self._call_provider(model, call)
                duration_ms = (time.perf_counter() - started) * 1000
                result = ModelRunResult(
                    text=text,
                    model_name=model.name,
                    model_id=model.model_id,
                    provider=model.provider,
                    intent=decision.intent,
                    reason=decision.reason,
                    duration_ms=duration_ms,
                    fallback_attempts=tuple(fallback_attempts),
                )
                self._record(result, success=True)
                metrics.end_operation(
                    "model_call",
                    {
                        "success": True,
                        "model": model.model_id,
                        "profile": model.name,
                        "intent": decision.intent,
                        "fallbacks": list(fallback_attempts),
                    },
                )
                return result
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000
                errors.append(f"{model.name}/{model.model_id}: {exc}")
                logger.warning(
                    "Model call failed profile=%s model=%s intent=%s error=%s",
                    model.name,
                    model.model_id,
                    decision.intent,
                    exc,
                )
                self._record_error(decision, model, exc, duration_ms)
                metrics.end_operation(
                    "model_call",
                    {
                        "success": False,
                        "model": model.model_id,
                        "profile": model.name,
                        "intent": decision.intent,
                        "error": str(exc),
                    },
                )
                if not self.policy.should_retry_with_fallback(exc):
                    break

        raise RuntimeError("Model routing failed: " + " | ".join(errors))

    def _call_provider(self, model: ModelProfile, call: ModelCall) -> str:
        provider = self.provider_clients.get(model.provider)
        if provider:
            return provider(model, call)
        if model.provider == "gemini":
            return _call_gemini(model, call)
        if model.provider == "ollama":
            return _call_ollama(model, call)
        raise RuntimeError(f"Unsupported provider: {model.provider}")

    def _cache_get(self, prompt: str, model_id: str, intent: str) -> dict[str, Any] | None:
        cache = self.cache or get_api_cache()
        try:
            return cache.get(prompt, model=model_id, intent=intent)
        except Exception as exc:
            logger.debug("Model cache get skipped: %s", exc)
            return None

    def _cache_set(self, prompt: str, result: ModelRunResult) -> None:
        cache = self.cache or get_api_cache()
        try:
            cache.set(
                prompt,
                {"text": result.text, "provider": result.provider, "profile": result.model_name},
                model=result.model_id,
                intent=result.intent,
            )
        except Exception as exc:
            logger.debug("Model cache set skipped: %s", exc)

    def _record(self, result: ModelRunResult, *, success: bool) -> None:
        entry = {
            "success": success,
            "intent": result.intent,
            "profile": result.model_name,
            "model": result.model_id,
            "provider": result.provider,
            "duration_ms": result.duration_ms,
            "fallbacks": list(result.fallback_attempts),
            "reason": result.reason,
            "cache_hit": result.cache_hit,
        }
        self.telemetry.append(entry)
        logger.info(
            "Model route intent=%s profile=%s model=%s provider=%s duration=%.1fms fallbacks=%s",
            result.intent,
            result.model_name,
            result.model_id,
            result.provider,
            result.duration_ms,
            list(result.fallback_attempts),
        )

    def _record_error(
        self,
        decision: ModelDecision,
        model: ModelProfile,
        error: Exception,
        duration_ms: float,
    ) -> None:
        self.telemetry.append(
            {
                "success": False,
                "intent": decision.intent,
                "profile": model.name,
                "model": model.model_id,
                "provider": model.provider,
                "duration_ms": duration_ms,
                "error": str(error),
            }
        )


_gemini_clients: dict[str, Any] = {}
_gemini_models: dict[tuple[str, str], Any] = {}
_gemini_client_lock = threading.Lock()


def _call_gemini(model: ModelProfile, call: ModelCall) -> str:
    contents = call.contents if call.contents is not None else call.prompt
    if call.tools or call.has_image:
        from google import genai

        api_key = _api_key("gemini")
        key_id = str(hash(api_key))
        with _gemini_client_lock:
            client = _gemini_clients.get(key_id)
            if client is None:
                client = genai.Client(api_key=api_key)
                _gemini_clients[key_id] = client
        config: dict[str, Any] = {}
        if call.tools:
            config["tools"] = [call.tools] if isinstance(call.tools, dict) else call.tools
        if call.system_instruction:
            config["system_instruction"] = call.system_instruction
        response = client.models.generate_content(
            model=model.model_id,
            contents=contents,
            config=config or None,
        )
        return _extract_text(response)

    import google.generativeai as genai

    api_key = _api_key("gemini")
    genai.configure(api_key=api_key)
    kwargs = {}
    if call.system_instruction:
        kwargs["system_instruction"] = call.system_instruction
    cache_key = (model.model_id, call.system_instruction)
    with _gemini_client_lock:
        gemini_model = _gemini_models.get(cache_key)
        if gemini_model is None:
            gemini_model = genai.GenerativeModel(model.model_id, **kwargs)
            _gemini_models[cache_key] = gemini_model
    response = gemini_model.generate_content(contents)
    return _extract_text(response)


def _call_ollama(model: ModelProfile, call: ModelCall) -> str:
    from core.llm_fallback import get_ollama_fallback

    prompt = call.prompt or _contents_to_prompt(call.contents)
    ollama = get_ollama_fallback()
    if hasattr(ollama, "model"):
        ollama.model = model.model_id
    return ollama.generate_text(prompt, call.system_instruction)


def _api_key(service: str) -> str:
    from config.config_loader import get_config

    key = str(get_config().get_api_key(service) or "").strip()
    if not key:
        raise RuntimeError(f"Missing API key for provider: {service}")
    return key


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()
    candidates = getattr(response, "candidates", None) or []
    chunks: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(str(part_text))
    if chunks:
        return "".join(chunks).strip()
    return str(response).strip()


def _contents_to_prompt(contents: Any) -> str:
    if contents is None:
        return ""
    if isinstance(contents, str):
        return contents
    if isinstance(contents, (list, tuple)):
        return "\n".join(_contents_to_prompt(item) for item in contents if isinstance(item, str))
    if isinstance(contents, dict):
        return str(contents.get("text") or contents.get("mime_type") or "")
    return "" if _contains_non_text_part(contents) else str(contents)


def _contains_non_text_part(contents: Any) -> bool:
    if contents is None or isinstance(contents, str):
        return False
    if isinstance(contents, (list, tuple)):
        return any(_contains_non_text_part(item) for item in contents)
    if isinstance(contents, dict):
        return "data" in contents or "mime_type" in contents
    return True


def _is_cacheable(contents: Any, tools: Any = None) -> bool:
    return tools is None and not _contains_non_text_part(contents)


_runner: ModelRunner | None = None


def get_model_runner() -> ModelRunner:
    global _runner
    if _runner is None:
        _runner = ModelRunner()
    return _runner


def get_routed_model(**kwargs: Any) -> RoutedModel:
    return get_model_runner().routed_model(**kwargs)
