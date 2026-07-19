# M.I.C.A AI Assistant - API Documentation

## Overview

This document describes the internal APIs used within the M.I.C.A system. These APIs are primarily for developers working on extending or integrating with M.I.C.A.

## Communication API

`GET /api/communications` returns redacted channel status and history.
`POST /api/communications` configures pairings, Telegram polling, confirmed
messages and calls, proactive notifications, and Home Assistant actions. The
signed provider webhook is `POST /api/communications/telephony`. See
[COMMUNICATIONS.md](COMMUNICATIONS.md) for payload actions and setup.

## Table of Contents

- [Core Services](#core-services)
- [Action API](#action-api)
- [Plugin API](#plugin-api)
- [Memory API](#memory-api)
- [Configuration API](#configuration-api)
- [Error Handling API](#error-handling-api)
- [Dependency Injection API](#dependency-injection-api)

## Core Services

### Memory Manager

Location: `core/memory_manager.py`

```python
from core.memory_manager import get_memory_manager

memory_manager = get_memory_manager()

# Add to conversation memory
memory_manager.add_to_conversation(role="user", content="Hello")

# Get conversation history
history = memory_manager.get_conversation_history()

# Add to long-term memory
memory_manager.add_long_term_memory(category="identity", key="name", value="John")

# Retrieve long-term memory
value = memory_manager.get_long_term_memory("name")

# Compress memory
memory_manager.compress_memory()
```

### Approval Flow

Location: `core/approval_flow.py`

```python
from core.approval_flow import get_approval_flow

approval_flow = get_approval_flow()

# Set permission level
approval_flow.set_permission_level("normal")

# Check if action requires approval
requires_approval = approval_flow.requires_approval(action_name, parameters)

# Request user approval
approved = approval_flow.request_approval(action_name, parameters)

# Set confirmation requirements
approval_flow.set_require_confirmation_for_medium(True)
```

### Plugin System

Location: `core/plugin_system.py`

```python
from core.plugin_system import get_plugin_manager

plugin_manager = get_plugin_manager()

# Load plugins from directory
plugin_manager.load_plugins("plugins/")

# Get all tool declarations from plugins
tools = plugin_manager.get_tool_declarations()

# Execute a plugin tool
result = plugin_manager.execute_tool(tool_name, parameters)

# Get plugin status
status = plugin_manager.get_plugin_status(plugin_name)
```

### Workflow Engine

Location: `core/workflow_engine.py`

```python
from core.workflow_engine import get_workflow_engine

workflow_engine = get_workflow_engine()

# Create a workflow
workflow = workflow_engine.create_workflow(
    name="test_workflow",
    steps=[
        {"action": "web_search", "parameters": {"query": "test"}},
        {"action": "save_memory", "parameters": {"category": "notes", "key": "test", "value": "result"}}
    ]
)

# Execute workflow
result = workflow_engine.execute_workflow(workflow)

# Get workflow status
status = workflow_engine.get_workflow_status(workflow_id)
```

### Performance Tracker

Location: `core/performance_tracker.py`

```python
from core.performance_tracker import get_performance_tracker

perf_tracker = get_performance_tracker()

# Start tracking an operation
perf_tracker.start_operation("operation_name", {"context": "value"})

# End tracking
perf_tracker.end_operation("operation_name", {"result": "success"})

# Get performance metrics
metrics = perf_tracker.get_metrics()

# Get slow operations
slow_ops = perf_tracker.get_slow_operations(threshold_ms=2000)
```

## Action API

### Base Action Interface

Location: `actions/base_action.py`

```python
from actions.base_action import BaseAction, ActionMetadata, ActionPermission

class MyAction(BaseAction):
    @property
    def metadata(self):
        return ActionMetadata(
            name="my_action",
            description="Description of my action",
            permission=ActionPermission.MEDIUM,
            category="custom"
        )

    def execute(self, parameters):
        """Execute the action with given parameters."""
        # Implementation here
        return "Result"

    def validate_parameters(self, parameters):
        """Validate parameters before execution."""
        required = ["param1"]
        for param in required:
            if param not in parameters:
                return False
        return True

    def get_required_parameters(self):
        return ["param1"]

    def get_optional_parameters(self):
        return {"param2": "default_value"}
```

### Action Registry

Location: `actions/base_action.py`

```python
from actions.base_action import get_action_registry

registry = get_action_registry()

# Register an action
registry.register(MyAction())

# Get an action
action = registry.get("my_action")

# Get all actions
all_actions = registry.get_all()

# Get enabled actions only
enabled_actions = registry.get_enabled()

# Get tool declarations for all enabled actions
declarations = registry.get_tool_declarations()
```

## Plugin API

### Creating a Plugin

Create a file in the `plugins/` directory:

```python
# plugins/my_plugin.py

from actions.base_action import BaseAction, ActionMetadata, ActionPermission

class MyPluginAction(BaseAction):
    @property
    def metadata(self):
        return ActionMetadata(
            name="plugin_action",
            description="Action from my plugin",
            permission=ActionPermission.SAFE
        )

    def execute(self, parameters):
        return "Plugin result"

    def validate_parameters(self, parameters):
        return True

def register(plugin_manager):
    """Register plugin actions with the plugin manager."""
    plugin_manager.register_action(MyPluginAction())
```

### Plugin Registration

The plugin system automatically discovers and loads plugins from the `plugins/` directory. Each plugin should provide a `register()` function.

## Memory API

### Conversation Memory

```python
from core.memory_manager import get_memory_manager

memory = get_memory_manager()

# Add message
memory.add_to_conversation(role="user", content="Hello")

# Get history
history = memory.get_conversation_history(limit=10)

# Clear conversation
memory.clear_conversation()
```

### Long-term Memory

```python
# Add memory
memory.add_long_term_memory(
    category="preferences",
    key="favorite_color",
    value="blue"
)

# Retrieve memory
value = memory.get_long_term_memory("favorite_color")

# Search memories
results = memory.search_memories("color")

# Delete memory
memory.delete_long_term_memory("favorite_color")
```

### Memory Backup

Location: `memory/memory_backup.py`

```python
from memory.memory_backup import MemoryBackupManager

backup_manager = MemoryBackupManager()

# Create backup
backup_manager.create_backup()

# Restore backup
backup_manager.restore_backup(backup_id)

# List backups
backups = backup_manager.list_backups()

# Schedule automatic backups
backup_manager.schedule_backup(interval_hours=24)
```

## Configuration API

### Loading Configuration

Location: `config/config_loader.py`

```python
from config.config_loader import get_config

config = get_config()

# Get configuration value
value = config.get("key.path", default="default")

# Get API key
api_key = config.get_api_key("service_name")

# Reload configuration
config.reload()
```

### Startup Configuration

Location: `config/startup_config.py`

```python
from config.startup_config import (
    get_api_key,
    load_system_prompt,
    BASE_DIR,
    DEFAULT_CHANNELS
)

# Get API key
api_key = get_api_key()

# Load system prompt
prompt = load_system_prompt()

# Get base directory
base = BASE_DIR
```

## Error Handling API

### Custom Exceptions

Location: `core/error_handler.py`

```python
from core.error_handler import (
    M.I.C.AError,
    ConfigurationError,
    ActionExecutionError,
    APIError,
    ResourceError,
    ErrorSeverity
)

# Raise custom error
raise ActionExecutionError(
    action_name="my_action",
    message="Execution failed",
    context={"error_code": 500}
)
```

### Error Handler

Location: `core/error_handler.py`

```python
from core.error_handler import get_error_handler, handle_errors

error_handler = get_error_handler()

# Handle an error
error_handler.handle(error, context={"key": "value"})

# Register custom handler
def my_handler(error):
    return "handled"

error_handler.register_handler(ValueError, my_handler)

# Register recovery strategy
def my_recovery():
    return True

error_handler.register_recovery_strategy(ValueError, my_recovery)

# Use decorator
@handle_errors(default_return="fallback")
def my_function():
    # May raise exceptions
    return "success"
```

## Dependency Injection API

### Service Container

Location: `core/dependency_injection.py`

```python
from core.dependency_injection import get_container

container = get_container()

# Register singleton service
def my_service_factory():
    return MyService()

container.register_singleton("my_service", my_service_factory)

# Get singleton service
service = container.get("my_service")

# Register transient service
container.register_transient(MyService, lambda: MyService())

# Resolve transient service
instance = container.resolve(MyService)
```

### Registering Core Services

```python
from core.dependency_injection import register_core_services

register_core_services()
```

## Tool Declarations API

### Tool Declaration Format

Tools are declared in `tools/tool_declarations.py`:

```python
TOOL_DECLARATIONS = [
    {
        "name": "tool_name",
        "description": "Tool description",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "param1": {
                    "type": "STRING",
                    "description": "Parameter description"
                }
            },
            "required": ["param1"]
        }
    }
]
```

### Getting Tool Declarations

```python
from tools import TOOL_DECLARATIONS, FEATURE_TOOL_DECLARATIONS

# Get core tools
core_tools = TOOL_DECLARATIONS

# Get feature tools
feature_tools = FEATURE_TOOL_DECLARATIONS
```

## Utility APIs

### Logging

Location: `core/logger.py`

```python
from core.logger import get_logger

logger = get_logger(__name__)

logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.debug("Debug message")
```

### Metrics Collection

Location: `core/metrics_collector.py`

```python
from core.metrics_collector import get_metrics_collector

metrics = get_metrics_collector()

# Record metric
metrics.record_metric("metric_name", value, tags={"tag": "value"})

# Get metrics
all_metrics = metrics.get_metrics()

# Export metrics
metrics.export_to_file("metrics.json")
```

### Paths

Location: `core/paths.py`

```python
from core.paths import (
    project_path,
    resolve_project_root,
    resolve_relative_path
)

# Get path relative to project
path = project_path("config", "config.yaml")

# Resolve project root
root = resolve_project_root()

# Resolve relative path
resolved = resolve_relative_path("relative/path")
```

## Type Hints

The codebase uses Python type hints extensively. Key types:

```python
from typing import Any, Dict, List, Optional, Callable, TypeVar, Type

T = TypeVar("T")

def example_function(
    param1: str,
    param2: Optional[int] = None
) -> Dict[str, Any]:
    """Example function with type hints."""
    return {"result": param1}
```

## Best Practices

### Error Handling

- Always use custom exceptions from `core/error_handler.py`
- Provide context information when raising errors
- Use the `@handle_errors` decorator for functions that may fail

### Action Development

- Inherit from `BaseAction`
- Implement all required methods
- Provide accurate metadata
- Validate parameters before execution

### Plugin Development

- Provide a `register()` function
- Use the action interface for tools
- Keep plugins lightweight
- Document plugin dependencies

### Memory Usage

- Use conversation memory for temporary context
- Use long-term memory for persistent facts
- Compress memory regularly
- Back up memory periodically

### Performance

- Use feature flags for experimental features
- Monitor operation performance
- Cache expensive operations
- Use lazy loading where appropriate

## API Stability

### Stable APIs

The following APIs are considered stable and will maintain backward compatibility:

- Core service getters (get_memory_manager, get_approval_flow, etc.)
- Base action interface
- Plugin registration API
- Configuration API

### Experimental APIs

The following APIs are experimental and may change:

- Dependency injection container
- Performance tracking API
- Workflow engine API

### Deprecated APIs

No APIs are currently deprecated. Any future deprecations will be announced in the CHANGELOG.
