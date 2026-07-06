from datetime import datetime

from core.daily_briefing import DailyBriefing
from core.morning_routine import MorningRoutine
from core.session_manager import SessionContextManager
from core.workflow_engine import WorkflowEngine
from memory.memory_manager import cleanup_expired_memories, load_memory, remember_todo


def test_structured_briefing_prioritizes_focus_without_live_calls(monkeypatch):
    def fake_memory():
        return {
            "identity": {"name": {"value": "Alex"}},
            "projects": {"mica": {"value": "Finish M.I.C.A session intelligence"}},
            "todos": {"review": {"value": "Review morning flow", "tags": ["urgent"]}},
            "preferences": {"habit_water": {"value": "Drink water before coffee", "tags": ["habit"]}},
        }

    monkeypatch.setattr("memory.memory_manager.load_memory", fake_memory)
    briefing = DailyBriefing(
        providers={
            "calendar": lambda: [{"title": "Planning", "time": "09:00"}],
            "email": lambda: "Email: 2 important unread messages.",
            "weather": lambda: "Weather: mild and dry.",
            "reminders": lambda: ["Pay invoice"],
        },
        clock=lambda: datetime(2026, 6, 24, 8, 0),
    )

    result = briefing.generate_briefing("morning", time_budget_minutes=20)

    assert result["date"] == "2026-06-24"
    assert result["focus"][0]["priority"] == "high"
    assert any(item["category"] == "calendar" for item in result["items"])
    assert any("Drink water" in item["content"] for item in result["items"])


def test_session_resume_tracks_activity_open_ends_and_recent_files(tmp_path):
    manager = SessionContextManager(max_messages=20)
    manager._history_path = tmp_path / "chat_history.json"
    manager.clear()
    manager.record_user_message("Implement session resume")
    manager.record_activity(
        "Edited session manager",
        files=["core/session_manager.py", "tests/test_session_manager.py"],
        open_ends=["Run focused tests"],
        timestamp=datetime(2026, 6, 24, 10, 0),
    )

    packet = manager.build_resume_packet()
    resume_text = manager.resume_where_left_off()

    assert packet["has_context"] is True
    assert packet["recent_files"][0] == "core/session_manager.py"
    assert packet["open_ends"] == ["Run focused tests"]
    assert "Edited session manager" in resume_text


def test_quick_commands_use_session_and_daily_flows(monkeypatch, tmp_path):
    class FakeBriefing:
        def generate_morning_briefing(self):
            return "Morning focus"

        def generate_evening_briefing(self):
            return "Evening wrap"

    monkeypatch.setattr("core.daily_briefing.get_daily_briefing", lambda: FakeBriefing())
    routine = MorningRoutine()

    start = routine.run_quick_command("start my day")
    focus = routine.run_quick_command("focus mode", focus_minutes=25)

    assert start["action"] == "start_day"
    assert start["briefing"] == "Morning focus"
    assert focus["next_steps"][0].startswith("Start 25-minute")


def test_memory_structured_todo_expiry_cleanup(tmp_path):
    memory_path = tmp_path / "long_term.json"
    remember_todo(
        "old_task",
        "Clean stale task",
        tags=["todo", "routine"],
        expires_in_days=-1,
        memory_path=memory_path,
    )
    remember_todo(
        "new_task",
        "Keep current task",
        tags=["todo"],
        expires_in_days=3,
        memory_path=memory_path,
    )

    removed = cleanup_expired_memories(memory_path=memory_path, now=datetime.now())
    memory = load_memory(memory_path)

    assert removed == 1
    assert "old_task" not in memory["todos"]
    assert memory["todos"]["new_task"]["tags"] == ["todo"]


def test_workflow_routine_flow_factory_uses_existing_workflow_shape(tmp_path):
    engine = WorkflowEngine(persistence_dir=tmp_path)

    workflow = engine.create_routine_flow("wrap up")

    assert workflow.name == "Routine: wrap up"
    assert workflow.overall_risk_level == "low"
    assert [step.action for step in workflow.steps] == ["daily_briefing", "memory"]
    assert workflow.steps[1].parameters == {"kind": "daily_summary"}
