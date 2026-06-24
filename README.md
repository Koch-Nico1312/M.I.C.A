# JARVIS

JARVIS is a local-first desktop AI assistant for Windows-oriented personal automation. It combines voice interaction, Gemini model calls, tool execution, memory, safety approvals, optional retrieval, and a PyQt-based desktop UI. The repository also contains a React/Vite UI workspace under `UI/` for the frontend assets used by the assistant experience.

The project is designed as a modular assistant runtime: `main.py` starts the app, `tools/` declares what the model can call, `actions/` implements those tools, and `core/` provides shared services such as configuration, logging, approvals, memory, monitoring, plugins, sessions, and workflow execution.

## Features

- Voice-capable assistant loop using Gemini live/audio models.
- Tool calling for browser control, desktop automation, files, weather, reminders, messaging, YouTube, Spotify, Gmail, Google Calendar, and more.
- Safety and approval flow for medium- and high-risk actions.
- Persistent action history, session state, long-term memory, backups, and optional Obsidian integration.
- Optional semantic search/RAG with ChromaDB and sentence-transformers.
- Optional passive vision, screen processing, OCR, and HUD overlay features.
- Optional local LLM fallback through Ollama.
- Performance monitoring, health checks, cache support, and feature flags.
- React/Vite UI workspace in `UI/` plus PyQt/PyQt WebEngine runtime dependencies.

## Repository Layout

```text
.
|-- actions/          # Concrete action implementations called by tools
|-- agent/            # Planner, executor, task queue, and orchestration helpers
|-- config/           # Config loaders, startup config, MCP server config
|-- core/             # Runtime services: memory, safety, plugins, health, UI bridge, etc.
|-- data/             # Local runtime data such as history and vector DB files
|-- docs/             # Architecture, API, setup, troubleshooting, and integration docs
|-- memory/           # Memory managers, backups, retrieval, Obsidian bridge
|-- plugins/          # Local plugin directory
|-- startup/          # Application, safety, and performance initialization
|-- tests/            # Unit, integration, and benchmark tests
|-- tools/            # Gemini tool declarations
|-- UI/               # React/Vite frontend workspace
|-- main.py           # Main runtime entry point
|-- ui_bridge.py      # PyQt UI bridge and app surface
|-- config.yaml       # Main YAML configuration
`-- .env.example      # Environment variable template
```

## Requirements

- Python 3.11+
- A Gemini API key in `GEMINI_API_KEY`
- Windows is the primary target for desktop automation features
- Optional microphone and speakers for voice interaction
- Optional Node.js/npm for working on the `UI/` frontend
- Optional Ollama for local model fallback
- Optional Playwright browsers for browser automation

Some integrations require additional credentials or local setup, for example Gmail, Google Calendar, Spotify, Telegram, Discord, VS Code, Obsidian, OCR tools, or smart-home services.

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

Install Playwright browsers if you want browser automation:

```powershell
python -m playwright install
```

Create your local environment file:

```powershell
copy .env.example .env
```

Then set at least:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

You can also run the helper setup script, which installs requirements, Playwright browsers, and pre-commit hooks:

```powershell
python setup.py
```

## Configuration

JARVIS reads configuration from `config.yaml` and environment variables. Environment variables are useful for secrets and local overrides, while `config.yaml` contains the broader runtime defaults.

Common settings include:

- `GEMINI_API_KEY`
- `LIVE_MODEL`, `TEXT_MODEL`, `VISION_MODEL`
- `OLLAMA_ENABLED`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- `PASSIVE_VISION_ENABLED`
- `RAG_ENABLED`, `RAG_INDEX_PATH`
- `HUD_ENABLED`
- `PROACTIVE_SUGGESTIONS_ENABLED`
- `GMAIL_ENABLED`, `CALENDAR_ENABLED`
- `SPOTIFY_ENABLED`
- `OBSIDIAN_ENABLED`, `OBSIDIAN_VAULT_PATH`
- `PERMISSION_PROFILE`, `DISABLED_ACTIONS`

See `.env.example` and `config.yaml` for the current list of supported options.

## Running JARVIS

Start the desktop assistant:

```powershell
.\venv\Scripts\python.exe .\main.py
```

Run in CLI mode:

```powershell
.\venv\Scripts\python.exe .\main.py --cli
```

The startup flow checks configuration, initializes safety and performance systems, starts the UI when enabled, and then launches the assistant runtime.

## Frontend Workspace

The `UI/` directory contains the React/Vite workspace.

```powershell
cd UI
npm install
npm run dev
```

Build the frontend:

```powershell
npm run build
```

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
pytest tests/integration
pytest tests/benchmarks
```

The project includes configuration for pytest, Black, isort, mypy, Bandit, and pre-commit.

## Documentation

- `docs/Architecture.md` - architecture and component overview
- `docs/API.md` - API and integration surfaces
- `docs/Troubleshooting.md` - common runtime issues
- `docs/GMAIL_SETUP.md` - Gmail setup
- `docs/OBSIDIAN_SETUP.md` - Obsidian setup
- `docs/Performance-Guide.md` - performance features and tuning
- `PERFORMANCE_FEATURES_ANLEITUNG.md` - German performance feature guide

## Local Data and Secrets

Do not commit `.env`, local credentials, tokens, logs, caches, virtual environments, coverage output, or generated runtime data. The repository includes `.gitignore` entries for common local artifacts, but check changes before committing because this app touches many local integrations.

## License

This project is licensed under the MIT License. See `LICENSE`.
