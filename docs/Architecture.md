# M.I.C.A AI Assistant - Architecture Documentation

## Overview

M.I.C.A (Just A Rather Very Intelligent System) is an AI-powered personal assistant that uses voice interaction, tool calling, memory management, and automation to help users with various tasks. This document describes the system architecture, component organization, and design patterns used in the project.

## Communication Gateway

`core/communication_gateway.py` unifies external identities, history, routing,
and notifications. `core/cross_device.py` provides Telegram and Discord
transports, while `core/telephony.py` encapsulates Twilio/SIP. Existing approval
flow, Companion sessions, Voice Mode, Supervisor notifications, and Home
Assistant remain authoritative, so external channels cannot bypass M.I.C.A's
central safety controls.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│  ┌──────────────┐              ┌──────────────┐            │
│  │   GUI Mode   │              │   CLI Mode   │            │
│  │  (PyQt6)     │              │  (Terminal)  │            │
│  └──────────────┘              └──────────────┘            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Main Loop  │  │  Tool Calls  │  │  Action     │      │
│  │   (main.py)  │  │  (tools/)    │  │  Execution  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Core Services                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Memory     │  │  Approval    │  │  Plugin      │      │
│  │   Manager    │  │  Flow        │  │  System      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Workflow    │  │  Performance │  │  Error       │      │
│  │  Engine      │  │  Tracker     │  │  Handler     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Config      │  │  Logging     │  │  Dependency  │      │
│  │  Loader      │  │  System      │  │  Injection   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  AI Model    │  │  Gmail API   │  │  Calendar    │      │
│  │  (Gemini)    │  │              │  │  API         │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Spotify     │  │  Obsidian    │  │  Browser     │      │
│  │  API         │  │  Integration │  │  Control     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Component Organization

### Directory Structure

```
M.I.C.A/
├── actions/              # Action implementations
│   ├── base_action.py    # Base action interface
│   ├── browser_control.py
│   ├── code_helper.py
│   └── ...
├── config/               # Configuration management
│   ├── config_loader.py
│   ├── startup_config.py
│   └── mcp_servers.json
├── core/                 # Core services and utilities
│   ├── action_history.py
│   ├── approval_flow.py
│   ├── dependency_injection.py
│   ├── error_handler.py
│   ├── logger.py
│   ├── memory_manager.py
│   ├── performance_tracker.py
│   ├── plugin_system.py
│   └── workflow_engine.py
├── data/                 # Data storage
│   ├── vector_db/
│   ├── vision_memory/
│   └── workflows/
├── docs/                 # Documentation
├── memory/               # Memory management
│   ├── memory_backup.py
│   └── ...
├── plugins/              # Plugin directory
├── startup/              # Application initialization
│   ├── app_initializer.py
│   ├── safety_initializer.py
│   └── performance_initializer.py
├── tests/                # Test suite
│   ├── mocking_utils.py
│   ├── test_dependency_injection.py
│   └── ...
├── tools/                # Tool declarations
│   └── tool_declarations.py
├── UI/                   # User interface (React/Vite)
├── main.py               # Application entry point
├── config.yaml           # Main configuration file
└── requirements.txt      # Python dependencies
```

## Key Components

### 1. Main Application (main.py)

The main entry point that orchestrates the application startup and main loop. After refactoring, it now delegates responsibilities to specialized modules:

- **UI Initialization**: Handled by `startup/app_initializer.py`
- **Configuration Loading**: Handled by `config/startup_config.py`
- **Safety System**: Handled by `startup/safety_initializer.py`
- **Performance System**: Handled by `startup/performance_initializer.py`

### 2. Tool System (tools/)

The tool system defines all available actions that M.I.C.A can perform. Tools are declared in `tools/tool_declarations.py` and are separated into:

- **Core Tools (TOOL_DECLARATIONS)**: Always available tools
- **Feature Tools (FEATURE_TOOL_DECLARATIONS)**: Optional tools enabled by configuration

### 3. Action System (actions/)

Actions are the concrete implementations of tools. Each action:

- Inherits from `BaseAction` (defined in `actions/base_action.py`)
- Implements `execute()`, `validate_parameters()`, and provides metadata
- Can be registered in the `ActionRegistry`

### 4. Core Services (core/)

#### Memory Manager
Manages conversation memory, long-term memory, and memory compression.

#### Approval Flow
Handles safety checks and user confirmation for risky actions.

#### Plugin System
Dynamic loading of external plugins from the `plugins/` directory.

#### Workflow Engine
Executes multi-step workflows and task automation.

#### Performance Tracker
Monitors operation performance and resource usage.

#### Error Handler
Centralized error handling with custom exception hierarchy and recovery strategies.

#### Dependency Injection
Service container for managing component lifecycles and dependencies.

### 5. Startup System (startup/)

Handles application initialization in a modular way:

- **app_initializer.py**: UI and application mode selection
- **safety_initializer.py**: Safety and approval system setup
- **performance_initializer.py**: Performance monitoring setup

### 6. Configuration (config/)

- **config_loader.py**: Loads configuration from YAML and environment variables
- **startup_config.py**: Startup-specific configuration and constants

## Design Patterns

### Dependency Injection

The system uses a simple dependency injection container (`core/dependency_injection.py`) to manage service lifecycles:

```python
from core.dependency_injection import get_container

container = get_container()
service = container.get("service_name")
```

### Plugin Architecture

The plugin system (`core/plugin_system.py`) allows dynamic loading of external tools:

- Plugins are discovered in the `plugins/` directory
- Each plugin can register its own tools
- Plugins can be enabled/disabled via configuration

### Error Handling Strategy

Centralized error handling (`core/error_handler.py`) provides:

- Custom exception hierarchy (M.I.C.AError, ActionExecutionError, APIError, etc.)
- Error severity classification
- Recovery strategies
- Error history tracking

### Action Interface

All actions implement the `BaseAction` interface (`actions/base_action.py`):

- Consistent execution interface
- Parameter validation
- Metadata for tool declarations
- Lifecycle management (initialize/cleanup)

## Data Flow

### User Request Flow

1. User provides input (voice or text)
2. Input is transcribed (if voice)
3. AI model processes the input
4. Tool selection based on user intent
5. Action execution with parameter validation
6. Safety checks via approval flow
7. Action execution
8. Result returned to user
9. Memory updated if relevant

### Memory Flow

1. Conversation is stored in short-term memory
2. Important facts extracted and stored in long-term memory
3. Periodic memory compression to manage size
4. Automatic backups via memory backup system

### Plugin Loading Flow

1. Application startup
2. Plugin system scans `plugins/` directory
3. Each plugin is loaded and initialized
4. Plugin registers its tools
5. Tools become available to the AI

## Performance Considerations

### Feature Flags

The system uses feature flags (`core/performance_flags.py`) for gradual rollout of optimizations:

- `lazy_tool_declarations`: Lazy load tool declarations
- `cache_system_prompt`: Cache system prompt with TTL
- `lazy_load_actions`: Lazy load action modules
- `reduce_memory_footprint`: Enable memory management

### Caching Strategy

- System prompt caching with 5-minute TTL
- Tool declaration caching when lazy loading enabled
- File modification checking for cache invalidation

### Resource Monitoring

- Background resource monitoring (CPU, memory, disk)
- Performance threshold tracking
- Alert system for slow operations

## Security Architecture

### Permission Profiles

Three permission profiles control action safety:

- **Safe**: No confirmation required
- **Normal**: Confirmation for medium/high risk actions
- **Strict**: Confirmation for all actions

### Action History

Tracks all executed actions for:
- Audit trail
- Learning user preferences
- Security monitoring

### Disabled Actions

Configuration can disable specific actions for:
- Security compliance
- User preferences
- Environment restrictions

## Integration Points

### External APIs

- **Gemini AI**: Primary AI model
- **Gmail API**: Email management
- **Google Calendar**: Calendar integration
- **Spotify API**: Music control
- **Obsidian**: Note-taking integration

### Local Integrations

- **File System**: File operations
- **Browser Control**: Web automation
- **VS Code Bridge**: IDE integration
- **System Control**: OS-level operations

## Testing Architecture

### Test Structure

```
tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
├── benchmarks/        # Performance benchmarks
├── mocking_utils.py   # Common mocking utilities
└── test_*.py         # Test files
```

### CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`) provides:

- Automated testing on push/PR
- Coverage reporting (target: 70%)
- Linting (flake8, black, isort, bandit)
- Security scanning (safety)
- Performance benchmarking

### Mocking Strategy

Common mocks provided in `tests/mocking_utils.py`:

- `MockConfig`: Mock configuration
- `MockFileSystem`: Mock file operations
- `MockDatabase`: Mock database operations
- `MockAPIClient`: Mock API calls

## Future Architecture Considerations

### Scalability

- Consider microservices for large-scale deployments
- Implement message queues for async operations
- Add distributed caching for multi-instance deployments

### Extensibility

- Plugin system for third-party extensions
- Custom action registration
- Modular AI model support

### Monitoring

- Enhanced metrics collection
- Distributed tracing
- Real-time performance dashboards
