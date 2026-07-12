from agent.multi_agent_orchestrator import AgentTask, AgentType, SubAgent
from agent.role_profiles import get_role_profile


def test_role_profiles_are_distinct_and_tool_scoped():
    research = get_role_profile("research")
    execution = get_role_profile("execution")
    review = get_role_profile("review")

    assert research.system_prompt != execution.system_prompt
    assert "web_search" in research.allowed_tools
    assert "run_sandbox" in execution.allowed_tools
    assert "run_sandbox" not in review.allowed_tools
    assert len({research.model_intent, execution.model_intent, review.model_intent}) == 3


def test_subagent_passes_executable_profile_to_executor(monkeypatch):
    captured = {}
    agent = SubAgent(AgentType.DEEP_RESEARCH, profile_id="research")

    def fake_execute(**kwargs):
        captured.update(kwargs)
        return "grounded result"

    monkeypatch.setattr(agent.executor, "execute", fake_execute)
    result = agent.execute_task(
        AgentTask("task-1", AgentType.DEEP_RESEARCH, "Research M.I.C.A", context="local repo", profile_id="research")
    )

    assert result.success is True
    assert result.profile_id == "research"
    assert result.model_intent == "research"
    assert captured["allowed_tools"] == set(get_role_profile("research").allowed_tools)
    assert "never invent sources" in captured["system_prompt"]
    assert "local repo" in captured["goal"]


def test_executor_blocks_tools_outside_role_policy(monkeypatch):
    from agent import executor as executor_module

    monkeypatch.setattr(
        executor_module,
        "create_plan",
        lambda _goal: {"steps": [{"step": 1, "tool": "computer_control", "description": "unsafe", "parameters": {}}]},
    )
    executor = executor_module.AgentExecutor()

    try:
        executor.execute("research only", allowed_tools={"web_search"}, system_prompt="Research only")
    except PermissionError as exc:
        assert "computer_control" in str(exc)
    else:
        raise AssertionError("role tool policy did not block an unapproved tool")
