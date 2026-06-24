import json
import sys
import types


def test_save_api_keys_preserves_existing_and_adds_optional_fields(tmp_path, monkeypatch):
    from memory import config_manager

    config_file = tmp_path / "api_keys.json"
    config_file.write_text(json.dumps({"gemini_api_key": "existing-key"}), encoding="utf-8")
    monkeypatch.setattr(config_manager, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", config_file)

    config_manager.save_api_keys(
        openai_api_key="openai-key",
        ollama_base_url="http://localhost:11434",
    )

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["gemini_api_key"] == "existing-key"
    assert data["openai_api_key"] == "openai-key"
    assert data["ollama_base_url"] == "http://localhost:11434"


def test_save_setup_config_persists_router_choice_without_config_loader(tmp_path, monkeypatch):
    from memory import config_manager

    config_file = tmp_path / "api_keys.json"
    monkeypatch.setattr(config_manager, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", config_file)
    fake_loader = types.ModuleType("config.config_loader")

    class FakeConfig:
        def update_local_settings(self, settings):
            return settings

    fake_loader.get_config = lambda: FakeConfig()
    monkeypatch.setitem(sys.modules, "config.config_loader", fake_loader)

    result = config_manager.save_setup_config(
        gemini_api_key="gemini-key",
        preferred_model="local",
        model_scope="all",
    )

    assert json.loads(config_file.read_text(encoding="utf-8"))["gemini_api_key"] == "gemini-key"
    assert result["model_router"]["preferred_profile"] == "local"
    assert result["model_router"]["model_scope"] == "all"


def test_gemini_key_validation_requires_gemini_shape():
    from memory.config_manager import is_valid_gemini_key

    assert is_valid_gemini_key("AIza" + "x" * 32) is True
    assert is_valid_gemini_key("sk-proj-" + "x" * 40) is False
    assert is_valid_gemini_key("http://localhost:11434") is False


def test_first_run_wizard_saves_prompted_gemini_key(monkeypatch):
    from core import first_run_wizard

    saved = {}

    class FakeConfig:
        def reload(self):
            saved["reloaded"] = True

    monkeypatch.setattr(first_run_wizard, "has_valid_gemini_key", lambda: bool(saved.get("key")))
    monkeypatch.setattr(first_run_wizard, "_prompt_in_terminal", lambda: "AIza" + "x" * 32)
    monkeypatch.setattr(first_run_wizard, "save_api_keys", lambda gemini_api_key: saved.update(key=gemini_api_key))
    monkeypatch.setattr(first_run_wizard, "get_config", lambda: FakeConfig())

    assert first_run_wizard.ensure_gemini_api_key(use_gui=False) is True
    assert saved["key"].startswith("AIza")
    assert saved["reloaded"] is True
