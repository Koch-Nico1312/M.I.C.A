from pathlib import Path

from core.app_autostart import AppAutostartManager
from core.assistant_identity import AssistantIdentityManager
from core.wake_word import WakeWordDetector


def test_windows_autostart_is_explicit_reversible_and_per_user(tmp_path):
    entrypoint = tmp_path / "main.py"
    entrypoint.write_text("print('mica')", encoding="utf-8")
    target = tmp_path / "Startup" / "M.I.C.A.cmd"
    manager = AppAutostartManager(
        platform_name="Windows",
        target_path=target,
        python_executable="C:/Python/python.exe",
        entrypoint=entrypoint,
    )

    assert manager.preview()["automatic_changes"] is False
    assert manager.enable()["enabled"] is True
    assert "M.I.C.A" in target.name
    assert str(entrypoint) in target.read_text(encoding="utf-8")
    assert manager.disable()["enabled"] is False


def test_assistant_identity_persists_consistent_name_and_wake_aliases(tmp_path):
    path = tmp_path / "identity.json"
    manager = AssistantIdentityManager(path)
    manager.configure(display_name="Mika", wake_word="hey mika", aliases=["mika"])

    restored = AssistantIdentityManager(path).snapshot()
    assert restored["display_name"] == "Mika"
    assert restored["wake_word"] == "hey mika"
    assert restored["aliases"] == ["hey mika", "mika"]


def test_wake_word_detector_never_fakes_detection_without_model():
    detector = WakeWordDetector(model_path="")

    assert detector.status()["available"] is False
    assert detector.process_pcm(b"\x00\x00" * 512) is False
    assert "real" in detector.status()["last_error"]


def test_porcupine_adapter_processes_real_detector_frames():
    class FakePorcupine:
        frame_length = 4

        def process(self, frame):
            return 0 if frame == [1, 2, 3, 4] else -1

    detector = WakeWordDetector(model_path="")
    detector.engine = "porcupine"
    detector._model = FakePorcupine()

    assert detector.process_pcm(b"\x01\x00\x02\x00\x03\x00\x04\x00") is True


def test_user_facing_reminder_and_youtube_dialog_use_mica_name():
    reminder_source = (Path(__file__).parents[1] / "actions" / "reminder.py").read_text(encoding="utf-8")
    youtube_source = (Path(__file__).parents[1] / "actions" / "youtube_video.py").read_text(encoding="utf-8")

    assert "M.I.C.A Reminder" in reminder_source
    assert "J.A.R.V.I.S Reminder" not in reminder_source
    assert 'askstring("M.I.C.A"' in youtube_source
