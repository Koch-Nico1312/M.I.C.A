import json
import subprocess


def test_agent_reach_doctor_missing_cli(monkeypatch):
    from actions import agent_reach

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: None)

    result = agent_reach.agent_reach({"action": "doctor"})

    assert "not installed" in result


def test_agent_reach_doctor_uses_current_json_flag(monkeypatch):
    from actions import agent_reach

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"channels": [{"name": "web", "status": "ready"}]}',
            stderr="",
        )

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: "agent-reach")
    monkeypatch.setattr(agent_reach.subprocess, "run", fake_run)

    result = json.loads(agent_reach.agent_reach({"action": "doctor", "timeout": 3}))

    assert result["role"] == "capability installer and health checker"
    assert result["platform_commands"] is False
    assert result["doctor"]["channels"][0]["status"] == "ready"
    assert calls[0][0] == ["agent-reach", "doctor", "--json"]
    assert calls[0][1]["timeout"] == 3


def test_agent_reach_rejects_obsolete_platform_subcommand():
    from actions.agent_reach import agent_reach

    result = agent_reach({"action": "run", "args": ["github", "owner/repo"]})

    assert "not an Agent-Reach CLI command" in result
    assert "GitHub integration" in result


def test_agent_reach_runs_real_read_only_command(monkeypatch):
    from actions import agent_reach

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="Agent Reach v1.2.3", stderr="")

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: "agent-reach")
    monkeypatch.setattr(agent_reach.subprocess, "run", fake_run)

    result = agent_reach.agent_reach({"action": "run", "args": ["version"]})

    assert result == "Agent Reach v1.2.3"
    assert calls[0][0] == ["agent-reach", "version"]


def test_agent_reach_blocks_state_changing_raw_command():
    from actions.agent_reach import agent_reach

    result = agent_reach({"action": "run", "args": ["configure"]})

    assert "change external state" in result


def test_agent_reach_transcribe_builds_current_cli_command(monkeypatch):
    from actions import agent_reach

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="transcript saved", stderr="")

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: "agent-reach")
    monkeypatch.setattr(agent_reach.subprocess, "run", fake_run)

    result = agent_reach.agent_reach(
        {
            "action": "transcribe",
            "source": "https://example.com/audio.mp3",
            "provider": "groq",
            "output": "transcript.txt",
        }
    )

    assert result == "transcript saved"
    assert calls[0] == [
        "agent-reach",
        "transcribe",
        "https://example.com/audio.mp3",
        "--provider",
        "groq",
        "--output",
        "transcript.txt",
    ]


def test_agent_reach_capabilities_explains_upstream_role(monkeypatch):
    from actions import agent_reach

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: None)

    result = json.loads(agent_reach.agent_reach({"action": "capabilities"}))

    assert result["installed"] is False
    assert "does not expose" in result["platform_access"]
    assert "github" in result["legacy_route_guidance"]


def test_agent_reach_timeout_is_bounded(monkeypatch):
    from actions import agent_reach

    calls = []

    def fake_run(command, **kwargs):
        calls.append(kwargs["timeout"])
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: "agent-reach")
    monkeypatch.setattr(agent_reach.subprocess, "run", fake_run)

    assert agent_reach.agent_reach({"action": "version", "timeout": 9999}) == "ok"
    assert calls == [600]


def test_agent_reach_declaration_does_not_advertise_fake_platform_commands():
    from tools.tool_declarations import TOOL_DECLARATIONS

    declaration = next(item for item in TOOL_DECLARATIONS if item["name"] == "agent_reach")
    args_description = declaration["parameters"]["properties"]["args"]["description"]

    assert "github" not in args_description.lower()
    assert "doctor" in args_description.lower()
