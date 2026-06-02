"""
Dynamic Plugin System for JARVIS
Allows tools to be loaded dynamically from the plugins/ directory
"""

import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolDeclaration:
    """Represents a tool/function declaration for the AI"""

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    category: str = "general"
    enabled: bool = True


class PluginManager:
    """Manages dynamic plugin loading and tool registration"""

    def __init__(self, plugins_dir: Optional[Path] = None):
        if plugins_dir is None:
            # Get base directory
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).resolve().parent.parent
            plugins_dir = base_dir / "plugins"

        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(exist_ok=True)

        self.tools: Dict[str, ToolDeclaration] = {}
        self.loaded_plugins: Dict[str, Any] = {}

    def discover_plugins(self) -> List[Path]:
        """Discover all Python files in the plugins directory"""
        if not self.plugins_dir.exists():
            return []

        plugin_files = list(self.plugins_dir.glob("*.py"))
        # Ignore __init__.py
        return [f for f in plugin_files if f.name != "__init__.py"]

    def load_plugin(self, plugin_path: Path) -> Optional[ToolDeclaration]:
        """Load a single plugin from a file"""
        try:
            # Import the module
            module_name = plugin_path.stem
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)

            if spec is None or spec.loader is None:
                print(f"[Plugin] ERROR: Could not load spec for {plugin_path.name}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Look for tool declaration
            if hasattr(module, "TOOL_DECLARATION"):
                tool_decl = module.TOOL_DECLARATION

                # Get the handler function
                handler_name = tool_decl.get("name")
                if hasattr(module, handler_name):
                    handler = getattr(module, handler_name)

                    tool = ToolDeclaration(
                        name=tool_decl["name"],
                        description=tool_decl["description"],
                        parameters=tool_decl["parameters"],
                        handler=handler,
                        category=tool_decl.get("category", "general"),
                        enabled=tool_decl.get("enabled", True),
                    )

                    self.loaded_plugins[module_name] = module
                    print(f"[Plugin] OK: Loaded {tool.name} from {plugin_path.name}")
                    return tool
                else:
                    print(
                        f"[Plugin] WARN: Handler '{handler_name}' not found in {plugin_path.name}"
                    )

            # Also check for register_tool function
            elif hasattr(module, "register_tool"):
                tool = module.register_tool()
                if tool and isinstance(tool, ToolDeclaration):
                    self.loaded_plugins[module_name] = module
                    print(f"[Plugin] OK: Loaded {tool.name} from {plugin_path.name}")
                    return tool

            return None

        except Exception as e:
            print(f"[Plugin] ERROR: Loading {plugin_path.name} failed: {e}")
            return None

    def load_all_plugins(self) -> List[ToolDeclaration]:
        """Load all plugins from the plugins directory"""
        plugin_files = self.discover_plugins()
        loaded_tools = []

        for plugin_file in plugin_files:
            tool = self.load_plugin(plugin_file)
            if tool:
                self.tools[tool.name] = tool
                loaded_tools.append(tool)

        print(f"[Plugin] Loaded {len(loaded_tools)} plugins")
        return loaded_tools

    def get_tool(self, name: str) -> Optional[ToolDeclaration]:
        """Get a tool by name"""
        return self.tools.get(name)

    def get_all_tools(self) -> List[ToolDeclaration]:
        """Get all loaded tools"""
        return list(self.tools.values())

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        """Get all tool declarations in the format expected by the AI"""
        declarations = []
        for tool in self.tools.values():
            if tool.enabled:
                declarations.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                )
        return declarations

    def execute_tool(self, name: str, args: Dict[str, Any], **kwargs) -> Any:
        """Execute a tool by name"""
        tool = self.tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        try:
            return tool.handler(parameters=args, **kwargs)
        except Exception as e:
            print(f"[Plugin] ERROR: Executing {name} failed: {e}")
            raise

    def reload_plugin(self, plugin_name: str) -> Optional[ToolDeclaration]:
        """Reload a specific plugin"""
        if plugin_name in self.loaded_plugins:
            # Remove old tool
            old_module = self.loaded_plugins[plugin_name]
            if hasattr(old_module, "TOOL_DECLARATION"):
                tool_name = old_module.TOOL_DECLARATION.get("name")
                if tool_name in self.tools:
                    del self.tools[tool_name]

            # Remove from sys.modules
            if plugin_name in sys.modules:
                del sys.modules[plugin_name]

            del self.loaded_plugins[plugin_name]

        # Reload
        plugin_path = self.plugins_dir / f"{plugin_name}.py"
        if plugin_path.exists():
            return self.load_plugin(plugin_path)

        return None

    def create_plugin_template(
        self, name: str, description: str, parameters: Dict[str, Any]
    ) -> Path:
        """Create a template plugin file"""
        template = f'''"""
{name} Plugin for JARVIS
"""

TOOL_DECLARATION = {{
    "name": "{name.lower().replace(' ', '_')}",
    "description": "{description}",
    "parameters": {parameters},
    "category": "custom",
    "enabled": True
}}

def {name.lower().replace(' ', '_')}(parameters: dict, player=None, speak=None, **kwargs) -> str:
    """
    Handler for {name}
    
    Args:
        parameters: Tool parameters from the AI
        player: UI player for audio output
        speak: Function to speak text
    
    Returns:
        Result message
    """
    # Extract parameters
    # param = parameters.get('param_name', default_value)
    
    # Your implementation here
    
    return "Done."
'''

        plugin_path = self.plugins_dir / f"{name.lower().replace(' ', '_')}.py"
        plugin_path.write_text(template, encoding="utf-8")
        return plugin_path


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
