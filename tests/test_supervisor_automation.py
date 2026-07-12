from datetime import datetime

from core.supervisor_automation import SupervisorAutomationManager


INBOX = [
    {"id": "approval", "priority": "urgent", "title": "Freigabe wartet", "detail": "Systemänderung prüfen"},
    {"id": "focus", "priority": "low", "title": "Fokus setzen", "detail": "Priorität fehlt"},
]


def test_supervisor_automation_respects_threshold_and_quiet_hours(tmp_path):
    manager = SupervisorAutomationManager(tmp_path / "automation.json")
    manager.configure({"desktop_notifications": True, "min_priority": "high", "quiet_start": 22, "quiet_end": 7})
    delivered = []

    result = manager.evaluate(
        INBOX,
        now=datetime(2026, 7, 12, 23, 0),
        notifier=lambda title, detail, priority: delivered.append((title, detail, priority)) or True,
    )

    assert result["quiet"] is True
    assert result["candidate_count"] == 1
    assert delivered == []


def test_supervisor_automation_deduplicates_desktop_notifications(tmp_path):
    manager = SupervisorAutomationManager(tmp_path / "automation.json")
    manager.configure({"desktop_notifications": True, "min_priority": "normal"})
    delivered = []
    notify = lambda title, detail, priority: delivered.append((title, priority)) or True

    first = manager.evaluate(INBOX, now=datetime(2026, 7, 12, 12, 0), notifier=notify)
    second = manager.evaluate(INBOX, now=datetime(2026, 7, 12, 12, 5), notifier=notify)

    assert len(first["notifications"]) == 1
    assert second["notifications"] == []
    assert delivered == [("Freigabe wartet", "urgent")]


def test_supervisor_automation_persists_dismissals(tmp_path):
    path = tmp_path / "automation.json"
    manager = SupervisorAutomationManager(path)
    manager.dismiss("approval")

    restored = SupervisorAutomationManager(path)
    result = restored.evaluate(INBOX, now=datetime(2026, 7, 12, 12, 0))
    assert result["candidate_count"] == 0


def test_focus_mode_and_read_state_are_persistent(tmp_path):
    path = tmp_path / "automation.json"
    manager = SupervisorAutomationManager(path)
    manager.configure({"focus_mode": True, "quiet_start": 21, "quiet_end": 8})
    manager.mark_read("failed-run")
    manager.mark_all_read(["approval", "limit"])

    restored = SupervisorAutomationManager(path).snapshot()
    assert restored["focus_mode"] is True
    assert restored["quiet_start"] == 21
    assert restored["read_ids"] == ["failed-run", "approval", "limit"]
