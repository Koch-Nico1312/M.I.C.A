# Release Flow

This project ships as a local-first desktop assistant. The release flow keeps
runtime code, configuration templates, documentation, and the built React UI in
one archive.

## Versioning

- Use semantic versions: `MAJOR.MINOR.PATCH`.
- Update `CHANGELOG.md` before building a release.
- Keep secrets out of releases. `config/api_keys.json`, `.env`, and credential
  files are ignored by git and are not included by the release script.

## Build

Build the UI first:

```powershell
cd UI
.\node_modules\.bin\vite.cmd build
cd ..
```

Run the focused verification suite:

```powershell
uv run pytest tests/test_model_routing.py tests/test_config_setup.py tests/test_tool_executor_runtime.py --tb=short --no-cov
```

Create a release archive:

```powershell
uv run python scripts/build_release.py --version 0.4.0 --clean
```

The archive and manifest are written to `dist/`.

## Release Checklist

- Tests pass.
- UI build passes.
- `CHANGELOG.md` has a dated entry.
- `config/api_keys.example.json` is present and contains no real secrets.
- `dist/jarvis-<version>.manifest.json` has a SHA-256 checksum.
