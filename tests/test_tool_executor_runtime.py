import pytest

from core.action_history import ActionStatus
from core.tool_executor import ToolExecutor


class FakeApproval:
    def __init__(self, allowed=True, message="Allowed"):
        self.allowed = allowed
        self.message = message
        self.calls = []

    def check_and_request_approval(self, tool_name, action, parameters):
        self.calls.append((tool_name, action, parameters))
        return self.allowed, self.message


class FakeHistory:
    def __init__(self):
        self.records = []

    def record_action(self, **kwargs):
        self.records.append(kwargs)


@pytest.mark.asyncio
async def test_execute_tool_checks_approval_and_records_success(monkeypatch):
    approval = FakeApproval()
    history = FakeHistory()
    monkeypatch.setattr("core.tool_executor.get_approval_flow", lambda: approval)
    monkeypatch.setattr("core.tool_executor.get_action_history", lambda: history)

    executor = ToolExecutor()

    def demo_tool(args, _player=None, _speak=None):
        return f"ok:{args['value']}"

    executor.register_tool("demo_tool", demo_tool)

    result = await executor.execute_tool("demo_tool", {"value": "done"})

    assert result["success"] is True
    assert result["result"] == "ok:done"
    assert approval.calls[0][0] == "demo_tool"
    assert history.records[0]["status"] == ActionStatus.SUCCESS
    assert history.records[0]["tool_name"] == "demo_tool"


@pytest.mark.asyncio
async def test_execute_tool_blocks_unapproved_action_and_records_failure(monkeypatch):
    approval = FakeApproval(False, "Confirmation required")
    history = FakeHistory()
    monkeypatch.setattr("core.tool_executor.get_approval_flow", lambda: approval)
    monkeypatch.setattr("core.tool_executor.get_action_history", lambda: history)
    called = False

    executor = ToolExecutor()

    def risky_tool(_args, _player=None, _speak=None):
        nonlocal called
        called = True
        return "should not run"

    executor.register_tool("file_controller", risky_tool)

    result = await executor.execute_tool("file_controller", {"action": "delete", "path": "x"})

    assert called is False
    assert result["success"] is False
    assert result["approval_required"] is True
    assert history.records[0]["status"] == ActionStatus.FAILED
    assert history.records[0]["action"] == "delete"
