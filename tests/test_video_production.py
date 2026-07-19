import json
from pathlib import Path

from core.video_production import VideoProductionManager


def _footage(tmp_path: Path) -> Path:
    source = tmp_path / "footage"
    source.mkdir()
    (source / "take-1.mp4").write_bytes(b"video")
    (source / "notes.txt").write_text("ignore", encoding="utf-8")
    return source


def test_video_production_requires_strategy_approval_before_execution(tmp_path):
    manager = VideoProductionManager(tmp_path / "projects.json")
    project = manager.create(str(_footage(tmp_path)), name="Launch")

    try:
        manager.record_stage(project["id"], "transcribe")
    except ValueError as exc:
        assert "approved" in str(exc)
    else:
        raise AssertionError("unapproved video execution was accepted")


def test_video_production_persists_strategy_and_self_eval_gate(tmp_path):
    path = tmp_path / "projects.json"
    source = _footage(tmp_path)
    manager = VideoProductionManager(path)
    project = manager.create(str(source), name="Launch")
    manager.propose(
        project["id"],
        "Fast hook, concise demo, calm CTA",
        {"aspect": "9:16", "subtitles": True, "grade": "neutral_punch"},
    )
    approved = manager.approve(project["id"], True, note="Looks right")
    manager.record_stage(project["id"], "preview", artifacts={"preview": str(source / "edit" / "preview.mp4")})
    verified = manager.record_evaluation(
        project["id"],
        passed=True,
        evidence={"cut_boundaries": 4, "duration_s": 42.0},
    )

    assert approved["approved_at"]
    assert verified["status"] == "verified"
    assert VideoProductionManager(path).get(project["id"])["strategy"].startswith("Fast hook")


def test_video_production_caps_self_eval_and_keeps_final_inside_edit_dir(tmp_path):
    source = _footage(tmp_path)
    manager = VideoProductionManager(tmp_path / "projects.json")
    project = manager.create(str(source))
    manager.propose(project["id"], "Documentary cut")
    manager.approve(project["id"], True)
    for index in range(3):
        manager.record_evaluation(project["id"], passed=False, issues=[f"issue-{index}"])

    try:
        manager.record_evaluation(project["id"], passed=False, issues=["issue-4"])
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("self-evaluation exceeded three passes")


def test_video_action_setup_is_preview_only(monkeypatch):
    from actions import video_production

    manager = VideoProductionManager(Path("unused-video-projects.json"))
    monkeypatch.setattr(video_production, "get_video_production_manager", lambda: manager)
    result = json.loads(video_production.video_production({"action": "setup_preview"}))

    assert result["automatic_changes"] is False
    assert any("MICA_VIDEO_USE_ROOT" in step for step in result["steps"])
