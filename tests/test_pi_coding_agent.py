import json
from pathlib import Path

import pytest

from actions import pi_coding_agent as pi_agent
from core.action_loader import ActionLoader
from core.approval_flow import ApprovalFlow, RiskLevel
from tools.tool_declarations import TOOL_DECLARATIONS


def test_resolve_project_path_stays_under_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MICA_PI_WORKSPACE_ROOT", str(workspace))

    resolved = pi_agent._resolve_project_path("demo")

    assert resolved == workspace.resolve() / "demo"
    assert resolved.exists()


@pytest.mark.parametrize("bad_path", ["../escape", "/tmp/escape", "C:\\Users\\user\\Desktop\\repo"])
def test_resolve_project_path_rejects_escapes(monkeypatch, tmp_path, bad_path):
    monkeypatch.setenv("MICA_PI_WORKSPACE_ROOT", str(tmp_path / "workspace"))

    with pytest.raises(ValueError):
        pi_agent._resolve_project_path(bad_path)


def test_pi_coding_agent_requires_enable_flag(monkeypatch):
    monkeypatch.delenv("MICA_PI_ENABLED", raising=False)

    result = pi_agent.pi_coding_agent({"task": "inspect this repo"})

    assert "disabled" in result.lower()


def test_pi_coding_agent_handles_missing_pi_binary(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    logs = tmp_path / "logs"
    monkeypatch.setenv("MICA_PI_ENABLED", "true")
    monkeypatch.setenv("MICA_PI_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(pi_agent, "project_path", lambda *parts: logs.joinpath(*parts))

    result = pi_agent.pi_coding_agent(
        {"task": "inspect this repo", "project_path": "demo", "timeout": 30}
    )
    payload = json.loads(result)

    assert payload["status"] == "failed"
    assert payload["project_dir"] == str((workspace / "demo").resolve())
    assert "Command not found" in payload["output_preview"]
    assert Path(payload["log_path"]).exists()


def test_pi_coding_agent_is_registered():
    declarations = {item["name"]: item for item in TOOL_DECLARATIONS}

    assert "pi_coding_agent" in declarations
    assert "task" in declarations["pi_coding_agent"]["parameters"]["required"]
    assert "pi_coding_agent" in ActionLoader()._action_map


def test_pi_coding_agent_is_high_risk():
    flow = ApprovalFlow()

    assert flow.classify_risk("pi_coding_agent", "pi_coding_agent") == RiskLevel.HIGH
