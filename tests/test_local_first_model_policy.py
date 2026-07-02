from dataclasses import dataclass

from core.model_policy import ModelPolicy, Sensitivity
from core.model_registry import ModelProfile


class DummyConfig:
    def __init__(self):
        self.values = {
            "model_router.long_context_chars": 40000,
            "model_router.cost_mode": "balanced",
            "model_router.preferred_profile": "",
            "model_router.fallbacks.local_review": ["reasoning"],
            "model_router.fallbacks.local_code": ["reasoning"],
        }

    def get(self, key, default=None):
        return self.values.get(key, default)


@dataclass
class DummyRegistry:
    config: DummyConfig

    def __post_init__(self):
        self.models = {
            "fast": ModelProfile("fast", "cloud-fast", provider="gemini"),
            "reasoning": ModelProfile("reasoning", "cloud-reasoning", provider="gemini"),
            "local": ModelProfile("local", "llama", provider="ollama", cost_tier="free"),
            "local_review": ModelProfile(
                "local_review",
                "llama-review",
                provider="ollama",
                capabilities=("text", "summary"),
                cost_tier="free",
            ),
            "local_code": ModelProfile(
                "local_code",
                "llama-code",
                provider="ollama",
                capabilities=("text", "code"),
                cost_tier="free",
            ),
        }

    def get(self, name):
        return self.models[name]


def test_secret_prompt_routes_local_and_disallows_cloud():
    policy = ModelPolicy(DummyRegistry(DummyConfig()))

    decision = policy.choose(text="my api key token is sk-test", intent="chat")

    assert decision.sensitivity == Sensitivity.SECRET.value
    assert decision.profile in {"local_code", "local_review", "local"}
    assert decision.cloud_allowed is False


def test_private_summary_prefers_local_review():
    policy = ModelPolicy(DummyRegistry(DummyConfig()))

    decision = policy.choose(text="summarize my personal calendar and contacts")

    assert decision.intent == "summary"
    assert decision.sensitivity == Sensitivity.PRIVATE.value
    assert decision.profile == "local_review"


def test_public_code_still_uses_reasoning_route():
    policy = ModelPolicy(DummyRegistry(DummyConfig()))

    route = policy.explain_route("fix code for this public sample project")

    assert route["intent"] == "code_edit"
    assert route["profile"] == "reasoning"
    assert route["cloud_allowed"] is True
