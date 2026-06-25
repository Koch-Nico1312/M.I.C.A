from actions import self_dev_agent as module


def test_self_dev_status_uses_git_snapshot(monkeypatch):
    def fake_git(args, timeout=60, input_text=None):
        if args == ["branch", "--show-current"]:
            return {"ok": True, "stdout": "codex/test\n", "stderr": ""}
        if args == ["status", "--short"]:
            return {"ok": True, "stdout": " M file.py\n", "stderr": ""}
        if args == ["diff", "--stat"]:
            return {"ok": True, "stdout": " file.py | 1 +\n", "stderr": ""}
        return {"ok": True, "stdout": "", "stderr": ""}

    monkeypatch.setattr(module, "_git", fake_git)
    status = module._status()

    assert status["branch"] == "codex/test"
    assert status["ready_for_cycle"] is True
    assert status["dirty_files"] == [" M file.py"]


def test_self_dev_patch_rejects_empty_patch():
    result = module._apply_patch("", "", 10)

    assert result["ok"] is False
    assert "No patch" in result["error"]
