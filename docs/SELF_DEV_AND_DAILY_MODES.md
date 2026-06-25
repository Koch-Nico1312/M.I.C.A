# Self-Dev and Daily Modes

This document covers the controlled offline self-development workflow and daily-driver modes.

## Daily Modes

Use the `daily_mode` action:

```json
{"action": "list"}
```

```json
{"action": "apply", "mode": "offline"}
```

Available modes:

- `safe`: read-mostly operation, destructive actions disabled, confirmations enabled.
- `work`: calendar/RAG/proactive subtle mode for daily productivity.
- `focus`: fewer background interruptions and no passive vision.
- `offline`: prefers local Ollama routing and disables cross-device pushes.
- `admin`: broader permissions, while high-risk confirmations remain enabled.

## Self-Dev Agent

Use the `self_dev_agent` action for repository self-improvement work. It never merges automatically.

Actions:

- `status`: report branch, dirty files, and diff stat.
- `branch`: create or confirm a `codex/*` development branch.
- `plan`: create a conservative implementation checklist.
- `test`: run a test command, defaulting to `pytest -q`.
- `review`: summarize the current diff and optional model review.
- `patch`: validate and apply a provided unified diff with `git apply --check`, then run tests.
- `cycle`: create/check branch, run tests, review diff, and write a merge readiness report.

Reports are written to `data/self_dev_runs/`.

## Offline Model Profiles

`config.yaml` defines `local_code` and `local_review` Ollama-backed model profiles. They become useful when:

```yaml
ollama:
  enabled: true
model_router:
  preferred_profile: "local_code"
```

The `offline` daily mode applies that preference automatically.

## Safety Model

Self-development is intentionally gated:

- no automatic merge
- no automatic push
- branch-first workflow
- unified diff validation before patching
- test command after patching
- action-history record for self-dev runs
- file snapshots for local file write/move/copy/rename/delete operations
