from __future__ import annotations

from core.model_policy import ModelPolicy
from core.model_registry import ModelRegistry
from core.model_runner import CodeVerificationLoop, ModelCall, ModelRunner


class FakeConfig:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        value = self.data
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def get_api_key(self, service="gemini"):
        return f"{service}-key"


class NullCache:
    def get(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None


def _runner(config_data=None, providers=None):
    config = FakeConfig(
        {
            "models": {
                "text": "gemini-fast",
                "vision": "gemini-vision",
                "context_window": 1000000,
            },
            "ollama": {"enabled": True, "model": "llama-local"},
            "model_router": {
                "long_context_chars": 100,
                "fallbacks": {
                    "fast": ["reasoning", "local"],
                    "reasoning": ["fast", "local"],
                    "vision": ["reasoning", "fast", "local"],
                    "long_context": ["reasoning", "fast", "local"],
                },
            },
            **(config_data or {}),
        }
    )
    registry = ModelRegistry(config)
    policy = ModelPolicy(registry, config)
    return ModelRunner(policy, provider_clients=providers or {}, cache=NullCache())


def test_intent_detection_covers_required_categories():
    policy = _runner().policy

    assert policy.detect_intent("hello") == "chat"
    assert policy.detect_intent("please patch this bug") == "code_edit"
    assert policy.detect_intent("run tests now") == "test_run"
    assert policy.detect_intent("pytest failure traceback") == "test_failure_analysis"
    assert policy.detect_intent("find this button in the screenshot") == "vision"
    assert policy.detect_intent("summarize this document") == "summary"
    assert policy.detect_intent("plan the tool workflow") == "tool_planning"
    assert policy.detect_intent("delete these files", risk="high") == "high_risk_action"


def test_model_choice_matrix_and_long_context_budget():
    policy = _runner().policy

    assert policy.choose("chat").profile == "fast"
    assert policy.choose("code_edit").profile == "reasoning"
    assert policy.choose("vision").model.model_id == "gemini-vision"
    assert policy.choose(None, text="plain chat", context_chars=500).profile == "long_context"
    assert policy.choose("test_failure_analysis").profile == "reasoning"


def test_registry_loads_configured_profiles_and_aliases():
    config = FakeConfig(
        {
            "models": {"text": "legacy-text", "vision": "legacy-vision"},
            "ollama": {"enabled": False, "model": "local-old"},
            "model_router": {
                "models": {
                    "fast": {
                        "model_id": "custom-fast",
                        "provider": "gemini",
                        "capabilities": ["text", "tools"],
                        "latency_tier": "low",
                    }
                },
                "aliases": {"routine": "fast"},
            },
        }
    )

    registry = ModelRegistry(config)

    assert registry.get("routine").model_id == "custom-fast"
    assert registry.get("vision").model_id == "legacy-vision"


def test_fallback_chain_handles_rate_limits_and_records_telemetry():
    calls = []

    def gemini_provider(model, call):
        calls.append(model.name)
        raise RuntimeError("429 rate limit")

    def ollama_provider(model, call):
        calls.append(model.name)
        return f"local:{call.intent}:{model.model_id}"

    runner = _runner(providers={"gemini": gemini_provider, "ollama": ollama_provider})

    result = runner.generate(ModelCall(prompt="fix failing pytest", intent="test_failure_analysis"))

    assert result.text == "local:test_failure_analysis:llama-local"
    assert result.model_name == "local"
    assert result.fallback_attempts == ("fast", "local")
    assert calls == ["reasoning", "fast", "local"]
    assert runner.telemetry[-1]["success"] is True
    assert runner.telemetry[-1]["fallbacks"] == ["fast", "local"]


def test_successful_call_uses_selected_model_and_logs_reason():
    def gemini_provider(model, call):
        return f"{model.name}:{call.prompt}"

    runner = _runner(providers={"gemini": gemini_provider})

    result = runner.generate(ModelCall(prompt="write code", intent="code_edit", use_cache=False))

    assert result.text == "reasoning:write code"
    assert result.reason.startswith("code generation")
    assert runner.telemetry[-1]["profile"] == "reasoning"
    assert runner.telemetry[-1]["duration_ms"] >= 0


def test_code_verification_loop_routes_failure_analysis_to_reasoning_profile():
    seen = []

    def gemini_provider(model, call):
        seen.append((model.name, call.intent))
        return f"{model.name}:{call.intent}"

    loop = CodeVerificationLoop(_runner(providers={"gemini": gemini_provider}))

    assert loop.plan("add feature").startswith("reasoning:tool_planning")
    assert loop.patch("fix bug").startswith("reasoning:code_edit")
    assert loop.analyze_failure("pytest", "AssertionError").startswith(
        "reasoning:test_failure_analysis"
    )
    assert seen == [
        ("reasoning", "tool_planning"),
        ("reasoning", "code_edit"),
        ("reasoning", "test_failure_analysis"),
    ]


def test_agent_error_handler_uses_routed_model(monkeypatch):
    from agent import error_handler
    from agent.error_handler import ErrorDecision

    seen = {}

    class FakeResponse:
        text = '{"decision": "replan", "reason": "bad input", "fix_suggestion": "use another tool", "max_retries": 1, "user_message": "Adjusting, sir."}'

    class FakeModel:
        def generate_content(self, prompt):
            seen["prompt"] = prompt
            return FakeResponse()

    def fake_get_routed_model(**kwargs):
        seen["kwargs"] = kwargs
        return FakeModel()

    monkeypatch.setattr(error_handler, "get_routed_model", fake_get_routed_model)

    result = error_handler.analyze_error(
        {"step": 1, "tool": "web_search", "description": "search", "parameters": {}},
        "timeout",
    )

    assert result["decision"] == ErrorDecision.REPLAN
    assert seen["kwargs"]["intent"] == "test_failure_analysis"
    assert seen["kwargs"]["use_cache"] is False
    assert "timeout" in seen["prompt"]


def test_executor_summary_uses_routed_model(monkeypatch):
    from agent import executor

    seen = {}

    class FakeResponse:
        text = "All done, sir."

    class FakeModel:
        def generate_content(self, prompt):
            seen["prompt"] = prompt
            return FakeResponse()

    def fake_get_routed_model(**kwargs):
        seen["kwargs"] = kwargs
        return FakeModel()

    monkeypatch.setattr(executor, "get_routed_model", fake_get_routed_model)

    summary = executor.AgentExecutor()._summarize(
        "make a report",
        [{"description": "Collected source data"}],
        speak=None,
    )

    assert summary == "All done, sir."
    assert seen["kwargs"]["intent"] == "summary"
    assert "Collected source data" in seen["prompt"]
