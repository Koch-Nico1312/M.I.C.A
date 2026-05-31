import tempfile
import unittest
from pathlib import Path

from core.healthcheck import build_runtime_report, format_runtime_report


class FakeConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        value = self.values
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def get_api_key(self, service="gemini"):
        return self.values.get("api_key", "")


class FakePlugin:
    def __init__(self, name):
        self.name = name


class FakePluginManager:
    def get_all_tools(self):
        return [FakePlugin("demo_plugin")]


class HealthcheckTests(unittest.TestCase):
    def test_report_marks_ready_when_prompt_and_api_key_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            (base_dir / "core").mkdir()
            (base_dir / "config").mkdir()
            (base_dir / "plugins").mkdir()
            (base_dir / "memory").mkdir()
            (base_dir / "core" / "prompt.txt").write_text("prompt", encoding="utf-8")
            (base_dir / "memory" / "long_term.json").write_text("{}", encoding="utf-8")

            report = build_runtime_report(
                base_dir,
                config=FakeConfig({"api_key": "test-key", "proactive": {"enabled": True}}),
                plugin_manager=FakePluginManager(),
                tool_declarations=[{"name": "demo"}],
            )

            self.assertTrue(report["api_key_present"])
            self.assertEqual(report["plugins"], ["demo_plugin"])
            self.assertEqual(report["tool_count"], 1)

    def test_formatter_includes_warnings_and_enabled_features(self):
        report = {
            "ready": False,
            "api_key_present": False,
            "tool_count": 3,
            "plugins": [],
            "features": {"proactive": True, "gmail": False},
            "missing_required": ["Gemini live client"],
            "warnings": ["Prompt missing."],
            "required_modules": {},
            "optional_modules": {},
        }

        formatted = format_runtime_report(report, verbose=False)

        self.assertIn("Runtime ready: no", formatted)
        self.assertIn("Enabled features: proactive", formatted)
        self.assertIn("Prompt missing.", formatted)


if __name__ == "__main__":
    unittest.main()
