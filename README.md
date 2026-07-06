# M.I.C.A

M.I.C.A is a local-first AI assistant and personal automation workspace. It is built for a Windows-oriented desktop setup, with a Python runtime, Gemini model integration, voice interaction, tool execution, memory, approvals, workflows, local knowledge, and a React/Vite Studio UI.

The runtime is modular: `main.py` starts the app, `core/jarvis_live.py` runs the M.I.C.A assistant loop, `tools/` declares callable tools, `actions/` implements those tools, and `core/` provides shared services such as configuration, model routing, safety approvals, monitoring, workflows, plugins, publishing, and the Studio platform hub.

## Current Capabilities

- Gemini 2.5 live/text/vision defaults with centralized model routing and optional Ollama fallback.
- Voice-capable assistant loop, CLI mode, and desktop UI startup with browser fallback support.
- Tool calling for browser control, desktop automation, files, reminders, messaging, weather, YouTube, Spotify, Gmail, Google Calendar, local analysis, screen processing, and more.
- Safety approvals, permission profiles, disabled-action controls, and persistent action history.
- Long-term memory, conversation compression, hybrid retrieval, memory curation, backups, Obsidian support, and optional ChromaDB vector storage.
- Local analysis for files/images/documents plus multimodal context and passive vision hooks.
- Workflow engine, task pipeline, background tasks, automation scheduling, proactive suggestions, and daily/morning routines.
- Platform Hub / M.I.C.A Studio Solo Workspace for private agents, knowledge sync, document ingestion, sandbox runs, artifacts, publishing links, companion access, evaluations, metrics, marketplace review, MCP tools, and a 20-point audit.
- React/Vite frontend workspace under `UI/`, backed by the Python `ui_bridge.py` API surface.
- Docker Compose, Helm manifests, Postgres migration assets, and release helper scripts for deployment-oriented workflows.

## Repository Layout

```text
.
|-- actions/          # Concrete action implementations called by tools
|-- agent/            # Planner, executor, task queue, pipelines, orchestration
|-- config/           # Config loader, startup config, MCP and API key examples
|-- core/             # Runtime services: live loop, models, safety, platform hub, UI, workflows
|-- data/             # Local runtime state, history, platform store, artifacts, vector DB
|-- deploy/           # Docker, Helm, and Postgres deployment assets
|-- docs/             # Architecture, API, setup, solo workspace, troubleshooting docs
|-- extensions/       # Browser companion extension
|-- memory/           # Memory managers, curation, backups, retrieval, Obsidian bridge
|-- plugins/          # Local plugin directory and examples
|-- scripts/          # Release/build helper scripts
|-- startup/          # Application, safety, and performance initialization
|-- tests/            # Unit, integration, and benchmark tests
|-- tools/            # Gemini tool declarations
|-- UI/               # React/Vite Studio frontend
|-- main.py           # Main runtime entry point
|-- ui_bridge.py      # Local UI/API bridge for Studio and dashboard surfaces
|-- config.yaml       # Main YAML configuration
`-- .env.example      # Environment variable template
```

## Requirements

- Python 3.11+
- A Gemini API key in `GEMINI_API_KEY`
- Windows for the primary desktop automation path
- Optional microphone and speakers for voice mode
- Optional Node.js/npm for `UI/`
- Optional Playwright browsers for browser automation
- Optional Ollama for local model fallback
- Optional Docker/Compose for Postgres, Redis, MinIO, or deployment-style platform storage

Additional integrations can require their own credentials or local setup, such as Gmail, Google Calendar, Spotify, Telegram, Discord, VS Code, Obsidian, OCR tools, smart-home services, or MCP servers.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Create your local environment file:

```powershell
copy .env.example .env
```

Set at least:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

If you want browser automation, install Playwright browsers:

```powershell
python -m playwright install
```

You can also run the helper setup script, which installs requirements, Playwright browsers, and pre-commit hooks:

```powershell
python setup.py
```

## Configuration

M.I.C.A reads `config.yaml` plus environment variables. Use `.env` for secrets and local overrides, and use `config.yaml` for broader runtime defaults.

Important settings include:

- `GEMINI_API_KEY`
- `LIVE_MODEL`, `TEXT_MODEL`, `VISION_MODEL`
- `MODEL_ROUTER_*` and the `model_router` section in `config.yaml`
- `OLLAMA_ENABLED`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- `PASSIVE_VISION_ENABLED`, `RAG_ENABLED`, `HUD_ENABLED`
- `PROACTIVE_SUGGESTIONS_ENABLED`
- `GMAIL_ENABLED`, `CALENDAR_ENABLED`, `SPOTIFY_ENABLED`
- `OBSIDIAN_ENABLED`, `OBSIDIAN_VAULT_PATH`
- `PERMISSION_PROFILE`, `DISABLED_ACTIONS`
- `MICA_PLATFORM_STORE`, `MICA_POSTGRES_URL`, `MICA_REDIS_URL`, `MICA_S3_ENDPOINT`, `MICA_S3_BUCKET`

See `.env.example` and `config.yaml` for the active option set.

## Running M.I.C.A

Start the desktop assistant:

```powershell
.\venv\Scripts\python.exe .\main.py
```

Run in CLI mode:

```powershell
.\venv\Scripts\python.exe .\main.py --cli
```

On startup, M.I.C.A checks for a Gemini API key, initializes the UI mode, loads configuration, starts safety and performance systems, configures workflows, initializes local analysis and retrieval, verifies memory integrity, and then starts the live assistant runtime. Action modules, tool declarations, resource monitoring, and UI server work are lazily loaded where possible.

If PyQt WebEngine cannot initialize and you want to allow browser fallback, set:

```powershell
$env:MICA_ALLOW_BROWSER_FALLBACK="1"
```

## Studio and Solo Workspace

M.I.C.A Studio is the local workspace surface exposed through `UI/` and `ui_bridge.py`. Solo mode prepares the platform features for a private, single-user setup:

- private local agents and personal ACLs
- local knowledge sources, sync, hybrid search, and document ingestion
- workflow builder/debugger primitives
- sandbox execution and artifact rendering
- local publishing links for app, embed, REST, and MCP access
- browser/mobile companion pairing
- marketplace and OpenAPI/MCP tool management paths
- a 20-point readiness audit

See `docs/SOLO_WORKSPACE.md` for the Studio buttons, expected good state, and the programmatic `core.platform_hub` quickstart/audit flow.

## Frontend Workspace

The `UI/` directory contains the React/Vite frontend.

```powershell
cd UI
npm install
npm run dev
```

Build the frontend:

```powershell
npm run build
```

The frontend uses React, Vite, TypeScript, Radix UI, Material UI icons, Recharts, Tailwind CSS, and local API helpers in `UI/src/app/lib/api.ts`.

## Tests and Quality

Run the main test suite:

```powershell
pytest
```

Run with coverage:

```powershell
pytest --cov=. --cov-report=term-missing
```

Useful focused commands:

```powershell
pytest tests/test_healthcheck.py
pytest tests/test_model_routing.py
pytest tests/test_platform_hub.py
pytest tests/test_local_first_model_policy.py
pytest tests/integration
pytest tests/benchmarks
```

The project includes configuration for pytest, Black, isort, mypy, Bandit, and pre-commit. Some integration and benchmark tests require external services, credentials, browsers, or local runtime data.

## Deployment Notes

Local-first file storage is the default development path. Platform-style persistence can use Postgres, Redis, and S3-compatible storage when configured through environment variables and deployment assets:

- `docker-compose.yml`
- `Dockerfile`
- `deploy/postgres/migrations/`
- `deploy/helm/mica/`

Use these paths when validating publishing, artifact storage, platform state, or deployment readiness outside the simple local file-store mode.

## Documentation

- `docs/Architecture.md` - architecture and component overview
- `docs/API.md` - API and integration surfaces
- `docs/SOLO_WORKSPACE.md` - single-user Studio workspace, quickstart, and audit
- `docs/SELF_DEV_AND_DAILY_MODES.md` - self-development and daily-mode features
- `docs/Troubleshooting.md` - common runtime issues
- `docs/GMAIL_SETUP.md` - Gmail setup
- `docs/OBSIDIAN_SETUP.md` - Obsidian setup
- `docs/Performance-Guide.md` - performance features and tuning
- `PERFORMANCE_FEATURES_ANLEITUNG.md` - German performance feature guide

## Local Data and Secrets

Do not commit `.env`, local credentials, tokens, logs, caches, virtual environments, coverage output, generated runtime data, or private local stores. The repository includes `.gitignore` entries for common local artifacts, but review changes before committing because M.I.C.A touches many local integrations and data directories.

## License

This project is licensed under the MIT License. See `LICENSE`.


Compatibility note: existing legacy JARVIS_* environment variables are still read as fallbacks while new MICA_* names take precedence.