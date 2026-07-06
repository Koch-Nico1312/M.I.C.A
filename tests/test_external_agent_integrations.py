import json

import actions.browser_agent as browser_agent_module
import actions.tool_provider as tool_provider_module
from actions.browser_agent import browser_agent
from actions.computer_control import computer_control
from actions.self_dev_agent import self_dev_agent
from actions.tool_provider import tool_provider
from core.action_loader import ActionLoader
from core.external_agent_integrations import IntegrationResult


def test_action_loader_exposes_external_agent_actions():
    loader = ActionLoader()
    declarations = loader.get_tool_declarations()
    names = {declaration["name"] for declaration in declarations}

    assert "browser_agent" in names
    assert "tool_provider" in names


def test_browser_agent_records_adapter_result(monkeypatch):
    async def fake_run(*args, **kwargs):
        return IntegrationResult(
            True,
            "browser_use",
            "agent",
            result="done",
            artifacts={"trace": "data/browser_agent_runs/test.json"},
        )

    monkeypatch.setattr(browser_agent_module, "run_browser_use_agent", fake_run)
    monkeypatch.setattr(browser_agent_module, "_record", lambda *_args, **_kwargs: None)
    result = json.loads(browser_agent({"task": "Open example.com", "headless": True}))

    assert result["provider"] == "browser_use"
    assert result["action"] == "agent"
    assert result["ok"] is True
    assert result["artifacts"]["trace"].endswith("test.json")


def test_computer_control_cua_status_is_non_destructive(monkeypatch):
    monkeypatch.delenv("JARVIS_CUA_DRIVER_CMD", raising=False)
    result = json.loads(computer_control({"action": "cua_status"}))

    assert result["provider"] == "cua"
    assert "available" in result


def test_tool_provider_status_handles_missing_composio(monkeypatch):
    def fake_get_client(self):
        raise RuntimeError("not configured")

    monkeypatch.setattr(tool_provider_module.ComposioToolProvider, "_get_client", fake_get_client)
    monkeypatch.setattr(tool_provider_module, "_record", lambda *_args, **_kwargs: None)
    result = json.loads(tool_provider({"action": "status"}))

    assert result["provider"] == "composio"
    assert result["action"] == "status"
    assert result["ok"] is False


def test_self_dev_openhands_status_returns_checks():
    result = json.loads(self_dev_agent({"action": "openhands_status"}))

    assert result["provider"] == "openhands"
    assert result["action"] == "status"
    assert isinstance(result["result"], list)
