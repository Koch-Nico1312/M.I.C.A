import json
import tempfile
import unittest
from pathlib import Path

from core.plugin_system import PluginManager

PLUGIN_CONTENT = """TOOL_DECLARATION = {
    "name": "demo_tool",
    "description": "Demo plugin",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

def demo_tool(parameters: dict, **kwargs):
    return "plugin-ok"
"""


class PluginSystemTests(unittest.TestCase):
    def test_plugin_manager_loads_and_executes_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp)
            (plugins_dir / "demo_tool.py").write_text(PLUGIN_CONTENT, encoding="utf-8")

            manager = PluginManager(plugins_dir=plugins_dir)
            loaded = manager.load_all_plugins()

            self.assertEqual(len(loaded), 1)
            self.assertEqual(manager.get_tool_declarations()[0]["name"], "demo_tool")
            self.assertEqual(manager.execute_tool("demo_tool", {}), "plugin-ok")

    def test_plugin_manager_skips_disabled_manifest_plugins(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "disabled_tool"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "id": "disabled_tool",
                        "name": "Disabled Tool",
                        "entrypoint": "plugin.py",
                        "permissions": ["text:read"],
                        "enabled": False,
                    }
                ),
                encoding="utf-8",
            )
            (plugin_dir / "plugin.py").write_text(PLUGIN_CONTENT, encoding="utf-8")

            manager = PluginManager(plugins_dir=Path(tmp))

            self.assertEqual(manager.load_all_plugins(), [])
            self.assertEqual(manager.get_tool_declarations(), [])


if __name__ == "__main__":
    unittest.main()
