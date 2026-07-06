import subprocess


def test_agent_reach_doctor_missing_cli(monkeypatch):
    from actions import agent_reach

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: None)

    result = agent_reach.agent_reach({"action": "doctor"})

    assert "not installed" in result


def test_agent_reach_blocks_login_state_without_opt_in():
    from actions.agent_reach import agent_reach

    result = agent_reach({"action": "run", "args": ["reddit", "search", "mica"]})

    assert "login state or cookies" in result


def test_agent_reach_runs_allowlisted_command(monkeypatch):
    from actions import agent_reach

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="doctor ok", stderr="")

    monkeypatch.setattr(agent_reach.shutil, "which", lambda _name: "agent-reach")
    monkeypatch.setattr(agent_reach.subprocess, "run", fake_run)

    result = agent_reach.agent_reach({"action": "run", "args": ["doctor"], "timeout": 3})

    assert result == "doctor ok"
    assert calls[0][0] == ["agent-reach", "doctor"]
    assert calls[0][1]["timeout"] == 3
