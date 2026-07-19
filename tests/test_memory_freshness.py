from datetime import datetime, timedelta

from core.memory_freshness import MemoryFreshnessManager
from core.memory_lifecycle import MemoryLifecycleHooks
from core.project_state import ProjectStateManager
from core.session_manager import SessionContextManager


def test_freshness_report_surfaces_missing_and_stale_sections(tmp_path):
    manager = MemoryFreshnessManager(
        tmp_path / "freshness.json",
        policies={"current_state": 7, "telos.mission": 90},
    )
    now = datetime(2026, 7, 19, 12, 0, 0)
    manager.touch("current_state", reviewed_at=now - timedelta(days=8))

    report = manager.report(now=now)

    assert report["status"] == "stale"
    assert report["stale_count"] == 2
    assert report["missing_count"] == 1
    assert report["stale"][0]["section"] in {"current_state", "telos.mission"}


def test_freshness_touch_persists_review_metadata(tmp_path):
    path = tmp_path / "freshness.json"
    reviewed_at = datetime(2026, 7, 19, 12, 0, 0)
    manager = MemoryFreshnessManager(path, policies={"ideal_state": 90})
    manager.touch("ideal_state", reviewed_at=reviewed_at, source="test", reason="confirmed")

    restored = MemoryFreshnessManager(path, policies={"ideal_state": 90})
    item = restored.report(now=reviewed_at)["items"][0]

    assert item["stale"] is False
    assert item["source"] == "test"
    assert item["reason"] == "confirmed"


def test_session_lifecycle_persists_handover_and_refreshes_context(tmp_path):
    freshness = MemoryFreshnessManager(
        tmp_path / "freshness.json",
        policies={"session_context": 1},
    )
    state = ProjectStateManager(tmp_path / "project_state.json")
    hooks = MemoryLifecycleHooks(freshness=freshness, project_state=state)
    sessions = SessionContextManager(
        history_path=tmp_path / "history.json",
        lifecycle_hooks=hooks,
    )

    session_id = sessions.start_session()
    context = sessions.build_context_summary()
    assert "Stale: session_context" in context
    sessions.record_user_message("Continue the reliability work")
    sessions.record_activity(
        "Hardened retries",
        files=["core/reliability.py"],
        open_ends=["Add recovery test"],
    )
    sessions.finalize_session(summary="Reliability work in progress")

    handover = state.snapshot()["last_handover"]
    archived = sessions.get_session(session_id)
    assert handover["summary"] == "Reliability work in progress"
    assert handover["open_ends"] == ["Add recovery test"]
    assert archived["memory_lifecycle"]["event"] == "session_end"
    assert freshness.report()["status"] == "fresh"


def test_lifecycle_hooks_fail_open_when_hook_crashes(tmp_path):
    class BrokenHooks:
        def on_session_start(self, _session):
            raise RuntimeError("boom")

        def on_session_end(self, _session):
            raise RuntimeError("boom")

    sessions = SessionContextManager(
        history_path=tmp_path / "history.json",
        lifecycle_hooks=BrokenHooks(),
    )
    session_id = sessions.start_session()
    sessions.record_user_message("Still persist me")

    assert sessions.finalize_session() == session_id
    assert sessions.get_session(session_id)["status"] == "completed"
