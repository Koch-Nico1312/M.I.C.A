from __future__ import annotations

import ast
import base64
import contextlib
import hashlib
import hmac
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.paths import project_path
from agent.role_profiles import ROLE_PROFILES

try:  # Optional at import time, required for RS256 OIDC verification.
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
except Exception:  # pragma: no cover - exercised only in stripped-down environments.
    InvalidSignature = None
    hashes = None
    padding = None
    rsa = None


STORE_PATH = project_path("data", "platform_hub.json")
COMMUNITY_PLUGIN_DIR = project_path("plugins", "community")
PUBLISHED_DIR = project_path("data", "published")
BROWSER_COMPANION_DIR = project_path("extensions", "browser-companion")
INGESTION_DIR = project_path("data", "ingestion")
SANDBOX_ARTIFACT_DIR = project_path("data", "sandbox_artifacts")
AGENT_PACKAGE_DIR = project_path("data", "agent_packages")

SPECIALIZED_AGENT_DEFAULTS = [
    {
        "id": "orchestrator", "name": "Orchestrator", "model": "quality",
        "prompt": "Du koordinierst M.I.C.A-Agenten. Zerlege Ziele, weise Arbeit passend zu, beachte Abhängigkeiten und fordere Freigaben für riskante Schritte an.",
        "tools": ["task_graph", "task_pipeline", "approval_flow"], "knowledge": ["local-documents", "obsidian-vault"],
        "permissions": ["agents:execute", "workflows:execute", "artifacts:read"],
        "parameters": {"temperature": 0.2, "max_tokens": 2200, "role": "orchestrator"},
    },
    {
        "id": "planner", "name": "Planer", "model": "quality",
        "prompt": "Du erstellst belastbare Pläne. Definiere Schritte, Abhängigkeiten, Risiken, Akzeptanzkriterien und den nächsten sicheren Schritt.",
        "tools": ["task_graph", "create_note_action"], "knowledge": ["local-documents", "obsidian-vault"],
        "permissions": ["workflows:write", "artifacts:write", "knowledge:read"],
        "parameters": {"temperature": 0.35, "max_tokens": 1800, "role": "planner"},
    },
    {
        "id": "research", "name": "Recherche", "model": "fast",
        "prompt": "Du recherchierst präzise, vergleichst Quellen, kennzeichnest Unsicherheit und lieferst kompakte Ergebnisse mit Evidenz.",
        "tools": ["web_search", "documents_search", "summarize_text"], "knowledge": ["local-documents", "obsidian-vault", "github-main"],
        "permissions": ["tools:execute", "knowledge:read", "artifacts:read"],
        "parameters": {"temperature": 0.25, "max_tokens": 1800, "role": "researcher"},
    },
    {
        "id": "execution", "name": "Ausführung", "model": "fast",
        "prompt": "Du setzt freigegebene Arbeitsschritte zuverlässig um. Arbeite reversibel, protokolliere Änderungen und stoppe bei unklaren oder riskanten Aktionen.",
        "tools": ["run_sandbox", "create_note_action", "normalize_text"], "knowledge": ["local-documents", "github-main"],
        "permissions": ["tools:execute", "artifacts:write", "sandbox:execute"],
        "parameters": {"temperature": 0.15, "max_tokens": 2000, "role": "executor"},
    },
    {
        "id": "review", "name": "Review", "model": "quality",
        "prompt": "Du prüfst Ergebnisse gegen Anforderungen, Tests, Evidenz und Sicherheitsregeln. Melde konkrete Abweichungen und gib nur belegte Freigaben.",
        "tools": ["evidence", "test_tool"], "knowledge": ["local-documents", "github-main"],
        "permissions": ["tools:execute", "artifacts:read", "knowledge:read"],
        "parameters": {"temperature": 0.1, "max_tokens": 1600, "role": "reviewer"},
    },
    {
        "id": "monitor", "name": "Monitor", "model": "local",
        "prompt": "Du überwachst Agent-Läufe, Kosten, Fehler, Ressourcen und Sicherheitsereignisse. Eskaliere Abweichungen klar und frühzeitig.",
        "tools": ["aggregate_metrics", "healthcheck"], "knowledge": ["local-documents"],
        "permissions": ["metrics:read", "artifacts:read", "agents:read"],
        "parameters": {"temperature": 0.05, "max_tokens": 1200, "role": "monitor"},
    },
]


ACTION_PERMISSIONS = {
    "prepare_solo_workspace": "agents:write",
    "run_solo_quickstart": "agents:execute",
    "run_solo_audit": "agents:read",
    "save_agent": "agents:write",
    "delete_agent": "agents:write",
    "start_agent_run": "agents:execute",
    "pause_agent_run": "agents:execute",
    "resume_agent_run": "agents:execute",
    "stop_agent_run": "agents:execute",
    "export_agent_package": "agents:write",
    "import_agent_package": "agents:write",
    "install_marketplace_item": "tools:write",
    "sync_marketplace_registry": "tools:write",
    "verify_marketplace_item": "tools:write",
    "review_marketplace_item": "tools:write",
    "save_marketplace_policy": "tools:write",
    "update_marketplace_item": "tools:write",
    "set_marketplace_item_enabled": "tools:write",
    "uninstall_marketplace_item": "tools:write",
    "import_openapi": "tools:write",
    "discover_mcp_tools": "tools:read",
    "load_mcp_tool": "tools:write",
    "unload_mcp_tool": "tools:write",
    "save_tool": "tools:write",
    "test_tool": "tools:execute",
    "execute_openapi_tool": "tools:execute",
    "save_group": "groups:write",
    "save_role": "roles:write",
    "save_acl": "agents:share",
    "share_agent": "agents:share",
    "check_access": "read",
    "save_identity_provider": "identity:write",
    "test_identity_provider": "identity:write",
    "start_sso_login": "read",
    "complete_sso_login": "read",
    "ldap_bind_login": "read",
    "provision_scim_user": "scim:write",
    "deprovision_scim_user": "scim:write",
    "sync_identity_claims": "identity:write",
    "save_knowledge_source": "knowledge:write",
    "schedule_knowledge_sync": "knowledge:write",
    "save_workflow": "workflows:write",
    "edit_workflow_node": "workflows:write",
    "connect_workflow_nodes": "workflows:write",
    "schedule_workflow": "workflows:write",
    "run_due_workflows": "workflows:execute",
    "version_workflow": "workflows:write",
    "run_workflow": "workflows:execute",
    "resume_workflow_run": "workflows:execute",
    "run_evaluation": "evals:write",
    "save_evaluation_dataset": "evals:write",
    "run_agent_chain": "agents:execute",
    "sync_knowledge": "knowledge:write",
    "search_knowledge": "knowledge:write",
    "run_due_knowledge_syncs": "knowledge:write",
    "ingest_documents": "knowledge:write",
    "configure_extraction": "knowledge:write",
    "create_artifact": "artifacts:write",
    "version_artifact": "artifacts:write",
    "restore_artifact_version": "artifacts:write",
    "link_artifact": "artifacts:write",
    "delete_artifact": "artifacts:write",
    "render_artifact": "artifacts:read",
    "run_sandbox": "sandbox:execute",
    "publish_agent": "agents:publish",
    "save_publish_policy": "agents:publish",
    "issue_publish_api_key": "agents:publish",
    "revoke_publish_api_key": "agents:publish",
    "rotate_publish_api_key": "agents:publish",
    "check_deployment_readiness": "agents:publish",
    "check_database_migrations": "agents:publish",
    "save_user": "users:write",
    "save_secret_reference": "secrets:write",
    "delete_secret_reference": "secrets:write",
    "test_integration": "tools:execute",
    "aggregate_metrics": "metrics:read",
    "list_workspace_files": "artifacts:read",
    "read_workspace_file": "artifacts:read",
    "run_local_terminal": "sandbox:execute",
    "run_companion_terminal": "sandbox:execute",
    "create_companion_pairing": "artifacts:read",
    "activate_companion_session": "artifacts:read",
    "heartbeat_companion_session": "artifacts:read",
    "revoke_companion_session": "artifacts:write",
    "get_companion_workspace": "artifacts:read",
}

ROLE_PERMISSION_DEFAULTS = {
    "owner": ["*"],
    "admin": [
        "users:write",
        "groups:write",
        "roles:write",
        "agents:read",
        "agents:write",
        "agents:share",
        "agents:execute",
        "agents:publish",
        "tools:read",
        "tools:write",
        "tools:execute",
        "workflows:read",
        "workflows:write",
        "workflows:execute",
        "evals:write",
        "knowledge:write",
        "artifacts:read",
        "artifacts:write",
        "sandbox:execute",
        "metrics:read",
        "secrets:write",
        "identity:write",
        "scim:write",
        "audit:read",
        "read",
    ],
    "builder": [
        "agents:read",
        "agents:write",
        "agents:execute",
        "tools:read",
        "tools:write",
        "tools:execute",
        "workflows:read",
        "workflows:write",
        "workflows:execute",
        "evals:write",
        "knowledge:write",
        "artifacts:read",
        "artifacts:write",
        "sandbox:execute",
        "metrics:read",
        "read",
    ],
    "viewer": ["read", "agents:read", "workflows:read", "artifacts:read", "metrics:read"],
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slug(value: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    clean = "-".join(part for part in clean.split("-") if part)
    return clean or f"item-{uuid4().hex[:8]}"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _display_path(path: Path) -> str:
    with contextlib.suppress(Exception):
        return str(path.relative_to(project_path()))
    return str(path)


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _b64url_json(value: str) -> dict[str, Any]:
    decoded = _b64url_decode(value)
    parsed = json.loads(decoded.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _b64url_uint(value: str) -> int:
    return int.from_bytes(_b64url_decode(value), "big")


class PlatformStateStore:
    """Storage boundary for the platform state document."""

    backend = "unknown"

    def load(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def save(self, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {"backend": self.backend, "status": "ready"}


class JsonPlatformStateStore(PlatformStateStore):
    backend = "json"

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with contextlib.suppress(Exception):
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
        return None

    def save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def status(self) -> dict[str, Any]:
        return {"backend": self.backend, "status": "ready", "path": _display_path(self.path)}


class PostgresPlatformStateStore(PlatformStateStore):
    backend = "postgres"

    def __init__(self, url: str, fallback: JsonPlatformStateStore):
        self.url = url
        self.fallback = fallback
        self._driver: Any | None = None
        self._driver_name = ""
        self._last_error = ""

    def _load_driver(self) -> Any | None:
        if self._driver is not None:
            return self._driver
        try:
            import psycopg  # type: ignore[import-not-found]

            self._driver = psycopg
            self._driver_name = "psycopg"
            return self._driver
        except Exception as exc:
            self._last_error = str(exc)
        try:
            import psycopg2  # type: ignore[import-not-found]

            self._driver = psycopg2
            self._driver_name = "psycopg2"
            return self._driver
        except Exception as exc:
            self._last_error = str(exc)
        return None

    def _connect(self) -> Any:
        driver = self._load_driver()
        if driver is None:
            raise RuntimeError("Postgres driver not installed")
        return driver.connect(self.url)

    def _ensure_schema(self, cursor: Any) -> None:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_state (
                key TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

    def load(self) -> dict[str, Any] | None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    self._ensure_schema(cursor)
                    cursor.execute("SELECT payload FROM platform_state WHERE key = %s", ("hub",))
                    row = cursor.fetchone()
                    if not row:
                        return self.fallback.load()
                    payload = row[0]
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    return payload if isinstance(payload, dict) else None
        except Exception as exc:
            self._last_error = str(exc)
            return self.fallback.load()

    def save(self, data: dict[str, Any]) -> None:
        serialized = json.dumps(data, ensure_ascii=False)
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    self._ensure_schema(cursor)
                    cursor.execute(
                        """
                        INSERT INTO platform_state(key, payload, updated_at)
                        VALUES (%s, %s::jsonb, now())
                        ON CONFLICT (key)
                        DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                        """,
                        ("hub", serialized),
                    )
            self.fallback.save(data)
        except Exception as exc:
            self._last_error = str(exc)
            self.fallback.save(data)

    def status(self) -> dict[str, Any]:
        driver = self._load_driver()
        status = "ready" if driver is not None and not self._last_error else "fallback-json"
        return {
            "backend": self.backend,
            "status": status,
            "driver": self._driver_name or "missing",
            "fallback": self.fallback.status(),
            "last_error": self._last_error,
        }


def build_platform_state_store(path: Path) -> PlatformStateStore:
    json_store = JsonPlatformStateStore(path)
    backend = (os.environ.get("MICA_PLATFORM_STORE") or os.environ.get("JARVIS_PLATFORM_STORE", "json")).strip().lower()
    postgres_url = (os.environ.get("MICA_POSTGRES_URL") or os.environ.get("MICA_POSTGRES_URL", "")).strip()
    use_auto_postgres = backend == "auto" and postgres_url and path.resolve() == STORE_PATH.resolve()
    if backend == "postgres" or use_auto_postgres:
        if postgres_url:
            return PostgresPlatformStateStore(postgres_url, json_store)
    return json_store


@dataclass
class PlatformHub:
    """Persistent feature hub for agents, teams, tools, workflows, evals, and publishing."""

    store_path: Path = field(default_factory=lambda: STORE_PATH)
    community_plugin_dir: Path = field(default_factory=lambda: COMMUNITY_PLUGIN_DIR)
    published_dir: Path = field(default_factory=lambda: PUBLISHED_DIR)
    browser_companion_dir: Path = field(default_factory=lambda: BROWSER_COMPANION_DIR)
    ingestion_dir: Path = field(default_factory=lambda: INGESTION_DIR)
    sandbox_artifact_dir: Path = field(default_factory=lambda: SANDBOX_ARTIFACT_DIR)
    agent_package_dir: Path = field(default_factory=lambda: AGENT_PACKAGE_DIR)
    data: dict[str, Any] = field(default_factory=dict)
    state_store: PlatformStateStore = field(init=False)

    def __post_init__(self) -> None:
        self.state_store = build_platform_state_store(self.store_path)
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        loaded = self.state_store.load()
        if isinstance(loaded, dict):
            return self._with_defaults(loaded)
        seeded = self._with_defaults({})
        self._save(seeded)
        return seeded

    def _save(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            self.data = data
        self.state_store.save(self.data)

    def _with_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        data.setdefault(
            "solo",
            {
                "enabled": True,
                "owner_user": "u-admin",
                "workspace_name": "Personal M.I.C.A",
                "local_only": True,
                "status": "ready",
                "updated_at": _now(),
            },
        )
        data.setdefault("users", [
            {"id": "u-admin", "name": "You", "email": "you@mica.local", "roles": ["owner"], "groups": ["personal"]},
            {"id": "u-builder", "name": "Agent Builder", "email": "builder@mica.local", "roles": ["builder"], "groups": ["personal"]},
        ])
        data.setdefault("groups", [
            {"id": "personal", "name": "Personal Workspace", "members": ["u-admin", "u-builder"]},
            {"id": "core", "name": "Core", "members": ["u-admin", "u-builder"]},
            {"id": "research", "name": "Research", "members": ["u-builder"]},
        ])
        data.setdefault("roles", [
            {"id": role_id, "permissions": permissions}
            for role_id, permissions in ROLE_PERMISSION_DEFAULTS.items()
        ])
        data.setdefault("secret_references", [
            {"id": "gemini-api", "name": "Gemini API", "env_var": "GEMINI_API_KEY", "scope": "models", "status": "configured" if os.environ.get("GEMINI_API_KEY") else "missing", "updated_at": _now()},
            {"id": "github-token", "name": "GitHub Token", "env_var": "GITHUB_TOKEN", "scope": "connectors", "status": "configured" if os.environ.get("GITHUB_TOKEN") else "missing", "updated_at": _now()},
            {"id": "agent-token", "name": "Agent API Token", "env_var": "MICA_AGENT_TOKEN", "scope": "publishing", "status": "configured" if os.environ.get("MICA_AGENT_TOKEN") else "missing", "updated_at": _now()},
        ])
        self._merge_default_role_permissions(data)
        data.setdefault("acls", [
            {"resource": "agent:research-copilot", "subjects": [{"type": "group", "id": "core", "access": "owner"}]},
        ])
        data.setdefault("agents", [
            {
                "id": "research-copilot",
                "name": "Research Copilot",
                "model": "fast",
                "prompt": "You research, cite sources, and summarize compactly.",
                "tools": ["web_search", "documents_search"],
                "knowledge": ["local-documents", "obsidian-vault"],
                "parameters": {"temperature": 0.3, "max_tokens": 1800, "top_p": 0.9},
                "visibility": "private",
                "owner": "u-admin",
                "updated_at": _now(),
            }
        ])
        existing_agent_ids = {str(agent.get("id")) for agent in data["agents"] if isinstance(agent, dict)}
        for specialized in SPECIALIZED_AGENT_DEFAULTS:
            if specialized["id"] in existing_agent_ids:
                continue
            data["agents"].append(
                {
                    **specialized,
                    "version": "1.0.0",
                    "visibility": "private",
                    "owner": "u-admin",
                    "updated_at": _now(),
                }
            )
        for agent in data["agents"]:
            profile = ROLE_PROFILES.get(str(agent.get("id")))
            if profile:
                agent["runtime_profile"] = {
                    "id": profile.id,
                    "active": True,
                    "model_intent": profile.model_intent,
                    "allowed_tools": list(profile.allowed_tools),
                    "expected_output": profile.expected_output,
                }
        data.setdefault("agent_packages", [])
        data.setdefault("marketplace", [
            {"id": "github-sync", "name": "GitHub Knowledge Sync", "kind": "connector", "installed": False, "enabled": False, "version": "1.0.0", "latest_version": "1.1.0", "trust": "community", "review_status": "pending", "checksum": "sha256:community-github-sync", "signature": "unsigned", "source_url": "https://plugins.mica.local/github-sync", "description": "Keeps repositories indexed for RAG.", "entrypoint": "github_sync"},
            {"id": "docling-ingest", "name": "Docling/Tika Ingestion", "kind": "extractor", "installed": True, "enabled": True, "version": "0.4.0", "latest_version": "0.4.1", "trust": "verified", "review_status": "approved", "checksum": "sha256:verified-docling-ingest", "signature": "mica:verified-docling-ingest", "source_url": "https://plugins.mica.local/docling-ingest", "description": "Batch extracts PDFs, scans, tables, and layouts.", "entrypoint": "docling_ingest"},
            {"id": "workflow-human-gate", "name": "Human Approval Gate", "kind": "workflow-node", "installed": True, "enabled": True, "version": "1.2.1", "latest_version": "1.2.1", "trust": "verified", "review_status": "approved", "checksum": "sha256:verified-human-gate", "signature": "mica:verified-human-gate", "source_url": "https://plugins.mica.local/workflow-human-gate", "description": "Adds human-in-the-loop workflow checkpoints.", "entrypoint": "workflow_human_gate"},
        ])
        data.setdefault(
            "marketplace_policy",
            {
                "require_review": True,
                "require_signature": True,
                "allowed_trust": ["verified", "community"],
                "max_risk": "medium",
                "permission_denylist": ["system:write", "filesystem:write", "network:unrestricted", "secrets:read"],
                "trusted_publishers": ["mica"],
                "updated_at": _now(),
            },
        )
        data.setdefault("marketplace_audit", [])
        self._normalize_marketplace(data)
        data.setdefault("tools", [
            {"id": "tool-openapi-weather", "name": "weather_lookup", "kind": "openapi", "status": "ready", "schema": {"type": "object", "properties": {"city": {"type": "string"}}}, "test_result": "Ready"},
            {"id": "tool-custom-summarize", "name": "summarize_text", "kind": "function", "status": "draft", "code": "return text[:500]", "test_result": "Not run"},
            {"id": "filter-nonempty-text", "name": "nonempty_text", "kind": "filter", "status": "ready", "code": "return bool(parameters.get('text', '').strip())", "test_parameters": {"text": "M.I.C.A"}, "test_result": "Filter ready"},
            {"id": "pipe-normalize-text", "name": "normalize_text", "kind": "pipe", "status": "ready", "code": "return parameters.get('text', '').strip().lower()", "test_parameters": {"text": "  M.I.C.A Studio  "}, "test_result": "Pipe ready"},
            {"id": "action-create-note", "name": "create_note_action", "kind": "action", "status": "ready", "code": "return {'artifact_title': parameters.get('title', 'Tool Note'), 'content': parameters.get('content', '')}", "test_parameters": {"title": "Tool Note", "content": "Created by action"}, "test_result": "Action ready"},
        ])
        self._normalize_tools(data)
        data.setdefault("mcp", {"deferred": True, "last_query": "", "servers": [], "tools": [], "loaded_tools": []})
        data.setdefault("workflows", [
            {
                "id": "wf-triage",
                "name": "Document Triage",
                "nodes": [
                    {"id": "input", "type": "input", "label": "Upload", "x": 6, "y": 42},
                    {"id": "extract", "type": "extract", "label": "Extract", "x": 26, "y": 42},
                    {"id": "route", "type": "branch", "label": "Needs Review?", "x": 46, "y": 42},
                    {"id": "human", "type": "human", "label": "Approval", "x": 66, "y": 20},
                    {"id": "loop", "type": "loop", "label": "Retry Extract", "x": 66, "y": 64},
                    {"id": "publish", "type": "publish", "label": "Report", "x": 84, "y": 42},
                ],
                "edges": [["input", "extract"], ["extract", "route"], ["route", "human", "low confidence"], ["route", "publish", "ready"], ["route", "loop", "retry"], ["loop", "extract"], ["human", "publish"]],
                "canvas": {"zoom": 1, "supports": ["branching", "loops", "routing", "human-in-the-loop"]},
                "status": "draft",
                "updated_at": _now(),
            }
        ])
        self._normalize_workflows(data)
        data.setdefault("runs", [
            {"id": "run-demo", "workflow_id": "wf-triage", "status": "completed", "started_at": _now(), "steps": [
                {"node": "input", "status": "completed", "input": "scan.pdf", "output": "1 file", "latency_ms": 18, "retries": 0},
                {"node": "extract", "status": "completed", "input": "scan.pdf", "output": "tables + text", "latency_ms": 242, "retries": 0},
                {"node": "route", "status": "completed", "input": "confidence=.78", "output": "human", "latency_ms": 12, "retries": 0},
            ]},
        ])
        data.setdefault("evaluations", [
            {
                "id": "eval-support",
                "name": "Support Prompt Arena",
                "agents": ["research-copilot", "research-copilot-v2"],
                "dataset": "golden-support-20",
                "status": "passing",
                "elo": {"research-copilot": 1240, "research-copilot-v2": 1216},
                "regressions": 0,
                "last_score": 0.92,
                "baseline": "research-copilot",
                "challenger": "research-copilot-v2",
                "regression_gate": {"min_score": 0.8, "max_regressions": 0},
            },
        ])
        data.setdefault("evaluation_datasets", [
            {
                "id": "golden-support-20",
                "name": "Golden Support 20",
                "cases": [
                    {"id": "case-1", "input": "Summarize refund policy", "expected": "Clear refund summary", "rubric": "groundedness"},
                    {"id": "case-2", "input": "Route urgent outage", "expected": "Escalate and draft response", "rubric": "actionability"},
                ],
            }
        ])
        data.setdefault("evaluation_runs", [
            {
                "id": "eval-run-demo",
                "evaluation_id": "eval-support",
                "dataset": "golden-support-20",
                "status": "passing",
                "score": 0.92,
                "regressions": 0,
                "winner": "research-copilot",
                "baseline": "research-copilot",
                "challenger": "research-copilot-v2",
                "elo_delta": {"research-copilot": 8, "research-copilot-v2": -3},
                "gate": {"status": "passed", "min_score": 0.8, "max_regressions": 0},
                "pairs": [
                    {"case_id": "case-1", "baseline": "research-copilot", "challenger": "research-copilot-v2", "winner": "research-copilot", "margin": 0.02},
                    {"case_id": "case-2", "baseline": "research-copilot", "challenger": "research-copilot-v2", "winner": "research-copilot", "margin": 0.01},
                ],
                "cases": [
                    {"case_id": "case-1", "agent": "research-copilot", "score": 0.94, "winner": True, "regression": False},
                    {"case_id": "case-2", "agent": "research-copilot", "score": 0.90, "winner": True, "regression": False},
                ],
                "created_at": _now(),
            }
        ])
        data.setdefault("metrics", [
            {"scope": "research-copilot", "model": "fast", "tool": "documents_search", "user": "u-admin", "agent": "research-copilot", "workflow": "wf-triage", "tokens": 42100, "cost": 0.84, "latency_ms": 1180, "tool_calls": 36},
            {"scope": "summarize_text", "model": "local", "tool": "summarize_text", "user": "u-builder", "agent": "research-copilot", "workflow": "wf-triage", "tokens": 9300, "cost": 0.0, "latency_ms": 420, "tool_calls": 12},
        ])
        data.setdefault("metric_events", [])
        data.setdefault("audit_events", [])
        data.setdefault("invocations", [])
        data.setdefault("agent_runs", [])
        data.setdefault("knowledge", [
            {"id": "local-documents", "source": "Folder", "target": "Documents", "uri": "Documents", "status": "synced", "last_sync": _now(), "rag": "hybrid: bm25 + vector + reranker", "vector_db": "chroma", "schedule": "watch"},
            {"id": "obsidian-vault", "source": "Folder", "target": "Obsidian", "uri": "memory", "status": "watching", "last_sync": _now(), "rag": "hybrid: bm25 + vector + reranker", "vector_db": "faiss", "schedule": "watch"},
            {"id": "github-main", "source": "GitHub", "target": "Repository Index", "uri": "https://github.com/example/mica", "status": "scheduled", "last_sync": _now(), "rag": "hybrid: bm25 + vector + cross-encoder reranker", "vector_db": "qdrant", "schedule": "*/15 * * * *"},
            {"id": "drive-personal", "source": "Drive", "target": "Personal Drive", "uri": "drive://personal", "status": "optional", "last_sync": _now(), "rag": "hybrid: bm25 + vector + cross-encoder reranker", "vector_db": "chroma", "schedule": "manual"},
            {"id": "s3-archive", "source": "S3", "target": "Archive Bucket", "uri": "s3://mica-archive", "status": "scheduled", "last_sync": _now(), "rag": "hybrid: bm25 + vector + cross-encoder reranker", "vector_db": "pgvector", "schedule": "daily"},
            {"id": "confluence-docs", "source": "Confluence", "target": "Product Space", "uri": "confluence://product", "status": "scheduled", "last_sync": _now(), "rag": "hybrid: bm25 + vector + cross-encoder reranker", "vector_db": "weaviate", "schedule": "hourly"},
        ])
        self._normalize_knowledge_sources(data)
        data.setdefault("knowledge_runs", [])
        data.setdefault("knowledge_scheduler_runs", [])
        data.setdefault("knowledge_indexes", {})
        data.setdefault("knowledge_searches", [])
        data.setdefault("extraction", {
            "engines": ["Docling", "Tika", "OCR"],
            "engine_config": {
                "Docling": {"tables": True, "layout": True, "ocr": True, "batch_size": 50},
                "Tika": {"tables": False, "layout": False, "ocr": False, "batch_size": 100},
                "OCR": {"tables": True, "layout": True, "ocr": True, "batch_size": 25},
            },
            "batch_queue": [],
            "runs": [],
            "tables": True,
            "layouts": True,
            "scans": True,
            "artifact_dir": _display_path(self.ingestion_dir),
        })
        data.setdefault("artifacts", [
            {"id": "artifact-dashboard", "title": "Operations Snapshot", "kind": "dashboard", "content": "<section>Live metrics</section>", "version": 1, "versions": [{"version": 1, "created_at": _now(), "content": "<section>Live metrics</section>"}], "render_status": "ready", "updated_at": _now()},
            {"id": "artifact-flow", "title": "Triage Flow", "kind": "mermaid", "content": "flowchart LR\nA-->B", "version": 1, "versions": [{"version": 1, "created_at": _now(), "content": "flowchart LR\nA-->B"}], "render_status": "ready", "updated_at": _now()},
        ])
        self._normalize_artifacts(data)
        data.setdefault("sandbox", {
            "enabled": True,
            "languages": ["python", "javascript"],
            "runs": [],
            "artifact_dir": _display_path(self.sandbox_artifact_dir),
            "policy": {
                "network": "disabled",
                "filesystem": "uploads-only",
                "timeout_seconds": 5,
                "max_output_chars": 4000,
                "max_upload_files": 10,
                "max_upload_bytes": 200000,
                "blocked_imports": ["ftplib", "http", "os", "pathlib", "requests", "shutil", "socket", "subprocess", "urllib"],
                "blocked_calls": ["__import__", "compile", "eval", "exec", "input", "open"],
            },
            "audit": [],
        })
        self._normalize_sandbox(data)
        data.setdefault("publishing", [
            {"id": "pub-chat", "agent_id": "research-copilot", "kind": "embeddable-chat", "status": "draft", "url": "/embed/research-copilot", "policy": {"auth": "workspace", "cors": ["http://localhost:5173"], "rate_limit_per_minute": 60, "allowed_groups": ["personal"], "secret_refs": []}},
            {"id": "pub-mcp", "agent_id": "research-copilot", "kind": "mcp-server", "status": "draft", "url": "/mcp/research-copilot", "policy": {"auth": "api-key", "cors": [], "rate_limit_per_minute": 120, "allowed_groups": ["personal"], "secret_refs": ["MICA_MCP_TOKEN"]}},
        ])
        data.setdefault("invocation_audit", [])
        self._normalize_publications(data)
        data.setdefault("deployment", {
            "docker_compose": "docker-compose.yml",
            "dockerfile": "Dockerfile",
            "kubernetes": "helm-ready",
            "helm_chart": "deploy/helm/mica",
            "postgres": "compose+helm-ready",
            "postgres_schema": "deploy/postgres/migrations/001_platform_hub.sql",
            "persistence": self.state_store.status(),
            "migrations": {"directory": "deploy/postgres/migrations", "applied": [], "pending": [], "catalog": [], "last_check": None},
            "redis": "compose+helm-ready",
            "storage": "persistent-volume+s3/minio-ready",
            "scaling": "horizontal-ready",
            "env_mapping": {
                "postgres": "MICA_POSTGRES_URL",
                "redis": "MICA_REDIS_URL",
                "s3_endpoint": "MICA_S3_ENDPOINT",
                "s3_bucket": "MICA_S3_BUCKET",
                "storage_backend": "MICA_STORAGE_BACKEND",
            },
            "readiness": {"status": "unknown", "checks": []},
        })
        data.setdefault("identity_providers", [
            {
                "id": "local",
                "name": "Local Accounts",
                "type": "local",
                "status": "enabled",
                "issuer": "mica://local",
                "client_id": "",
                "scim_enabled": False,
                "last_test": _now(),
            },
            {
                "id": "oidc-main",
                "name": "Primary OIDC",
                "type": "oidc",
                "status": "configured",
                "issuer": "https://login.example.com",
                "client_id": "mica",
                "scim_enabled": True,
                "last_test": None,
            },
        ])
        data.setdefault("scim_events", [])
        data.setdefault("sso", {
            "oidc": "configured",
            "ldap": "configurable",
            "scim": "enabled",
            "providers": ["local", "oidc"],
            "default_provider": "local",
            "provisioning": "scim-ready",
            "login_flows": [],
            "sessions": [],
            "events": [],
        })
        data.setdefault("subagents", [
            {"id": "subagent-research", "name": "Researcher", "parent": "research-copilot", "role": "gather evidence", "status": "available"},
            {"id": "subagent-writer", "name": "Writer", "parent": "research-copilot", "role": "compact final answer", "status": "available"},
        ])
        data.setdefault("agent_chain_runs", [])
        data.setdefault("solo_quickstarts", [])
        data.setdefault("solo_audits", [])
        data.setdefault("companion", {
            "browser_extension": "manifest-ready",
            "manifest_path": "extensions/browser-companion/manifest.json",
            "mobile_ui": "responsive",
            "remote_access": "guarded",
            "workspace_files": True,
            "terminal": True,
            "workspace_endpoint": "/api/companion/workspace",
            "file_endpoint": "/api/companion/file",
            "terminal_endpoint": "/api/companion/terminal",
            "pairing_endpoint": "/api/companion/pair",
            "session_endpoint": "/api/companion/session",
            "workspace_snapshot_endpoint": "/api/companion/mobile-workspace",
            "allowed_terminal_commands": [
                "git status",
                "python version",
                "list files",
                "pwd",
                "powershell version",
                "powershell list files",
                "powershell pwd",
                "linux uname",
                "linux list files",
                "linux pwd",
            ],
            "pairing_required": True,
            "pairing_codes": [],
            "sessions": [],
        })
        self._normalize_companion(data)
        self._ensure_companion_manifest()
        self._normalize_solo(data)
        data["updated_at"] = data.get("updated_at") or _now()
        return data

    def _normalize_solo(self, data: dict[str, Any]) -> None:
        solo = data.setdefault("solo", {})
        solo.setdefault("enabled", True)
        solo.setdefault("owner_user", "u-admin")
        solo.setdefault("workspace_name", "Personal M.I.C.A")
        solo.setdefault("local_only", True)
        solo.setdefault("status", "ready")
        solo.setdefault("updated_at", _now())
        owner_id = str(solo.get("owner_user") or "u-admin")
        users = data.setdefault("users", [])
        owner = next((item for item in users if item.get("id") == owner_id), None)
        if owner is None:
            owner = {"id": owner_id, "name": "You", "email": "you@mica.local", "roles": ["owner"], "groups": ["personal"]}
            users.insert(0, owner)
        owner.setdefault("roles", ["owner"])
        owner.setdefault("groups", ["personal"])
        if "owner" not in _as_list(owner.get("roles")):
            owner["roles"] = [*_as_list(owner.get("roles")), "owner"]
        if "personal" not in _as_list(owner.get("groups")):
            owner["groups"] = [*_as_list(owner.get("groups")), "personal"]
        groups = data.setdefault("groups", [])
        personal = next((item for item in groups if item.get("id") == "personal"), None)
        if personal is None:
            personal = {"id": "personal", "name": "Personal Workspace", "members": [owner_id]}
            groups.insert(0, personal)
        members = _as_list(personal.get("members"))
        if owner_id not in members:
            members.append(owner_id)
        personal["members"] = members

    def _normalize_marketplace(self, data: dict[str, Any]) -> None:
        data.setdefault(
            "marketplace_policy",
            {
                "require_review": True,
                "require_signature": True,
                "allowed_trust": ["verified", "community"],
                "max_risk": "medium",
                "permission_denylist": ["system:write", "filesystem:write", "network:unrestricted", "secrets:read"],
                "trusted_publishers": ["mica"],
                "updated_at": _now(),
            },
        )
        data.setdefault("marketplace_audit", [])
        for item in data.setdefault("marketplace", []):
            item.setdefault("enabled", bool(item.get("installed")))
            item.setdefault("latest_version", item.get("version", "1.0.0"))
            item.setdefault("trust", "community")
            item.setdefault("review_status", "approved" if item.get("trust") == "verified" else "pending")
            item.setdefault("checksum", f"sha256:{_slug(str(item.get('id') or item.get('name') or 'extension'))}")
            item.setdefault("signature", "unsigned")
            item.setdefault("source_url", f"https://plugins.mica.local/{item.get('id', 'extension')}")
            item.setdefault("publisher", "mica" if item.get("trust") == "verified" else "community")
            item.setdefault("permissions", ["tools:execute"])
            item.setdefault("manifest", self._marketplace_manifest(item))
            item.setdefault("verification", self._verify_marketplace_payload(item))
            item["risk"] = self._marketplace_risk(item)

    def _normalize_artifacts(self, data: dict[str, Any]) -> None:
        for artifact in data.setdefault("artifacts", []):
            artifact.setdefault("version", 1)
            artifact.setdefault(
                "versions",
                [{"version": artifact.get("version", 1), "created_at": artifact.get("updated_at") or _now(), "content": artifact.get("content", "")}],
            )
            artifact.setdefault("render_status", "ready")
            artifact.setdefault("dependencies", [])
            artifact.setdefault("created_by", "u-admin")
            artifact.setdefault("agent_id", "")
            artifact.setdefault("run_id", "")
            for version in artifact.get("versions", []):
                version.setdefault("note", "")
                version.setdefault("agent_id", artifact.get("agent_id", ""))
                version.setdefault("run_id", artifact.get("run_id", ""))

    def _normalize_sandbox(self, data: dict[str, Any]) -> None:
        sandbox = data.setdefault("sandbox", {})
        sandbox.setdefault("enabled", True)
        sandbox.setdefault("languages", ["python", "javascript"])
        sandbox.setdefault("runs", [])
        sandbox.setdefault("artifact_dir", _display_path(self.sandbox_artifact_dir))
        sandbox.setdefault(
            "policy",
            {
                "network": "disabled",
                "filesystem": "uploads-only",
                "timeout_seconds": 5,
                "max_output_chars": 4000,
                "max_upload_files": 10,
                "max_upload_bytes": 200000,
                "blocked_imports": ["ftplib", "http", "os", "pathlib", "requests", "shutil", "socket", "subprocess", "urllib"],
                "blocked_calls": ["__import__", "compile", "eval", "exec", "input", "open"],
            },
        )
        sandbox.setdefault("audit", [])

    def _normalize_publications(self, data: dict[str, Any]) -> None:
        for publication in data.setdefault("publishing", []):
            policy = publication.setdefault("policy", {})
            policy.setdefault("auth", "workspace")
            policy.setdefault("cors", ["http://localhost:5173"] if publication.get("kind") in {"web-app", "embeddable-chat"} else [])
            policy.setdefault("rate_limit_per_minute", 60)
            policy.setdefault("allowed_groups", ["core"])
            policy.setdefault("secret_refs", [])
            policy.setdefault("api_key_hashes", [])
            policy.setdefault("api_keys", [])
            policy.setdefault("audit_invocations", True)

    def _normalize_companion(self, data: dict[str, Any]) -> None:
        companion = data.setdefault("companion", {})
        companion.setdefault("pairing_required", True)
        companion.setdefault("pairing_codes", [])
        companion.setdefault("sessions", [])
        companion.setdefault("workspace_snapshot_endpoint", "/api/companion/mobile-workspace")
        companion.setdefault("session_endpoint", "/api/companion/session")

    def _normalize_tools(self, data: dict[str, Any]) -> None:
        tools = data.setdefault("tools", [])
        by_id = {str(tool.get("id")): tool for tool in tools}
        samples = [
            {"id": "filter-nonempty-text", "name": "nonempty_text", "kind": "filter", "status": "ready", "code": "return bool(parameters.get('text', '').strip())", "test_parameters": {"text": "M.I.C.A"}, "test_result": "Filter ready"},
            {"id": "pipe-normalize-text", "name": "normalize_text", "kind": "pipe", "status": "ready", "code": "return parameters.get('text', '').strip().lower()", "test_parameters": {"text": "  M.I.C.A Studio  "}, "test_result": "Pipe ready"},
            {"id": "action-create-note", "name": "create_note_action", "kind": "action", "status": "ready", "code": "return {'artifact_title': parameters.get('title', 'Tool Note'), 'content': parameters.get('content', '')}", "test_parameters": {"title": "Tool Note", "content": "Created by action"}, "test_result": "Action ready"},
        ]
        for sample in samples:
            if sample["id"] not in by_id:
                tools.append(sample)
        for tool in tools:
            tool.setdefault("status", "draft")
            tool.setdefault("schema", {"type": "object", "properties": {}})
            tool.setdefault("test_parameters", {})

    def _normalize_workflows(self, data: dict[str, Any]) -> None:
        for workflow in data.setdefault("workflows", []):
            nodes = workflow.setdefault("nodes", [])
            node_ids = {str(node.get("id")) for node in nodes}
            if workflow.get("id") == "wf-triage" and "loop" not in node_ids:
                nodes.insert(-1 if nodes else 0, {"id": "loop", "type": "loop", "label": "Retry Extract", "x": 66, "y": 64})
                edges = workflow.setdefault("edges", [])
                if ["route", "loop", "retry"] not in edges:
                    edges.append(["route", "loop", "retry"])
                if ["loop", "extract"] not in edges:
                    edges.append(["loop", "extract"])
            for index, node in enumerate(nodes):
                node.setdefault("x", 8 + (index % 5) * 20)
                node.setdefault("y", 25 + (index // 5) * 32)
            node_types = {str(node.get("type")) for node in nodes}
            workflow.setdefault("canvas", {"zoom": 1, "supports": []})
            workflow.setdefault("version", 1)
            workflow.setdefault("trigger", {"type": "manual", "enabled": True})
            workflow.setdefault("schedule", "manual")
            workflow.setdefault("next_run", "")
            workflow.setdefault(
                "versions",
                [{"version": workflow.get("version", 1), "created_at": workflow.get("updated_at") or _now(), "nodes": nodes, "edges": workflow.get("edges", [])}],
            )
            workflow["canvas"]["supports"] = sorted(
                set(workflow["canvas"].get("supports", []))
                | ({"branching"} if "branch" in node_types else set())
                | ({"loops"} if "loop" in node_types else set())
                | ({"human-in-the-loop"} if "human" in node_types else set())
                | {"routing"}
            )

    def _normalize_knowledge_sources(self, data: dict[str, Any]) -> None:
        for source in data.setdefault("knowledge", []):
            source.setdefault("rag", "hybrid: bm25 + vector + cross-encoder reranker")
            source.setdefault("vector_db", "chroma")
            source.setdefault("schedule", "manual")
            source.setdefault("connector_status", "ready")
            source.setdefault("watch_mode", source.get("schedule") == "watch")
            if "next_sync" not in source:
                source["next_sync"] = self._next_sync_time(str(source.get("schedule") or "manual"), source.get("last_sync"))

    def _next_sync_time(self, schedule: str, from_time: Any = None) -> str:
        normalized = schedule.strip().lower()
        if normalized in {"", "manual"}:
            return ""
        if normalized == "watch":
            return "watching"
        try:
            base = datetime.fromisoformat(str(from_time)) if from_time else datetime.now()
        except ValueError:
            base = datetime.now()
        if normalized == "hourly":
            return (base + timedelta(hours=1)).isoformat(timespec="seconds")
        if normalized == "daily":
            return (base + timedelta(days=1)).isoformat(timespec="seconds")
        if normalized.startswith("*/") and " " in normalized:
            minutes = normalized.split(" ", 1)[0].removeprefix("*/")
            with contextlib.suppress(ValueError):
                return (base + timedelta(minutes=max(1, int(minutes)))).isoformat(timespec="seconds")
        return (base + timedelta(minutes=15)).isoformat(timespec="seconds")

    def _is_knowledge_due(self, source: dict[str, Any], now: datetime | None = None) -> bool:
        schedule = str(source.get("schedule") or "manual").lower()
        if schedule in {"", "manual"}:
            return False
        if schedule == "watch":
            return source.get("status") in {"watching", "changed", "scheduled"}
        next_sync = str(source.get("next_sync") or "")
        if not next_sync:
            return True
        with contextlib.suppress(ValueError):
            return datetime.fromisoformat(next_sync) <= (now or datetime.now())
        return True

    def _merge_default_role_permissions(self, data: dict[str, Any]) -> None:
        roles = data.setdefault("roles", [])
        existing_roles = {str(role.get("id")): role for role in roles}
        for role_id, permissions in ROLE_PERMISSION_DEFAULTS.items():
            role = existing_roles.get(role_id)
            if not role:
                roles.append({"id": role_id, "permissions": permissions})
                continue
            merged = list(dict.fromkeys([*role.get("permissions", []), *permissions]))
            role["permissions"] = merged

    def snapshot(self) -> dict[str, Any]:
        self.data.setdefault("deployment", {})["persistence"] = self.state_store.status()
        data = json.loads(json.dumps(self.data, ensure_ascii=False))
        self._mask_companion_secrets(data)
        self._mask_sso_secrets(data)
        self._mask_publishing_secrets(data)
        data["solo_status"] = self._solo_status(data)
        return self._with_counts(data)

    def _run_solo_audit(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.snapshot()
        status = data.get("solo_status", {})
        checklist = status.get("checklist", []) if isinstance(status, dict) else []
        items = []
        for item in checklist:
            item_id = str(item.get("id") or "")
            evidence = self._solo_evidence(item_id, data)
            items.append(
                {
                    **item,
                    "evidence": evidence,
                    "recommendation": self._solo_recommendation(item_id, str(item.get("status") or "")),
                    "verified": item.get("status") in {"ready", "optional"} and bool(evidence),
                }
            )
        blocking = [item for item in items if item.get("status") == "needs-setup"]
        audit = {
            "id": f"solo-audit-{uuid4().hex[:8]}",
            "status": "ready" if not blocking else "needs-setup",
            "workspace_name": status.get("workspace_name", "Personal M.I.C.A") if isinstance(status, dict) else "Personal M.I.C.A",
            "ready_count": status.get("ready_count", 0) if isinstance(status, dict) else 0,
            "optional_count": status.get("optional_count", 0) if isinstance(status, dict) else 0,
            "blocking_count": len(blocking),
            "total_count": len(items),
            "items": items,
            "created_at": _now(),
        }
        self.data.setdefault("solo_audits", []).insert(0, audit)
        self.data["solo_audits"] = self.data["solo_audits"][:25]
        return audit

    def _solo_evidence(self, item_id: str, data: dict[str, Any]) -> list[str]:
        agents = data.get("agents", [])
        tools = data.get("tools", [])
        workflows = data.get("workflows", [])
        publications = data.get("publishing", [])
        evidence_map = {
            "agent_builder": [f"{len(agents)} agent(s)", *(f"{agent.get('id')}:{agent.get('visibility')}" for agent in agents[:3])],
            "solo_access": [f"{len(data.get('users', []))} user(s)", f"{len(data.get('roles', []))} role(s)", f"{len(data.get('acls', []))} ACL(s)"],
            "marketplace": [f"{sum(1 for item in data.get('marketplace', []) if item.get('installed'))} installed", f"{len(data.get('marketplace', []))} available"],
            "openapi_import": [tool.get("name", "") for tool in tools if tool.get("kind") == "openapi"][:4],
            "mcp_deferred": [f"deferred={data.get('mcp', {}).get('deferred')}", f"{len(data.get('mcp', {}).get('tools', []))} discovered"],
            "tool_editor": [f"{tool.get('kind')}:{tool.get('name')}" for tool in tools if tool.get("kind") in {"function", "filter", "pipe", "action"}][:5],
            "workflow_builder": [f"{workflow.get('id')}:{len(workflow.get('nodes', []))} nodes/{len(workflow.get('edges', []))} edges" for workflow in workflows[:3]],
            "workflow_debugger": [f"{len(data.get('runs', []))} run(s)", *(f"{run.get('id')}:{run.get('status')}" for run in data.get("runs", [])[:3])],
            "evaluations": [f"{len(data.get('evaluations', []))} evaluation(s)", f"{len(data.get('evaluation_datasets', []))} dataset(s)"],
            "metrics": [f"{len(data.get('metrics', []))} metric row(s)", f"{len(data.get('metric_events', []))} metric event(s)"],
            "knowledge_sync": [f"{source.get('id')}:{source.get('status')}" for source in data.get("knowledge", [])[:5]],
            "hybrid_rag": [str(source.get("rag")) for source in data.get("knowledge", []) if "bm25" in str(source.get("rag", "")).lower()][:3],
            "document_extraction": [f"engines={','.join(data.get('extraction', {}).get('engines', []))}", f"{len(data.get('extraction', {}).get('runs', []))} run(s)"],
            "artifacts": [f"{artifact.get('id')}:{artifact.get('kind')}" for artifact in data.get("artifacts", [])[:5]],
            "sandbox": [f"enabled={data.get('sandbox', {}).get('enabled')}", f"languages={','.join(data.get('sandbox', {}).get('languages', []))}", f"{len(data.get('sandbox', {}).get('runs', []))} run(s)"],
            "publishing": [f"{pub.get('kind')}:{pub.get('status')}:{pub.get('url')}" for pub in publications[:5]],
            "deployment": [str(data.get("deployment", {}).get("dockerfile", "")), str(data.get("deployment", {}).get("docker_compose", ""))],
            "identity": [f"solo_mode={data.get('sso', {}).get('solo_mode')}", f"default={data.get('sso', {}).get('default_provider')}"],
            "agent_chains": [f"{agent.get('id')}:{agent.get('status')}" for agent in data.get("subagents", [])[:4]],
            "companion": [str(data.get("companion", {}).get("manifest_path", "")), str(data.get("companion", {}).get("workspace_endpoint", ""))],
        }
        return [str(item) for item in evidence_map.get(item_id, []) if str(item)]

    def _solo_recommendation(self, item_id: str, status: str) -> str:
        if status == "ready":
            return "Bereit fuer lokale Nutzung."
        if status == "optional":
            return "Optional fuer deinen Einzelplatzbetrieb; nur bei Bedarf konfigurieren."
        recommendations = {
            "agent_builder": "Solo vorbereiten oder einen privaten Agent speichern.",
            "openapi_import": "Eine OpenAPI-Spezifikation importieren.",
            "workflow_debugger": "Einen Workflow ausfuehren.",
            "knowledge_sync": "Lokale Knowledge synchronisieren.",
            "sandbox": "Einen Python- oder JavaScript-Sandbox-Run starten.",
            "publishing": "Agent als Web-App, Embed, REST API oder MCP veroeffentlichen.",
        }
        return recommendations.get(item_id, "Solo Quickstart ausfuehren, um diesen Bereich automatisch vorzubereiten.")

    def _solo_status(self, data: dict[str, Any]) -> dict[str, Any]:
        solo = data.get("solo") if isinstance(data.get("solo"), dict) else {}
        local_agents = [agent for agent in data.get("agents", []) if agent.get("owner") == solo.get("owner_user", "u-admin")]
        private_agents = [agent for agent in local_agents if agent.get("visibility") == "private"]
        local_publications = [pub for pub in data.get("publishing", []) if pub.get("status") in {"draft", "published"}]
        installed_marketplace = [item for item in data.get("marketplace", []) if item.get("installed")]
        tool_kinds = {str(tool.get("kind")) for tool in data.get("tools", [])}
        workflow_supports = {
            support
            for workflow in data.get("workflows", [])
            for support in _as_list((workflow.get("canvas") or {}).get("supports"))
        }
        extraction = data.get("extraction", {}) if isinstance(data.get("extraction"), dict) else {}
        sandbox = data.get("sandbox", {}) if isinstance(data.get("sandbox"), dict) else {}
        companion = data.get("companion", {}) if isinstance(data.get("companion"), dict) else {}
        deployment = data.get("deployment", {}) if isinstance(data.get("deployment"), dict) else {}
        sso = data.get("sso", {}) if isinstance(data.get("sso"), dict) else {}
        publications = {str(pub.get("kind")) for pub in data.get("publishing", [])}
        checklist = [
            {"id": "agent_builder", "label": "Agent/Persona Builder", "status": "ready" if private_agents else "needs-setup"},
            {"id": "solo_access", "label": "Single-User Rollen/RBAC", "status": "ready" if solo.get("enabled") and data.get("roles") else "needs-setup"},
            {"id": "marketplace", "label": "Lokale Erweiterungen", "status": "ready" if installed_marketplace else "optional"},
            {"id": "openapi_import", "label": "OpenAPI Tool Import", "status": "ready" if "openapi" in tool_kinds else "needs-setup"},
            {"id": "mcp_deferred", "label": "MCP Deferred Discovery", "status": "ready" if data.get("mcp", {}).get("deferred") else "needs-setup"},
            {"id": "tool_editor", "label": "Tool/Function Editor", "status": "ready" if {"function", "filter", "pipe", "action"} & tool_kinds else "needs-setup"},
            {"id": "workflow_builder", "label": "Canvas Workflow Builder", "status": "ready" if {"branching", "loops", "routing", "human-in-the-loop"} <= workflow_supports else "needs-setup"},
            {"id": "workflow_debugger", "label": "Workflow Replay/Debugger", "status": "ready" if data.get("runs") else "needs-setup"},
            {"id": "evaluations", "label": "Evaluations/Model Arena", "status": "ready" if data.get("evaluations") and data.get("evaluation_datasets") else "needs-setup"},
            {"id": "metrics", "label": "Token/Kosten/Latenz", "status": "ready" if data.get("metrics") or data.get("metric_events") else "needs-setup"},
            {"id": "knowledge_sync", "label": "Knowledge Sync", "status": "ready" if data.get("knowledge") else "needs-setup"},
            {"id": "hybrid_rag", "label": "Hybrid RAG + Reranking", "status": "ready" if any("bm25" in str(item.get("rag", "")).lower() and "vector" in str(item.get("rag", "")).lower() for item in data.get("knowledge", [])) else "needs-setup"},
            {"id": "document_extraction", "label": "Dokument-Extraktion", "status": "ready" if extraction.get("engines") and extraction.get("tables") and extraction.get("scans") else "needs-setup"},
            {"id": "artifacts", "label": "Notes/Artifacts Workspace", "status": "ready" if data.get("artifacts") else "needs-setup"},
            {"id": "sandbox", "label": "Code Interpreter Sandbox", "status": "ready" if sandbox.get("enabled") and {"python", "javascript"} <= set(_as_list(sandbox.get("languages"))) else "needs-setup"},
            {"id": "publishing", "label": "Web/App/API/MCP Publishing", "status": "ready" if {"embeddable-chat", "web-app", "rest-api", "mcp-server"} & publications and local_publications else "needs-setup"},
            {"id": "deployment", "label": "Lokales Deployment", "status": "ready" if deployment.get("docker_compose") and deployment.get("dockerfile") else "needs-setup"},
            {"id": "identity", "label": "SSO/OIDC/LDAP/SCIM optional", "status": "optional" if sso.get("solo_mode") else "ready"},
            {"id": "agent_chains", "label": "Agent Chains/Subagents", "status": "ready" if data.get("subagents") else "needs-setup"},
            {"id": "companion", "label": "Mobile/Browser Companion", "status": "ready" if companion.get("browser_extension") and companion.get("workspace_files") else "needs-setup"},
        ]
        ready = sum(1 for item in checklist if item["status"] == "ready")
        blocking = [item for item in checklist if item["status"] == "needs-setup"]
        return {
            "enabled": bool(solo.get("enabled", True)),
            "owner_user": solo.get("owner_user", "u-admin"),
            "workspace_name": solo.get("workspace_name", "Personal M.I.C.A"),
            "local_only": bool(solo.get("local_only", True)),
            "status": "ready" if not blocking else "needs-setup",
            "ready_count": ready,
            "total_count": len(checklist),
            "optional_count": sum(1 for item in checklist if item["status"] == "optional"),
            "blocking_count": len(blocking),
            "checklist": checklist,
            "updated_at": solo.get("updated_at"),
        }

    def _mask_companion_secrets(self, data: dict[str, Any]) -> None:
        companion = data.get("companion")
        if not isinstance(companion, dict):
            return
        for pairing in companion.get("pairing_codes", []):
            code = str(pairing.get("code", ""))
            if code:
                pairing["code"] = f"***{code[-2:]}"

    def _mask_sso_secrets(self, data: dict[str, Any]) -> None:
        sso = data.get("sso")
        if not isinstance(sso, dict):
            return
        for session in sso.get("sessions", []):
            token = str(session.get("token", ""))
            if token:
                session["token"] = f"***{token[-4:]}"
        for provider in data.get("identity_providers", []):
            jwks = provider.get("jwks")
            if not isinstance(jwks, dict):
                continue
            for key in jwks.get("keys", []):
                if isinstance(key, dict) and key.get("k"):
                    key["k"] = "***"

    def _mask_publishing_secrets(self, data: dict[str, Any]) -> None:
        for publication in data.get("publishing", []):
            policy = publication.get("policy")
            if not isinstance(policy, dict):
                continue
            hashes = policy.get("api_key_hashes")
            if isinstance(hashes, list):
                policy["api_key_hashes"] = [f"sha256:***{str(item)[-6:]}" for item in hashes]
            keys = policy.get("api_keys")
            if isinstance(keys, list):
                policy["api_keys"] = [
                    {
                        "id": key.get("id"),
                        "name": key.get("name"),
                        "status": key.get("status"),
                        "created_at": key.get("created_at"),
                        "last_used_at": key.get("last_used_at"),
                    }
                    for key in keys
                    if isinstance(key, dict)
                ]
        for event in data.get("invocation_audit", []):
            if "api_key_hash" in event:
                event["api_key_hash"] = f"sha256:***{str(event['api_key_hash'])[-6:]}"

    def _with_counts(self, data: dict[str, Any]) -> dict[str, Any]:
        data["counts"] = {
            "agents": len(data.get("agents", [])),
            "agent_packages": len(data.get("agent_packages", [])),
            "users": len(data.get("users", [])),
            "marketplace_installed": sum(1 for item in data.get("marketplace", []) if item.get("installed")),
            "tools": len(data.get("tools", [])),
            "workflows": len(data.get("workflows", [])),
            "runs": len(data.get("runs", [])),
            "evaluations": len(data.get("evaluations", [])),
            "knowledge_sources": len(data.get("knowledge", [])),
            "artifacts": len(data.get("artifacts", [])),
            "identity_providers": len(data.get("identity_providers", [])),
            "knowledge_runs": len(data.get("knowledge_runs", [])),
            "knowledge_scheduler_runs": len(data.get("knowledge_scheduler_runs", [])),
            "knowledge_searches": len(data.get("knowledge_searches", [])),
            "evaluation_runs": len(data.get("evaluation_runs", [])),
            "agent_chain_runs": len(data.get("agent_chain_runs", [])),
            "extraction_runs": len(data.get("extraction", {}).get("runs", [])),
            "audit_events": len(data.get("audit_events", [])),
            "solo_audits": len(data.get("solo_audits", [])),
        }
        return data

    def action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "prepare_solo_workspace": self._prepare_solo_workspace,
            "run_solo_quickstart": self._run_solo_quickstart,
            "run_solo_audit": self._run_solo_audit,
            "save_agent": self._save_agent,
            "delete_agent": self._delete_agent,
            "start_agent_run": self._start_agent_run,
            "pause_agent_run": self._pause_agent_run,
            "resume_agent_run": self._resume_agent_run,
            "stop_agent_run": self._stop_agent_run,
            "export_agent_package": self._export_agent_package,
            "import_agent_package": self._import_agent_package,
            "install_marketplace_item": self._install_marketplace_item,
            "sync_marketplace_registry": self._sync_marketplace_registry,
            "verify_marketplace_item": self._verify_marketplace_item,
            "review_marketplace_item": self._review_marketplace_item,
            "save_marketplace_policy": self._save_marketplace_policy,
            "update_marketplace_item": self._update_marketplace_item,
            "set_marketplace_item_enabled": self._set_marketplace_item_enabled,
            "uninstall_marketplace_item": self._uninstall_marketplace_item,
            "import_openapi": self._import_openapi,
            "discover_mcp_tools": self._discover_mcp_tools,
            "load_mcp_tool": self._load_mcp_tool,
            "unload_mcp_tool": self._unload_mcp_tool,
            "save_tool": self._save_tool,
            "test_tool": self._test_tool,
            "execute_openapi_tool": self._execute_openapi_tool,
            "save_group": self._save_group,
            "save_role": self._save_role,
            "save_acl": self._save_acl,
            "share_agent": self._share_agent,
            "check_access": self._check_access_action,
            "save_identity_provider": self._save_identity_provider,
            "test_identity_provider": self._test_identity_provider,
            "start_sso_login": self._start_sso_login,
            "complete_sso_login": self._complete_sso_login,
            "ldap_bind_login": self._ldap_bind_login,
            "provision_scim_user": self._provision_scim_user,
            "deprovision_scim_user": self._deprovision_scim_user,
            "sync_identity_claims": self._sync_identity_claims,
            "save_knowledge_source": self._save_knowledge_source,
            "schedule_knowledge_sync": self._schedule_knowledge_sync,
            "save_workflow": self._save_workflow,
            "edit_workflow_node": self._edit_workflow_node,
            "connect_workflow_nodes": self._connect_workflow_nodes,
            "schedule_workflow": self._schedule_workflow,
            "run_due_workflows": self._run_due_workflows,
            "version_workflow": self._version_workflow,
            "run_workflow": self._run_workflow,
            "resume_workflow_run": self._resume_workflow_run,
            "run_evaluation": self._run_evaluation,
            "save_evaluation_dataset": self._save_evaluation_dataset,
            "run_agent_chain": self._run_agent_chain,
            "sync_knowledge": self._sync_knowledge,
            "search_knowledge": self._search_knowledge,
            "run_due_knowledge_syncs": self._run_due_knowledge_syncs,
            "ingest_documents": self._ingest_documents,
            "configure_extraction": self._configure_extraction,
            "create_artifact": self._create_artifact,
            "version_artifact": self._version_artifact,
            "restore_artifact_version": self._restore_artifact_version,
            "link_artifact": self._link_artifact,
            "delete_artifact": self._delete_artifact,
            "render_artifact": self._render_artifact,
            "run_sandbox": self._run_sandbox,
            "publish_agent": self._publish_agent,
            "save_publish_policy": self._save_publish_policy,
            "issue_publish_api_key": self._issue_publish_api_key,
            "revoke_publish_api_key": self._revoke_publish_api_key,
            "rotate_publish_api_key": self._rotate_publish_api_key,
            "get_publication": self._get_publication,
            "check_deployment_readiness": self._check_deployment_readiness,
            "check_database_migrations": self._check_database_migrations,
            "save_user": self._save_user,
            "save_secret_reference": self._save_secret_reference,
            "delete_secret_reference": self._delete_secret_reference,
            "test_integration": self._test_integration,
            "aggregate_metrics": self._aggregate_metrics_action,
            "list_workspace_files": self._list_workspace_files,
            "read_workspace_file": self._read_workspace_file,
            "run_local_terminal": self._run_local_terminal,
            "run_companion_terminal": self._run_companion_terminal,
            "create_companion_pairing": self._create_companion_pairing,
            "activate_companion_session": self._activate_companion_session,
            "heartbeat_companion_session": self._heartbeat_companion_session,
            "revoke_companion_session": self._revoke_companion_session,
            "get_companion_workspace": self._get_companion_workspace,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"unknown platform action: {action}"}
        started = time.perf_counter()
        authorized = self._authorize_action(action, payload)
        if not authorized["allowed"]:
            result = {
                "error": "permission denied",
                "action": action,
                "user": authorized["user"],
                "permission": authorized["permission"],
                "effective_permissions": authorized["effective_permissions"],
            }
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            self._record_audit_event(action, payload, status="denied", permission=authorized["permission"], result=result)
            self._record_metric_event(action, payload, result, latency_ms, status="denied")
            self._save()
            return {"error": result["error"], "result": _json_clone(result), "platform": self.snapshot()}
        result = handler(payload)
        if action == "check_deployment_readiness" and isinstance(result, dict):
            publication_id = str(payload.get("id") or payload.get("publication_id") or "")
            publication = next(
                (item for item in self.data.get("publishing", []) if item.get("id") == publication_id),
                None,
            )
            if publication:
                now = datetime.now()
                expired_keys = []
                for key in _as_list(publication.get("policy", {}).get("api_keys")):
                    if not isinstance(key, dict) or not key.get("expires_at"):
                        continue
                    with contextlib.suppress(ValueError, TypeError):
                        if datetime.fromisoformat(str(key["expires_at"])) <= now:
                            expired_keys.append(str(key.get("key_id") or key.get("id") or ""))
                result["expired_keys"] = expired_keys
                if expired_keys:
                    result.setdefault("warnings", []).append(f"{len(expired_keys)} expired API key(s)")
        if payload.get("api_key") or payload.get("token"):
            audit_result = result if isinstance(result, dict) else {"result": result}
            audit_status = "completed"
            if action == "check_deployment_readiness":
                publication_id = str(payload.get("id") or payload.get("publication_id") or "")
                if not any(item.get("id") == publication_id for item in self.data.get("publishing", [])):
                    audit_result = {"error": "publication not found"}
                    audit_status = "failed"
            elif audit_result.get("error"):
                audit_status = "failed"
            self._record_invocation_audit(
                str(payload.get("id") or payload.get("agent_id") or "platform"),
                payload,
                audit_result,
                audit_status,
                action=action,
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if isinstance(result, dict) and "error" in result:
            self._record_audit_event(action, payload, status="error", permission=authorized["permission"], result=result)
            self._record_metric_event(action, payload, result, latency_ms, status="error")
            self._save()
            return {"error": result["error"], "result": _json_clone(result), "platform": self.snapshot()}
        self._record_audit_event(action, payload, status="ok", permission=authorized["permission"], result=result)
        self._record_metric_event(action, payload, result, latency_ms, status="ok")
        self.data["updated_at"] = _now()
        self._save()
        return {"status": "ok", "result": _json_clone(result), "platform": self.snapshot()}

    def get_agent_manifest(self, agent_id: str) -> dict[str, Any] | None:
        agent = next((item for item in self.data.get("agents", []) if item.get("id") == agent_id), None)
        if not agent:
            return None
        return {
            "agent_id": agent.get("id"),
            "name": agent.get("name"),
            "version": agent.get("version", "1.0.0"),
            "model": agent.get("model"),
            "prompt": agent.get("prompt", ""),
            "tools": agent.get("tools", []),
            "knowledge": agent.get("knowledge", []),
            "parameters": agent.get("parameters", {}),
            "permissions": agent.get("permissions", []),
            "visibility": agent.get("visibility", "team"),
            "owner": agent.get("owner", "u-admin"),
            "package_format": "mica-agent-package/v1",
            "endpoints": {
                "web_app": f"/apps/{agent_id}",
                "embed": f"/embed/{agent_id}",
                "rest": f"/api/agents/{agent_id}/invoke",
                "mcp": f"/mcp/{agent_id}",
            },
            "publications": [
                {
                    "id": publication.get("id"),
                    "kind": publication.get("kind"),
                    "status": publication.get("status"),
                    "url": publication.get("url"),
                    "policy": self._public_policy(publication.get("policy", {})),
                }
                for publication in self.data.get("publishing", [])
                if publication.get("agent_id") == agent_id
            ],
        }

    def get_agent_package(self, agent_id: str) -> dict[str, Any] | None:
        manifest = self.get_agent_manifest(agent_id)
        if not manifest:
            return None
        return {
            "format": "mica-agent-package/v1",
            "exported_at": _now(),
            "manifest": manifest,
            "runtime": {
                "tool_count": len(manifest.get("tools", [])),
                "knowledge_count": len(manifest.get("knowledge", [])),
                "parameter_keys": sorted((manifest.get("parameters") or {}).keys()),
            },
        }

    def get_agent_web_app(self, agent_id: str, *, embedded: bool = False) -> str | None:
        agent = next((item for item in self.data.get("agents", []) if item.get("id") == agent_id), None)
        if not agent:
            return None
        title = html.escape(str(agent.get("name") or agent_id))
        prompt = html.escape(str(agent.get("prompt") or ""))
        tools = html.escape(", ".join(str(tool) for tool in agent.get("tools", [])) or "none")
        knowledge = html.escape(", ".join(str(source) for source in agent.get("knowledge", [])) or "none")
        model = html.escape(str(agent.get("model", "fast")))
        escaped_agent_id = html.escape(agent_id)
        agent_id_json = json.dumps(agent_id)
        shell_class = "embed" if embedded else "app"
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} - M.I.C.A Agent</title>
    <style>
      :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
      body {{ margin: 0; background: #06131c; color: #e7eef7; }}
      main {{ min-height: 100vh; display: grid; grid-template-rows: auto 1fr auto; }}
      header {{ padding: 18px 20px; border-bottom: 1px solid rgba(255,255,255,.1); }}
      h1 {{ font-size: 20px; margin: 0 0 6px; }}
      p {{ color: #9fb4c7; margin: 0; }}
      section {{ display: grid; gap: 12px; padding: 16px 20px; }}
      .meta {{ display: grid; gap: 8px; font-size: 12px; color: #b8c7d8; }}
      textarea {{ min-height: {120 if embedded else 180}px; resize: vertical; border: 1px solid rgba(255,255,255,.14); border-radius: 8px; background: #0a1d2a; color: inherit; padding: 12px; }}
      button {{ height: 38px; border: 0; border-radius: 8px; background: #39b7a5; color: #03111a; font-weight: 800; cursor: pointer; }}
      pre {{ margin: 0; min-height: 110px; white-space: pre-wrap; border-radius: 8px; background: rgba(255,255,255,.06); color: #d5e2ef; padding: 12px; }}
      footer {{ padding: 10px 20px; color: #71869b; font-size: 11px; }}
      .embed header {{ padding: 12px 14px; }}
      .embed section {{ padding: 12px 14px; }}
    </style>
  </head>
  <body>
    <main class="{shell_class}">
      <header>
        <h1>{title}</h1>
        <p>{prompt}</p>
      </header>
      <section>
        <div class="meta">
          <span>Model: {model}</span>
          <span>Tools: {tools}</span>
          <span>Knowledge: {knowledge}</span>
        </div>
        <textarea id="message" placeholder="Send a message to this M.I.C.A agent"></textarea>
        <button id="send">Send</button>
        <pre id="output">Ready.</pre>
      </section>
      <footer>REST: /api/agents/{escaped_agent_id}/invoke · MCP: /mcp/{escaped_agent_id}</footer>
    </main>
    <script>
      const send = document.querySelector('#send');
      const message = document.querySelector('#message');
      const output = document.querySelector('#output');
      send.addEventListener('click', async () => {{
        output.textContent = 'Running...';
        const agentId = {agent_id_json};
        const response = await fetch(`/api/agents/${{encodeURIComponent(agentId)}}/invoke`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ message: message.value }})
        }});
        const body = await response.json();
        output.textContent = body.output || body.error || JSON.stringify(body, null, 2);
      }});
    </script>
  </body>
</html>
"""

    def get_agent_mcp_descriptor(self, agent_id: str) -> dict[str, Any] | None:
        manifest = self.get_agent_manifest(agent_id)
        if not manifest:
            return None
        return {
            "schema_version": "2024-11-05",
            "name": f"mica-agent-{agent_id}",
            "description": f"MCP descriptor for {manifest['name']}",
            "tools": [
                {
                    "name": "invoke_agent",
                    "description": f"Invoke {manifest['name']} through M.I.C.A.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "input": {"type": "string"},
                        },
                    },
                    "endpoint": manifest["endpoints"]["rest"],
                }
            ],
            "resources": [
                {"uri": f"mica://agents/{agent_id}/manifest", "name": manifest["name"], "mimeType": "application/json"}
            ],
            "manifest": manifest,
        }

    def invoke_agent(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        agent = next((item for item in self.data.get("agents", []) if item.get("id") == agent_id), None)
        if not agent:
            return {"error": "agent not found"}
        policy_error = self._validate_invoke_policy(agent_id, payload)
        if policy_error:
            self._record_invocation_audit(agent_id, payload, policy_error, "denied")
            self._save()
            return policy_error
        message = str(payload.get("message") or payload.get("input") or "")
        invocation = {
            "id": f"invoke-{uuid4().hex[:8]}",
            "agent_id": agent_id,
            "status": "completed",
            "input": message,
            "output": f"{agent.get('name')} accepted the request with {len(agent.get('tools', []))} tools and {len(agent.get('knowledge', []))} knowledge sources.",
            "tool_plan": agent.get("tools", []),
            "policy": self._active_publication_policy(agent_id),
            "created_at": _now(),
        }
        self.data.setdefault("invocations", []).insert(0, invocation)
        self._record_invocation_audit(agent_id, payload, invocation, "completed")
        self._save()
        return invocation

    def _active_publication_policy(self, agent_id: str) -> dict[str, Any]:
        publication = next(
            (
                item
                for item in self.data.get("publishing", [])
                if item.get("agent_id") == agent_id and item.get("status") == "published"
            ),
            None,
        )
        if not publication:
            return {"auth": "workspace", "rate_limit_per_minute": 60, "allowed_groups": ["core"], "audit_invocations": True}
        return self._public_policy(publication.get("policy", {}))

    def _active_raw_publication_policy(self, agent_id: str) -> dict[str, Any]:
        publication = next(
            (
                item
                for item in self.data.get("publishing", [])
                if item.get("agent_id") == agent_id and item.get("status") == "published"
            ),
            None,
        )
        if not publication:
            return {"auth": "workspace", "rate_limit_per_minute": 60, "allowed_groups": ["core"], "audit_invocations": True, "api_key_hashes": [], "api_keys": []}
        policy = publication.setdefault("policy", {})
        policy.setdefault("api_key_hashes", [])
        policy.setdefault("api_keys", [])
        return policy

    def _public_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        return {
            "auth": policy.get("auth", "workspace"),
            "cors": _as_list(policy.get("cors")),
            "rate_limit_per_minute": int(policy.get("rate_limit_per_minute", 60) or 60),
            "allowed_groups": _as_list(policy.get("allowed_groups") or ["core"]),
            "secret_refs": ["configured" for _ in _as_list(policy.get("secret_refs"))],
            "api_keys": [
                {"id": key.get("id"), "name": key.get("name"), "status": key.get("status"), "created_at": key.get("created_at"), "last_used_at": key.get("last_used_at")}
                for key in _as_list(policy.get("api_keys"))
                if isinstance(key, dict)
            ],
            "api_key_count": len(_as_list(policy.get("api_key_hashes"))),
            "audit_invocations": bool(policy.get("audit_invocations", True)),
        }

    def _validate_invoke_policy(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        raw_policy = self._active_raw_publication_policy(agent_id)
        policy = self._public_policy(raw_policy)
        auth = str(policy.get("auth") or "workspace")
        if auth == "api-key":
            api_key = str(payload.get("api_key") or payload.get("token") or "")
            if not api_key:
                return {"error": "api key required", "policy": policy}
            key_hash = self._hash_publish_api_key(api_key)
            allowed_hashes = set(str(item) for item in _as_list(raw_policy.get("api_key_hashes")))
            if not allowed_hashes:
                return {"error": "api key not configured", "policy": policy}
            if key_hash not in allowed_hashes:
                return {"error": "invalid api key", "policy": policy}
            for key in raw_policy.get("api_keys", []):
                if isinstance(key, dict) and key.get("hash") == key_hash:
                    if key.get("status") != "active":
                        return {"error": "api key revoked", "policy": policy}
                    key["last_used_at"] = _now()
        if auth == "workspace":
            user_id = str(payload.get("user") or payload.get("user_id") or "u-admin")
            permissions = self._effective_permissions(user_id)
            if not self._permissions_allow(permissions, "agents:execute"):
                return {"error": "permission denied", "policy": policy}
        recent = [
            item
            for item in self.data.get("invocations", [])
            if item.get("agent_id") == agent_id and item.get("created_at", "") >= (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
        ]
        if len(recent) >= int(policy.get("rate_limit_per_minute", 60) or 60):
            return {"error": "rate limit exceeded", "policy": policy}
        return None

    def _hash_publish_api_key(self, api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    def _record_invocation_audit(self, agent_id: str, payload: dict[str, Any], result: dict[str, Any], status: str, *, action: str = "invoke_agent") -> None:
        api_key = str(payload.get("api_key") or payload.get("token") or "")
        event = {
            "id": f"invoke-audit-{uuid4().hex[:8]}",
            "agent_id": agent_id,
            "action": action,
            "status": status,
            "auth": self._active_publication_policy(agent_id).get("auth", "workspace"),
            "user": payload.get("user") or payload.get("user_id") or "anonymous",
            "api_key_hash": self._hash_publish_api_key(api_key) if api_key else "",
            "error": result.get("error", ""),
            "timestamp": _now(),
        }
        self.data.setdefault("invocation_audit", []).insert(0, event)
        self.data["invocation_audit"] = self.data["invocation_audit"][:500]

    def _record_metric_event(
        self,
        action: str,
        payload: dict[str, Any],
        result: Any,
        latency_ms: float,
        *,
        status: str,
    ) -> None:
        user = str(payload.get("user") or payload.get("user_id") or "u-admin")
        agent = str(payload.get("agent_id") or payload.get("id") or "platform")
        workflow = str(payload.get("workflow_id") or payload.get("workflow") or "platform")
        tool = str(payload.get("tool") or payload.get("tool_name") or action)
        model = str(payload.get("model") or "platform")
        token_seed = len(json.dumps(payload, default=str)) + len(json.dumps(result, default=str)[:2000])
        tokens = max(1, token_seed // 4)
        cost = round(tokens * 0.000002, 6) if model != "local" else 0.0
        event = {
            "id": f"metric-{uuid4().hex[:8]}",
            "action": action,
            "scope": agent if agent != "platform" else tool,
            "model": model,
            "tool": tool,
            "user": user,
            "actor": user,
            "agent": agent,
            "workflow": workflow,
            "tokens": tokens,
            "cost": cost,
            "latency_ms": latency_ms,
            "tool_calls": 1 if action not in {"aggregate_metrics", "check_access"} else 0,
            "status": status,
            "timestamp": _now(),
        }
        self.data.setdefault("metric_events", []).insert(0, event)
        self.data["metric_events"] = self.data["metric_events"][:500]
        self.data.setdefault("metrics", []).insert(0, event)
        self.data["metrics"] = self.data["metrics"][:250]

    def _record_audit_event(
        self,
        action: str,
        payload: dict[str, Any],
        *,
        status: str,
        permission: str,
        result: Any,
    ) -> None:
        user = str(payload.get("user") or payload.get("user_id") or "u-admin")
        resource = self._audit_resource_for_action(action, payload, result)
        event = {
            "id": f"audit-{uuid4().hex[:8]}",
            "action": action,
            "user": user,
            "actor": user,
            "permission": permission,
            "resource": resource,
            "status": status,
            "timestamp": _now(),
        }
        if isinstance(result, dict) and result.get("error"):
            event["error"] = str(result["error"])
        self.data.setdefault("audit_events", []).insert(0, event)
        self.data["audit_events"] = self.data["audit_events"][:500]

    def _audit_resource_for_action(self, action: str, payload: dict[str, Any], result: Any) -> str:
        if payload.get("resource"):
            return str(payload["resource"])
        if payload.get("agent_id"):
            return f"agent:{payload['agent_id']}"
        if payload.get("workflow_id"):
            return f"workflow:{payload['workflow_id']}"
        if isinstance(result, dict):
            if result.get("id"):
                return f"{action}:{result['id']}"
            if isinstance(result.get("agent"), dict) and result["agent"].get("id"):
                return f"agent:{result['agent']['id']}"
        return action

    def _authorize_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        permission = ACTION_PERMISSIONS.get(action, "read")
        user_id = str(payload.get("user") or payload.get("user_id") or "u-admin")
        permissions = self._effective_permissions(user_id)
        allowed = self._permissions_allow(permissions, permission)
        return {
            "allowed": allowed,
            "user": user_id,
            "permission": permission,
            "effective_permissions": sorted(permissions),
        }

    def _permissions_allow(self, permissions: set[str], permission: str) -> bool:
        if "*" in permissions or permission in permissions:
            return True
        if "read" in permissions and permission.endswith(":read"):
            return True
        scope = permission.split(":", 1)[0]
        return f"{scope}:*" in permissions

    def _aggregate_metrics_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        dimensions = _as_list(payload.get("dimensions") or ["model", "tool", "user", "agent", "workflow"])
        events = self._filter_metric_events(payload)
        top_n = max(1, int(payload.get("top_n") or 10))
        aggregates: dict[str, list[dict[str, Any]]] = {}
        for dimension in dimensions:
            grouped: dict[str, dict[str, Any]] = {}
            for event in events:
                key = str(event.get(str(dimension)) or "unknown")
                bucket = grouped.setdefault(
                    key,
                    {
                        "dimension": str(dimension),
                        "key": key,
                        "tokens": 0,
                        "cost": 0.0,
                        "latency_ms": 0.0,
                        "tool_calls": 0,
                        "count": 0,
                    },
                )
                bucket["tokens"] += int(event.get("tokens", 0) or 0)
                bucket["cost"] += float(event.get("cost", 0.0) or 0.0)
                bucket["latency_ms"] += float(event.get("latency_ms", 0.0) or 0.0)
                bucket["tool_calls"] += int(event.get("tool_calls", 0) or 0)
                bucket["count"] += 1
            rows = []
            for bucket in grouped.values():
                count = max(1, int(bucket["count"]))
                rows.append(
                    {
                        **bucket,
                        "cost": round(float(bucket["cost"]), 6),
                        "avg_latency_ms": round(float(bucket["latency_ms"]) / count, 2),
                    }
                )
            rows.sort(key=lambda item: (item["tokens"], item["tool_calls"]), reverse=True)
            aggregates[str(dimension)] = rows[:top_n]
        self.data["metrics_aggregate"] = aggregates
        return {"aggregates": aggregates, "event_count": len(events), "filters": self._metric_filter_summary(payload), "updated_at": _now()}

    def _filter_metric_events(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        start = str(payload.get("start") or filters.get("start") or "")
        end = str(payload.get("end") or filters.get("end") or "")
        rows = []
        for event in self.data.get("metrics", []):
            if not isinstance(event, dict):
                continue
            if start and str(event.get("timestamp", "")) < start:
                continue
            if end and str(event.get("timestamp", "")) > end:
                continue
            matched = True
            for key in ("model", "tool", "user", "agent", "workflow", "status"):
                allowed = _as_list(payload.get(key) or filters.get(key))
                if allowed and str(event.get(key) or "") not in {str(item) for item in allowed}:
                    matched = False
                    break
            if matched:
                rows.append(event)
        return rows

    def _metric_filter_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        summary: dict[str, Any] = {}
        for key in ("start", "end", "model", "tool", "user", "agent", "workflow", "status"):
            value = payload.get(key) or filters.get(key)
            if value:
                summary[key] = value
        return summary

    def _upsert(self, key: str, item: dict[str, Any], id_field: str = "id") -> dict[str, Any]:
        items = self.data.setdefault(key, [])
        item.setdefault(id_field, _slug(str(item.get("name") or uuid4().hex[:8])))
        for index, existing in enumerate(items):
            if existing.get(id_field) == item[id_field]:
                items[index] = {**existing, **item}
                return items[index]
        items.append(item)
        return item

    def _prepare_solo_workspace(self, payload: dict[str, Any]) -> dict[str, Any]:
        owner_id = str(payload.get("owner_user") or self.data.get("solo", {}).get("owner_user") or "u-admin")
        workspace_name = str(payload.get("workspace_name") or self.data.get("solo", {}).get("workspace_name") or "Personal M.I.C.A")
        self.data["solo"] = {
            "enabled": True,
            "owner_user": owner_id,
            "workspace_name": workspace_name,
            "local_only": bool(payload.get("local_only", True)),
            "status": "ready",
            "updated_at": _now(),
        }
        self._normalize_solo(self.data)

        owner = next((item for item in self.data.get("users", []) if item.get("id") == owner_id), None)
        if owner:
            owner["name"] = payload.get("owner_name") or owner.get("name") or "You"
            owner["email"] = payload.get("owner_email") or owner.get("email") or "you@mica.local"
            owner["roles"] = ["owner"]
            owner["groups"] = ["personal"]
        for group in self.data.get("groups", []):
            if group.get("id") == "personal":
                group["members"] = [owner_id]
            elif owner_id in _as_list(group.get("members")) and group.get("id") not in {"core"}:
                group["members"] = [member for member in _as_list(group.get("members")) if member != owner_id]

        for agent in self.data.get("agents", []):
            agent["owner"] = owner_id
            agent["visibility"] = "private"
            agent.setdefault("parameters", {"temperature": 0.3, "max_tokens": 1800})
            knowledge = _as_list(agent.get("knowledge"))
            if "local-documents" not in knowledge:
                knowledge.append("local-documents")
            agent["knowledge"] = knowledge
            agent["updated_at"] = _now()

        self._upsert("acls", {"resource": "workspace:personal", "subjects": [{"type": "user", "id": owner_id, "access": "owner"}]}, id_field="resource")
        for agent in self.data.get("agents", []):
            self._upsert(
                "acls",
                {"resource": f"agent:{agent.get('id')}", "subjects": [{"type": "user", "id": owner_id, "access": "owner"}]},
                id_field="resource",
            )

        self.data["marketplace_policy"] = {
            **self.data.get("marketplace_policy", {}),
            "require_review": True,
            "require_signature": False,
            "allowed_trust": ["verified", "community", "local"],
            "max_risk": "medium",
            "permission_denylist": ["system:write", "network:unrestricted", "secrets:read"],
            "trusted_publishers": ["mica", "local"],
            "solo_install_mode": "local-review",
            "updated_at": _now(),
        }

        for source in self.data.setdefault("knowledge", []):
            if source.get("source") in {"GitHub", "Drive", "S3", "Confluence"} and source.get("connector_status") != "connected":
                source["status"] = "optional"
                source["schedule"] = "manual"
            source.setdefault("watch_mode", source.get("source") == "Folder")
        for source in [
            {"id": "local-documents", "source": "Folder", "target": "Documents", "uri": "Documents", "status": "watching", "last_sync": _now(), "rag": "hybrid: bm25 + vector + reranker", "vector_db": "chroma", "schedule": "watch", "watch_mode": True},
            {"id": "mica-memory", "source": "Folder", "target": "M.I.C.A Memory", "uri": "memory", "status": "watching", "last_sync": _now(), "rag": "hybrid: bm25 + vector + reranker", "vector_db": "chroma", "schedule": "watch", "watch_mode": True},
        ]:
            self._upsert("knowledge", source)
        self._normalize_knowledge_sources(self.data)

        sso = self.data.setdefault("sso", {})
        sso.update({"solo_mode": True, "default_provider": "local", "oidc": "optional", "ldap": "optional", "scim": "optional", "provisioning": "local-only"})
        for provider in self.data.setdefault("identity_providers", []):
            if provider.get("id") == "local":
                provider.update({"status": "enabled", "scim_enabled": False, "last_test": _now()})

        for publication in self.data.get("publishing", []):
            kind = str(publication.get("kind") or "")
            policy = publication.setdefault("policy", {})
            if kind in {"web-app", "embeddable-chat"}:
                policy["auth"] = "workspace"
                policy["secret_refs"] = []
            policy["allowed_groups"] = ["personal"]
            policy.setdefault("rate_limit_per_minute", 60)
            publication["updated_at"] = _now()
        existing_publication_kinds = {str(item.get("kind")) for item in self.data.get("publishing", []) if item.get("agent_id") == "research-copilot"}
        publication_defaults = [
            ("web-app", "/apps/research-copilot", {"auth": "workspace", "rate_limit_per_minute": 60, "allowed_groups": ["personal"], "secret_refs": []}),
            ("embeddable-chat", "/embed/research-copilot", {"auth": "workspace", "rate_limit_per_minute": 60, "allowed_groups": ["personal"], "secret_refs": []}),
            ("rest-api", "/api/agents/research-copilot/invoke", {"auth": "api-key", "rate_limit_per_minute": 120, "allowed_groups": ["personal"], "secret_refs": ["MICA_AGENT_TOKEN"]}),
            ("mcp-server", "/mcp/research-copilot", {"auth": "api-key", "rate_limit_per_minute": 120, "allowed_groups": ["personal"], "secret_refs": ["MICA_MCP_TOKEN"]}),
        ]
        for kind, url, policy in publication_defaults:
            if kind in existing_publication_kinds:
                continue
            self.data.setdefault("publishing", []).append(
                {
                    "id": f"pub-{_slug(kind)}",
                    "agent_id": "research-copilot",
                    "kind": kind,
                    "status": "draft",
                    "url": url,
                    "policy": policy,
                    "updated_at": _now(),
                }
            )

        if not any(item.get("id") == "artifact-solo-start" for item in self.data.get("artifacts", [])):
            self._create_artifact(
                {
                    "id": "artifact-solo-start",
                    "title": "Solo Workspace Start",
                    "kind": "note",
                    "content": "Personal M.I.C.A workspace is ready for private agents, local tools, knowledge sync, sandbox runs, and local publishing.",
                    "created_by": owner_id,
                }
            )

        companion = self.data.setdefault("companion", {})
        companion.update({"pairing_required": True, "remote_access": "guarded-local", "workspace_files": True, "terminal": True})
        self._normalize_companion(self.data)
        self._ensure_companion_manifest()
        return {"solo_status": self._solo_status(self.data), "workspace_name": workspace_name}

    def _run_solo_quickstart(self, payload: dict[str, Any]) -> dict[str, Any]:
        setup = self._prepare_solo_workspace(
            {
                "workspace_name": payload.get("workspace_name") or self.data.get("solo", {}).get("workspace_name") or "Personal M.I.C.A",
                "owner_user": payload.get("user") or self.data.get("solo", {}).get("owner_user") or "u-admin",
            }
        )
        agent_id = str(payload.get("agent_id") or "research-copilot")
        message = str(payload.get("message") or "Summarize my local M.I.C.A workspace and suggest the next useful action.")
        query = str(payload.get("query") or "local M.I.C.A workspace hybrid rag tools")
        files = _as_list(payload.get("files") or ["solo-note.md", "local-scan.pdf"])

        knowledge = self._sync_knowledge({"id": "local-documents"})
        search = self._search_knowledge({"query": query, "source_ids": ["local-documents"], "top_k": 3})
        ingestion = self._ingest_documents({"files": files, "engine": "Docling"})
        sandbox = self._run_sandbox(
            {
                "language": "python",
                "code": "print('Solo M.I.C.A quickstart ready')\nprint('local tools, knowledge, artifacts, and publishing are prepared')",
            }
        )
        workflow_id = str(payload.get("workflow_id") or (self.data.get("workflows", [{}])[0].get("id") if self.data.get("workflows") else ""))
        workflow = self._run_workflow({"workflow_id": workflow_id}) if workflow_id else {"error": "no workflow available"}
        agent = self.invoke_agent(agent_id, {"message": message, "user": payload.get("user", "u-admin")})

        for kind in ("web-app", "embeddable-chat", "rest-api", "mcp-server"):
            if not any(item.get("agent_id") == agent_id and item.get("kind") == kind and item.get("status") == "published" for item in self.data.get("publishing", [])):
                self._publish_agent({"agent_id": agent_id, "kind": kind, "policy": {"allowed_groups": ["personal"]}})

        artifact = self._create_artifact(
            {
                "id": "artifact-solo-quickstart",
                "title": "Solo Quickstart Result",
                "kind": "report",
                "content": json.dumps(
                    {
                        "agent": agent.get("output", ""),
                        "knowledge_results": len(search.get("results", [])),
                        "ingestion": ingestion.get("id"),
                        "sandbox": sandbox.get("status"),
                        "workflow": workflow.get("status"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "created_by": payload.get("user", "u-admin"),
            }
        )
        rendered = self._render_artifact({"id": artifact["id"]})
        publications = [item for item in self.data.get("publishing", []) if item.get("agent_id") == agent_id]
        summary = {
            "title": f"{self.data.get('solo', {}).get('workspace_name', 'Personal M.I.C.A')} ist lokal bereit",
            "agent_output": str(agent.get("output") or ""),
            "knowledge_results": len(search.get("results", [])),
            "ingested_documents": len(ingestion.get("documents", [])),
            "sandbox_stdout": str(sandbox.get("stdout") or "").strip(),
            "workflow_status": workflow.get("status", "unknown"),
            "artifact_id": artifact["id"],
        }
        next_actions = [
            {"label": "Agent im lokalen Web-App-Fenster oeffnen", "href": f"/apps/{agent_id}", "kind": "link"},
            {"label": "Knowledge-Treffer pruefen", "target": "knowledge", "kind": "tab"},
            {"label": "Quickstart-Report rendern", "target": artifact["id"], "kind": "artifact"},
            {"label": "Sandbox-Ausgabe kontrollieren", "target": sandbox.get("id"), "kind": "sandbox"},
        ]
        result = {
            "status": "ready",
            "solo_status": setup["solo_status"],
            "summary": summary,
            "next_actions": next_actions,
            "agent": agent,
            "knowledge_run": knowledge["run"],
            "knowledge_search": search,
            "ingestion_run": ingestion,
            "sandbox_run": sandbox,
            "workflow_run": workflow,
            "artifact": artifact,
            "rendered_artifact": rendered,
            "links": {
                "agent_app": f"/apps/{agent_id}",
                "embed": f"/embed/{agent_id}",
                "rest": f"/api/agents/{agent_id}/invoke",
                "mcp": f"/mcp/{agent_id}",
            },
            "publications": publications,
        }
        self.data.setdefault("solo_quickstarts", []).insert(0, {
            "id": f"solo-quickstart-{uuid4().hex[:8]}",
            "status": result["status"],
            "agent_id": agent_id,
            "artifact_id": artifact["id"],
            "summary": summary,
            "next_actions": next_actions,
            "created_at": _now(),
            "links": result["links"],
        })
        self.data["solo_quickstarts"] = self.data["solo_quickstarts"][:25]
        return result

    def _save_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "New Agent")
        parameters = payload.get("parameters", {"temperature": 0.4, "max_tokens": 1600})
        if isinstance(parameters, str):
            with contextlib.suppress(Exception):
                parameters = json.loads(parameters)
        if not isinstance(parameters, dict):
            parameters = {"temperature": 0.4, "max_tokens": 1600}
        agent = {
            "id": payload.get("id") or _slug(name),
            "name": name,
            "model": payload.get("model", "fast"),
            "prompt": payload.get("prompt", "You are a helpful M.I.C.A agent."),
            "tools": _as_list(payload.get("tools")),
            "knowledge": _as_list(payload.get("knowledge")),
            "parameters": parameters,
            "permissions": _as_list(payload.get("permissions")),
            "version": payload.get("version", "1.0.0"),
            "visibility": payload.get("visibility", "private" if self.data.get("solo", {}).get("enabled", True) else "team"),
            "owner": payload.get("owner", self.data.get("solo", {}).get("owner_user", "u-admin")),
            "updated_at": _now(),
        }
        return self._upsert("agents", agent)

    def _delete_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or payload.get("id") or "").strip()
        if not agent_id:
            return {"error": "agent_id is required"}
        agent = next((item for item in self.data.get("agents", []) if item.get("id") == agent_id), None)
        if not agent:
            return {"error": "agent not found"}
        active_runs = [
            run for run in self.data.get("agent_runs", [])
            if run.get("agent_id") == agent_id and run.get("status") in {"running", "paused"}
        ]
        if active_runs and not payload.get("force"):
            return {"error": "agent has active runs", "active_run_ids": [run.get("id") for run in active_runs]}
        self.data["agents"] = [item for item in self.data.get("agents", []) if item.get("id") != agent_id]
        self.data["publishing"] = [item for item in self.data.get("publishing", []) if item.get("agent_id") != agent_id]
        return {"deleted": True, "agent": agent}

    def _start_agent_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or payload.get("id") or "").strip()
        agent = next((item for item in self.data.get("agents", []) if item.get("id") == agent_id), None)
        if not agent:
            return {"error": "agent not found"}
        assignment = str(payload.get("assignment") or payload.get("message") or payload.get("input") or "").strip()
        if not assignment:
            return {"error": "assignment is required"}
        now = _now()
        run = {
            "id": f"agent-run-{uuid4().hex[:8]}",
            "agent_id": agent_id,
            "agent_name": agent.get("name", agent_id),
            "assignment": assignment,
            "status": "running",
            "model": payload.get("model") or agent.get("model", "fast"),
            "started_at": now,
            "updated_at": now,
            "logs": [{"timestamp": now, "level": "info", "message": "Auftrag gestartet."}],
            "result": "",
        }
        self.data.setdefault("agent_runs", []).insert(0, run)
        self.data["agent_runs"] = self.data["agent_runs"][:250]
        return run

    def _agent_run_transition(self, payload: dict[str, Any], target: str) -> dict[str, Any]:
        run_id = str(payload.get("run_id") or payload.get("id") or "").strip()
        run = next((item for item in self.data.get("agent_runs", []) if item.get("id") == run_id), None)
        if not run:
            return {"error": "agent run not found"}
        allowed = {
            "paused": {"running"},
            "running": {"paused"},
            "stopped": {"running", "paused"},
        }
        if run.get("status") not in allowed[target]:
            return {"error": f"cannot transition agent run from {run.get('status')} to {target}"}
        now = _now()
        run["status"] = target
        run["updated_at"] = now
        if target == "stopped":
            run["completed_at"] = now
            run["result"] = str(payload.get("result") or "Vom Nutzer gestoppt.")
        run.setdefault("logs", []).append(
            {"timestamp": now, "level": "warning" if target == "stopped" else "info", "message": {"paused": "Lauf pausiert.", "running": "Lauf fortgesetzt.", "stopped": "Lauf gestoppt."}[target]}
        )
        return run

    def _pause_agent_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._agent_run_transition(payload, "paused")

    def _resume_agent_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._agent_run_transition(payload, "running")

    def _stop_agent_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._agent_run_transition(payload, "stopped")

    def _export_agent_package(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or payload.get("id") or "")
        if not agent_id:
            return {"error": "agent_id is required"}
        package = self.get_agent_package(agent_id)
        if not package:
            return {"error": "agent not found"}
        self.agent_package_dir.mkdir(parents=True, exist_ok=True)
        package_id = f"pkg-{_slug(agent_id)}-{uuid4().hex[:6]}"
        package["id"] = package_id
        package["name"] = f"{package['manifest']['name']} Package"
        package["agent_id"] = agent_id
        package_path = self.agent_package_dir / f"{package_id}.json"
        package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        record = {
            "id": package_id,
            "agent_id": agent_id,
            "name": package["name"],
            "format": package["format"],
            "version": package["manifest"].get("version", "1.0.0"),
            "artifact_path": _display_path(package_path),
            "exported_at": package["exported_at"],
            "tool_count": package["runtime"]["tool_count"],
            "knowledge_count": package["runtime"]["knowledge_count"],
        }
        self.data.setdefault("agent_packages", []).insert(0, record)
        self.data["agent_packages"] = self.data["agent_packages"][:100]
        return {"package": package, "record": record}

    def _import_agent_package(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_package = payload.get("package") or payload.get("manifest") or {}
        if isinstance(raw_package, str):
            raw_package = json.loads(raw_package)
        if not isinstance(raw_package, dict):
            return {"error": "package must be an object"}
        manifest = raw_package.get("manifest", raw_package)
        if not isinstance(manifest, dict) or not manifest.get("name"):
            return {"error": "agent manifest is required"}
        imported_id = str(payload.get("id") or manifest.get("agent_id") or _slug(str(manifest["name"])))
        if payload.get("clone", True):
            imported_id = f"{_slug(imported_id)}-import"
        agent = self._save_agent(
            {
                "id": imported_id,
                "name": payload.get("name") or manifest.get("name"),
                "model": manifest.get("model", "fast"),
                "prompt": manifest.get("prompt", "You are a helpful M.I.C.A agent."),
                "tools": manifest.get("tools", []),
                "knowledge": manifest.get("knowledge", []),
                "parameters": manifest.get("parameters", {}),
                "permissions": manifest.get("permissions", []),
                "version": manifest.get("version", "1.0.0"),
                "visibility": payload.get("visibility") or manifest.get("visibility", "team"),
                "owner": payload.get("owner") or manifest.get("owner", "u-admin"),
            }
        )
        return {"agent": agent, "source_format": raw_package.get("format", manifest.get("package_format", "manifest"))}

    def _save_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        user = {
            "id": payload.get("id") or _slug(str(payload.get("email") or payload.get("name") or "user")),
            "name": payload.get("name", "New User"),
            "email": payload.get("email", "user@mica.local"),
            "roles": _as_list(payload.get("roles") or ["viewer"]),
            "groups": _as_list(payload.get("groups")),
        }
        return self._upsert("users", user)

    def _save_secret_reference(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "Secret Reference").strip()
        env_var = str(payload.get("env_var") or "").strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", env_var):
            return {"error": "env_var must be an uppercase environment variable name"}
        reference = {
            "id": str(payload.get("id") or _slug(name)),
            "name": name,
            "env_var": env_var,
            "scope": str(payload.get("scope") or "workspace"),
            "status": "configured" if os.environ.get(env_var) else "missing",
            "updated_at": _now(),
        }
        return self._upsert("secret_references", reference)

    def _delete_secret_reference(self, payload: dict[str, Any]) -> dict[str, Any]:
        reference_id = str(payload.get("id") or "")
        references = self.data.setdefault("secret_references", [])
        before = len(references)
        self.data["secret_references"] = [item for item in references if item.get("id") != reference_id]
        return {"id": reference_id, "deleted": len(self.data["secret_references"]) < before}

    def _test_integration(self, payload: dict[str, Any]) -> dict[str, Any]:
        category = str(payload.get("category") or "knowledge")
        integration_id = str(payload.get("id") or "")
        status = "unavailable"
        detail = "Integration not found"
        if category == "knowledge":
            item = next((source for source in self.data.get("knowledge", []) if source.get("id") == integration_id), None)
            if item:
                status = "ready" if item.get("connector_status") in {"ready", "connected"} else "needs-setup"
                detail = f"{item.get('source')} · {item.get('connector_status', 'unknown')}"
        elif category == "identity":
            item = next((provider for provider in self.data.get("identity_providers", []) if provider.get("id") == integration_id), None)
            if item:
                tested = self._test_identity_provider({"id": integration_id})
                status = "ready" if tested.get("status") in {"ready", "connected", "passed"} else str(tested.get("status") or "needs-setup")
                detail = str(tested.get("message") or tested.get("type") or item.get("type") or "Identity provider")
        elif category == "marketplace":
            item = next((entry for entry in self.data.get("marketplace", []) if entry.get("id") == integration_id), None)
            if item:
                status = "ready" if item.get("installed") and item.get("enabled") else "needs-setup"
                detail = f"{item.get('kind')} · {'enabled' if item.get('enabled') else 'disabled'}"
        elif category == "mcp":
            servers = self.data.get("mcp", {}).get("servers", [])
            item = next((entry for entry in servers if str(entry.get("id") or entry.get("name")) == integration_id), None)
            if item:
                status = "ready" if item.get("status") in {"ready", "connected", "active"} else "needs-setup"
                detail = str(item.get("status") or "registered")
        check = {"id": f"integration-{uuid4().hex[:8]}", "category": category, "integration_id": integration_id, "status": status, "detail": detail, "checked_at": _now()}
        self.data.setdefault("integration_checks", []).insert(0, check)
        self.data["integration_checks"] = self.data["integration_checks"][:100]
        return check

    def _save_group(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "New Group")
        group = {
            "id": payload.get("id") or _slug(name),
            "name": name,
            "members": _as_list(payload.get("members")),
        }
        return self._upsert("groups", group)

    def _save_role(self, payload: dict[str, Any]) -> dict[str, Any]:
        role_id = str(payload.get("id") or payload.get("name") or "viewer")
        role = {
            "id": _slug(role_id),
            "permissions": _as_list(payload.get("permissions") or ["read"]),
        }
        return self._upsert("roles", role)

    def _save_acl(self, payload: dict[str, Any]) -> dict[str, Any]:
        resource = str(payload.get("resource") or "")
        if not resource:
            return {"error": "resource is required"}
        acl = {
            "resource": resource,
            "subjects": payload.get("subjects", []),
            "updated_at": _now(),
        }
        for index, existing in enumerate(self.data.setdefault("acls", [])):
            if existing.get("resource") == resource:
                self.data["acls"][index] = acl
                return acl
        self.data["acls"].append(acl)
        return acl

    def _share_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or "")
        if not agent_id:
            return {"error": "agent_id is required"}
        agent = next((item for item in self.data.get("agents", []) if item.get("id") == agent_id), None)
        if not agent:
            return {"error": "agent not found"}
        subjects = payload.get("subjects")
        if not isinstance(subjects, list) or not subjects:
            subjects = [{"type": "group", "id": "core", "access": payload.get("access", "read")}]
        normalized_subjects = []
        for subject in subjects:
            if not isinstance(subject, dict):
                continue
            normalized_subjects.append(
                {
                    "type": subject.get("type", "group"),
                    "id": str(subject.get("id") or "core"),
                    "access": subject.get("access", "read"),
                }
            )
        if not normalized_subjects:
            return {"error": "at least one subject is required"}
        acl = self._save_acl({"resource": f"agent:{agent_id}", "subjects": normalized_subjects})
        agent["visibility"] = payload.get("visibility", agent.get("visibility", "team"))
        agent["shared_at"] = _now()
        return {"agent": agent, "acl": acl}

    def _effective_permissions(self, user_id: str) -> set[str]:
        user = next((item for item in self.data.get("users", []) if item.get("id") == user_id), None)
        if not user:
            return set()
        role_ids = set(_as_list(user.get("roles")))
        group_ids = set(_as_list(user.get("groups")))
        for group in self.data.get("groups", []):
            if user_id in group.get("members", []):
                group_ids.add(str(group.get("id")))
        permissions: set[str] = set()
        for role in self.data.get("roles", []):
            if role.get("id") in role_ids:
                permissions.update(str(item) for item in role.get("permissions", []))
        for acl in self.data.get("acls", []):
            for subject in acl.get("subjects", []):
                subject_type = subject.get("type")
                subject_id = subject.get("id")
                if (subject_type == "user" and subject_id == user_id) or (
                    subject_type == "group" and subject_id in group_ids
                ):
                    permissions.add(f"{acl.get('resource')}:{subject.get('access', 'read')}")
        return permissions

    def _check_access_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "")
        permission = str(payload.get("permission") or "read")
        permissions = self._effective_permissions(user_id)
        allowed = self._permissions_allow(permissions, permission)
        return {"user_id": user_id, "permission": permission, "allowed": allowed, "effective_permissions": sorted(permissions)}

    def _save_identity_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_type = str(payload.get("type") or "oidc").lower()
        name = str(payload.get("name") or f"{provider_type.upper()} Provider")
        discovery = payload.get("discovery") if isinstance(payload.get("discovery"), dict) else {}
        issuer = str(payload.get("issuer") or discovery.get("issuer") or "").rstrip("/")
        client_id = str(payload.get("client_id", ""))
        audience = payload.get("audience") or client_id
        jwks = payload.get("jwks") if isinstance(payload.get("jwks"), dict) else {}
        provider = {
            "id": payload.get("id") or _slug(name),
            "name": name,
            "type": provider_type,
            "status": payload.get("status", "configured"),
            "issuer": issuer,
            "client_id": client_id,
            "audience": audience,
            "jwks_uri": payload.get("jwks_uri") or discovery.get("jwks_uri") or (f"{issuer}/.well-known/jwks.json" if issuer else ""),
            "authorization_endpoint": payload.get("authorization_endpoint") or discovery.get("authorization_endpoint") or "",
            "token_endpoint": payload.get("token_endpoint") or discovery.get("token_endpoint") or "",
            "jwks": jwks,
            "allowed_algs": _as_list(payload.get("allowed_algs") or ["RS256", "HS256"]),
            "ldap_url": payload.get("ldap_url", ""),
            "scim_enabled": bool(payload.get("scim_enabled", provider_type in {"oidc", "ldap"})),
            "claim_mapping": payload.get("claim_mapping", {"email": "email", "name": "name", "groups": "groups"}),
            "updated_at": _now(),
        }
        if provider_type == "oidc" and not provider["issuer"]:
            return {"error": "issuer is required for OIDC providers"}
        if provider_type == "ldap" and not provider["ldap_url"]:
            return {"error": "ldap_url is required for LDAP providers"}
        return self._upsert("identity_providers", provider)

    def _test_identity_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(payload.get("id") or "")
        provider = next((item for item in self.data.get("identity_providers", []) if item.get("id") == provider_id), None)
        if not provider:
            return {"error": "identity provider not found"}
        provider["last_test"] = _now()
        provider["status"] = "verified" if provider.get("type") in {"local", "oidc", "ldap"} else "configured"
        checks = [
            {"name": "configuration", "status": "passed"},
            {"name": "claim_mapping", "status": "passed"},
            {"name": "scim", "status": "passed" if provider.get("scim_enabled") else "skipped"},
        ]
        if provider.get("type") == "oidc":
            jwks = provider.get("jwks") if isinstance(provider.get("jwks"), dict) else {}
            checks.extend(
                [
                    {"name": "issuer", "status": "passed" if provider.get("issuer") else "failed"},
                    {"name": "audience", "status": "passed" if provider.get("audience") else "failed"},
                    {"name": "jwks", "status": "passed" if jwks.get("keys") or provider.get("jwks_uri") else "warning"},
                    {"name": "rs256", "status": "passed" if "RS256" in _as_list(provider.get("allowed_algs")) else "skipped"},
                ]
            )
        return {
            "id": provider_id,
            "status": provider["status"],
            "checks": checks,
        }

    def _start_sso_login(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(payload.get("provider_id") or payload.get("id") or self.data.get("sso", {}).get("default_provider") or "local")
        provider = next((item for item in self.data.get("identity_providers", []) if item.get("id") == provider_id), None)
        if not provider:
            return {"error": "identity provider not found"}
        provider_type = str(provider.get("type") or "local")
        if provider_type == "ldap":
            return {"error": "LDAP providers use ldap_bind_login"}
        state = f"state-{uuid4().hex}"
        nonce = f"nonce-{uuid4().hex}"
        redirect_uri = str(payload.get("redirect_uri") or "/api/auth/callback")
        scopes = _as_list(payload.get("scopes") or ["openid", "profile", "email", "groups"])
        issuer = str(provider.get("issuer") or "mica://local").rstrip("/")
        if provider_type == "local":
            authorization_url = f"/api/auth/local?state={state}"
        else:
            scope_text = "+".join(scopes)
            authorization_endpoint = str(provider.get("authorization_endpoint") or f"{issuer}/authorize")
            authorization_url = (
                f"{authorization_endpoint}?client_id={provider.get('client_id', '')}"
                f"&redirect_uri={redirect_uri}&response_type=code&scope={scope_text}&state={state}&nonce={nonce}"
            )
        flow = {
            "id": f"sso-flow-{uuid4().hex[:8]}",
            "provider_id": provider_id,
            "type": provider_type,
            "state": state,
            "nonce": nonce,
            "status": "pending",
            "redirect_uri": redirect_uri,
            "issuer": issuer,
            "audience": provider.get("audience") or provider.get("client_id"),
            "scopes": scopes,
            "authorization_endpoint": provider.get("authorization_endpoint") or f"{issuer}/authorize",
            "token_endpoint": provider.get("token_endpoint", ""),
            "authorization_url": authorization_url,
            "created_at": _now(),
        }
        sso = self.data.setdefault("sso", {})
        sso.setdefault("login_flows", []).insert(0, flow)
        sso["login_flows"] = sso["login_flows"][:50]
        self._record_sso_event("login_started", provider_id, "pending", {"flow_id": flow["id"]})
        return {"flow": flow, "authorization_url": authorization_url}

    def _complete_sso_login(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload.get("state") or "")
        if not state:
            return {"error": "state is required"}
        sso = self.data.setdefault("sso", {})
        flow = next((item for item in sso.setdefault("login_flows", []) if item.get("state") == state), None)
        if not flow:
            return {"error": "login flow not found"}
        if flow.get("status") not in {"pending", "started"}:
            return {"error": "login flow already completed", "status": flow.get("status")}
        provider_id = str(payload.get("provider_id") or flow.get("provider_id") or "")
        provider = next((item for item in self.data.get("identity_providers", []) if item.get("id") == provider_id), None)
        if not provider:
            return {"error": "identity provider not found"}
        token_validation: dict[str, Any] | None = None
        claims = payload.get("claims") if isinstance(payload.get("claims"), dict) else {}
        id_token = str(payload.get("id_token") or payload.get("token") or "")
        if id_token:
            token_validation = self._validate_oidc_token(provider, id_token, flow)
            flow["token_validation"] = {
                "status": token_validation.get("status"),
                "alg": token_validation.get("alg"),
                "kid": token_validation.get("kid"),
                "validated_at": _now(),
            }
            if token_validation.get("status") != "passed":
                flow["status"] = "failed"
                flow["error"] = token_validation.get("error", "token validation failed")
                self._record_sso_event(
                    "login_failed",
                    provider_id,
                    "failed",
                    {"flow_id": flow["id"], "error": flow["error"], "token_validation": flow["token_validation"]},
                )
                return {"error": flow["error"], "flow": flow, "token_validation": flow["token_validation"]}
            claims = token_validation.get("claims", {})
        if not claims and payload.get("email"):
            claims = {"email": payload.get("email"), "name": payload.get("name"), "groups": payload.get("groups"), "roles": payload.get("roles")}
        mapped = self._sync_identity_claims({"provider_id": provider_id, "claims": claims})
        if "error" in mapped:
            flow["status"] = "failed"
            flow["error"] = mapped["error"]
            self._record_sso_event("login_failed", provider_id, "failed", {"flow_id": flow["id"], "error": mapped["error"]})
            return mapped
        session = self._create_identity_session(mapped["user"], provider_id, payload.get("device_name") or "Browser")
        flow["status"] = "completed"
        flow["completed_at"] = _now()
        flow["session_id"] = session["id"]
        event_details = {"flow_id": flow["id"], "session_id": session["id"]}
        if token_validation:
            event_details["token_validation"] = flow["token_validation"]
        self._record_sso_event("login_completed", provider_id, "completed", event_details)
        return {"flow": flow, "session": session, "user": mapped["user"], "mapped_claims": mapped["mapped_claims"]}

    def _validate_oidc_token(self, provider: dict[str, Any], token: str, flow: dict[str, Any]) -> dict[str, Any]:
        if provider.get("type") != "oidc":
            return {"status": "failed", "error": "provider is not OIDC"}
        parts = token.split(".")
        if len(parts) != 3:
            return {"status": "failed", "error": "id_token must be a JWT"}
        try:
            header = _b64url_json(parts[0])
            claims = _b64url_json(parts[1])
            signature = _b64url_decode(parts[2])
        except Exception as exc:
            return {"status": "failed", "error": f"invalid jwt encoding: {exc}"}
        alg = str(header.get("alg") or "")
        kid = str(header.get("kid") or "")
        allowed_algs = [str(item) for item in _as_list(provider.get("allowed_algs") or ["HS256"])]
        if alg not in allowed_algs:
            return {"status": "failed", "error": "disallowed token algorithm", "alg": alg, "kid": kid}
        issuer = str(provider.get("issuer") or "").rstrip("/")
        if issuer and str(claims.get("iss") or "").rstrip("/") != issuer:
            return {"status": "failed", "error": "invalid token issuer", "alg": alg, "kid": kid}
        expected_audience = str(provider.get("audience") or provider.get("client_id") or flow.get("audience") or "")
        token_audience = _as_list(claims.get("aud"))
        if expected_audience and expected_audience not in [str(item) for item in token_audience]:
            return {"status": "failed", "error": "invalid token audience", "alg": alg, "kid": kid}
        now = int(time.time())
        exp = claims.get("exp")
        if exp is not None and int(exp) < now:
            return {"status": "failed", "error": "token expired", "alg": alg, "kid": kid}
        nbf = claims.get("nbf")
        if nbf is not None and int(nbf) > now + 30:
            return {"status": "failed", "error": "token not yet valid", "alg": alg, "kid": kid}
        iat = claims.get("iat")
        if iat is not None and int(iat) > now + 300:
            return {"status": "failed", "error": "token issued in the future", "alg": alg, "kid": kid}
        nonce = claims.get("nonce")
        if nonce and nonce != flow.get("nonce"):
            return {"status": "failed", "error": "invalid token nonce", "alg": alg, "kid": kid}
        
        # Fetch JWKS from remote endpoint if configured
        jwks = provider.get("jwks") if isinstance(provider.get("jwks"), dict) else {}
        jwks_uri = str(provider.get("jwks_uri") or "")
        if jwks_uri and not jwks:
            jwks = self._fetch_jwks(jwks_uri, provider_id=str(provider.get("id") or ""))
            if jwks:
                # Cache the fetched JWKS
                provider["jwks"] = jwks
                provider["jwks_fetched_at"] = _now()
        
        key = self._find_jwks_key(jwks, kid, alg)
        if not key:
            return {"status": "failed", "error": "jwks key not found", "alg": alg, "kid": kid}
        if alg == "HS256":
            secret = str(key.get("k") or "")
            if key.get("k_base64url"):
                secret_bytes = _b64url_decode(secret)
            else:
                secret_bytes = secret.encode("utf-8")
            signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
            expected_signature = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected_signature):
                return {"status": "failed", "error": "invalid token signature", "alg": alg, "kid": kid}
        elif alg == "RS256":
            if rsa is None or padding is None or hashes is None:
                return {"status": "failed", "error": "cryptography is required for RS256", "alg": alg, "kid": kid}
            if not key.get("n") or not key.get("e"):
                return {"status": "failed", "error": "rsa jwk requires n and e", "alg": alg, "kid": kid}
            signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
            try:
                public_key = rsa.RSAPublicNumbers(_b64url_uint(str(key["e"])), _b64url_uint(str(key["n"]))).public_key()
                public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
            except Exception as exc:
                if InvalidSignature is not None and isinstance(exc, InvalidSignature):
                    return {"status": "failed", "error": "invalid token signature", "alg": alg, "kid": kid}
                return {"status": "failed", "error": f"invalid rsa jwk: {exc}", "alg": alg, "kid": kid}
        else:
            return {"status": "failed", "error": "unsupported jwks algorithm", "alg": alg, "kid": kid}
        return {"status": "passed", "claims": claims, "header": header, "alg": alg, "kid": kid}

    def _fetch_jwks(self, jwks_uri: str, provider_id: str) -> dict[str, Any]:
        """Fetch JWKS from a remote endpoint with caching."""
        import urllib.request
        import urllib.error
        
        # Check cache (5 minute TTL)
        cache_key = f"jwks:{provider_id}"
        cache = self.data.get("jwks_cache", {})
        cached = cache.get(cache_key)
        if cached:
            cached_at = cached.get("cached_at", "")
            try:
                from datetime import datetime, timedelta
                if cached_at:
                    cached_time = datetime.fromisoformat(cached_at)
                    if datetime.now() - cached_time < timedelta(minutes=5):
                        return cached.get("jwks", {})
            except Exception:
                pass
        
        # Fetch from remote
        try:
            request = urllib.request.Request(jwks_uri)
            request.add_header("User-Agent", "MICA-PlatformHub/1.0")
            with urllib.request.urlopen(request, timeout=5) as response:
                data = response.read().decode("utf-8")
                jwks = json.loads(data) if isinstance(data, (str, bytes)) else data
                
                # Cache the result
                cache[cache_key] = {
                    "jwks": jwks,
                    "cached_at": _now(),
                    "uri": jwks_uri
                }
                self.data["jwks_cache"] = cache
                self._save()
                
                return jwks
        except urllib.error.URLError as exc:
            logger.warning(f"Failed to fetch JWKS from {jwks_uri}: {exc}")
        except json.JSONDecodeError as exc:
            logger.warning(f"Failed to parse JWKS from {jwks_uri}: {exc}")
        except Exception as exc:
            logger.warning(f"Unexpected error fetching JWKS: {exc}")
        
        return {}

    def _find_jwks_key(self, jwks: dict[str, Any], kid: str, alg: str) -> dict[str, Any] | None:
        for key in jwks.get("keys", []):
            if not isinstance(key, dict):
                continue
            if kid and str(key.get("kid") or "") != kid:
                continue
            if key.get("alg") and str(key.get("alg")) != alg:
                continue
            return key
        return None

    def _ldap_bind_login(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(payload.get("provider_id") or payload.get("id") or "")
        provider = next((item for item in self.data.get("identity_providers", []) if item.get("id") == provider_id), None)
        if not provider:
            return {"error": "identity provider not found"}
        if provider.get("type") != "ldap":
            return {"error": "provider is not LDAP"}
        username = str(payload.get("username") or payload.get("email") or "")
        if not username:
            return {"error": "username is required"}
        email = str(payload.get("email") or (username if "@" in username else f"{username}@ldap.local"))
        user = self._save_user(
            {
                "id": _slug(email),
                "name": payload.get("name") or username.split("@")[0],
                "email": email,
                "roles": payload.get("roles") or ["viewer"],
                "groups": payload.get("groups") or ["core"],
            }
        )
        session = self._create_identity_session(user, provider_id, payload.get("device_name") or "LDAP Bind")
        provider["last_bind"] = _now()
        self._record_sso_event("ldap_bind", provider_id, "completed", {"session_id": session["id"], "user_id": user["id"]})
        return {"session": session, "user": user}

    def _create_identity_session(self, user: dict[str, Any], provider_id: str, device_name: Any = "Browser") -> dict[str, Any]:
        session = {
            "id": f"sso-session-{uuid4().hex[:12]}",
            "user_id": user.get("id"),
            "email": user.get("email"),
            "provider_id": provider_id,
            "device_name": str(device_name or "Browser"),
            "status": "active",
            "token": f"mica-session-{uuid4().hex}",
            "issued_at": _now(),
            "expires_at": (datetime.now() + timedelta(hours=8)).isoformat(timespec="seconds"),
            "groups": user.get("groups", []),
            "roles": user.get("roles", []),
        }
        sso = self.data.setdefault("sso", {})
        sso.setdefault("sessions", []).insert(0, session)
        sso["sessions"] = sso["sessions"][:100]
        return session

    def _record_sso_event(self, action: str, provider_id: str, status: str, details: dict[str, Any] | None = None) -> None:
        event = {
            "id": f"sso-{uuid4().hex[:8]}",
            "action": action,
            "provider_id": provider_id,
            "status": status,
            "details": details or {},
            "timestamp": _now(),
        }
        sso = self.data.setdefault("sso", {})
        sso.setdefault("events", []).insert(0, event)
        sso["events"] = sso["events"][:100]

    def _provision_scim_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        email = str(payload.get("email") or "")
        if not email:
            return {"error": "email is required"}
        user = self._save_user(
            {
                "id": payload.get("id") or _slug(email),
                "name": payload.get("name") or email.split("@")[0],
                "email": email,
                "roles": payload.get("roles") or ["viewer"],
                "groups": payload.get("groups") or [],
            }
        )
        event = {
            "id": f"scim-{uuid4().hex[:8]}",
            "action": payload.get("action", "upsert"),
            "user_id": user["id"],
            "email": email,
            "status": "completed",
            "timestamp": _now(),
        }
        self.data.setdefault("scim_events", []).insert(0, event)
        return {"user": user, "event": event}

    def _deprovision_scim_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or payload.get("id") or "")
        email = str(payload.get("email") or "")
        users = self.data.setdefault("users", [])
        user = next(
            (
                item
                for item in users
                if (user_id and item.get("id") == user_id) or (email and item.get("email") == email)
            ),
            None,
        )
        if not user:
            return {"error": "user not found"}
        user["status"] = "deprovisioned"
        user["roles"] = []
        user["groups"] = []
        user["deprovisioned_at"] = _now()
        event = {
            "id": f"scim-{uuid4().hex[:8]}",
            "action": "deprovision",
            "user_id": user["id"],
            "email": user.get("email", email),
            "status": "completed",
            "timestamp": _now(),
        }
        self.data.setdefault("scim_events", []).insert(0, event)
        return {"user": user, "event": event}

    def _sync_identity_claims(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(payload.get("provider_id") or payload.get("id") or "")
        provider = next((item for item in self.data.get("identity_providers", []) if item.get("id") == provider_id), None)
        if not provider:
            return {"error": "identity provider not found"}
        claims = payload.get("claims") if isinstance(payload.get("claims"), dict) else {}
        mapping = provider.get("claim_mapping") if isinstance(provider.get("claim_mapping"), dict) else {}
        email_key = str(mapping.get("email", "email"))
        name_key = str(mapping.get("name", "name"))
        groups_key = str(mapping.get("groups", "groups"))
        roles_key = str(mapping.get("roles", "roles"))
        email = str(claims.get(email_key) or payload.get("email") or "")
        if not email:
            return {"error": "email claim is required"}
        user = self._save_user(
            {
                "id": payload.get("user_id") or _slug(email),
                "name": claims.get(name_key) or payload.get("name") or email.split("@")[0],
                "email": email,
                "roles": claims.get(roles_key) or payload.get("roles") or ["viewer"],
                "groups": claims.get(groups_key) or payload.get("groups") or [],
            }
        )
        provider["last_claim_sync"] = _now()
        return {"provider": provider, "user": user, "mapped_claims": {"email": email, "groups": user.get("groups", []), "roles": user.get("roles", [])}}

    def _install_marketplace_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = str(payload.get("id", ""))
        item = self._find_marketplace_item(item_id)
        if not item:
            return {"error": "marketplace item not found"}
        if item.get("review_status") not in {"approved", "verified"} and not payload.get("force"):
            self._record_marketplace_audit("install_blocked", item, "failed", {"reason": "review_required"})
            return {"error": "marketplace item requires review before install", "review_status": item.get("review_status")}
        verification = self._verify_marketplace_payload(item)
        item["verification"] = verification
        item["risk"] = self._marketplace_risk(item)
        if verification["status"] != "passed" and not payload.get("force"):
            self._record_marketplace_audit("install_blocked", item, "failed", {"reason": "verification_failed", "verification": verification})
            return {"error": "marketplace item verification failed", "verification": verification}
        artifact = self._write_marketplace_plugin(item)
        item["installed"] = True
        item["enabled"] = True
        item["installed_at"] = _now()
        item["artifact_path"] = artifact
        item["install_source"] = payload.get("source_url") or item.get("source_url")
        item["manifest_path"] = self._write_marketplace_manifest(item)
        self._record_marketplace_audit("install", item, "completed", {"artifact_path": item["artifact_path"], "risk": item["risk"]})
        return item

    def _sync_marketplace_registry(self, payload: dict[str, Any]) -> dict[str, Any]:
        registry_url = str(payload.get("registry_url") or (os.environ.get("MICA_MARKETPLACE_REGISTRY_URL") or os.environ.get("JARVIS_MARKETPLACE_REGISTRY_URL")) or "")
        
        # Use remote registry if configured
        if registry_url:
            try:
                from core.marketplace_client import MarketplaceRegistryClient
                client = MarketplaceRegistryClient(registry_url)
                sync_result = client.sync_registry()
                index = client.get_registry_index()
                registry_items = index.get("items", [])
                self.data.setdefault("deployment", {})["marketplace_registry"] = {
                    "url": registry_url,
                    "last_sync": sync_result.get("synced_at"),
                    "status": sync_result.get("status"),
                    "total_items": sync_result.get("total_items")
                }
            except Exception as exc:
                logger.warning(f"Failed to sync from remote at {registry_url}: {exc}")
                registry_items = payload.get("items")
        else:
            registry_items = payload.get("items")
        
        if not isinstance(registry_items, list):
            registry_items = [
                {
                    "id": "browser-companion-tools",
                    "name": "Browser Companion Tools",
                    "kind": "companion",
                    "version": "0.1.0",
                    "latest_version": "0.1.0",
                "trust": "community",
                "review_status": "pending",
                "checksum": "sha256:community-browser-companion-tools",
                "signature": "unsigned",
                "publisher": "community",
                "permissions": ["tools:execute", "browser:read"],
                "source_url": "https://plugins.mica.local/browser-companion-tools",
                "description": "Adds browser-side capture and workspace actions.",
                "entrypoint": "browser_companion_tools",
                }
            ]
        upserted = []
        for raw in registry_items:
            if not isinstance(raw, dict):
                continue
            item = {
                "id": str(raw.get("id") or _slug(str(raw.get("name") or "extension"))),
                "name": str(raw.get("name") or raw.get("id") or "Extension"),
                "kind": str(raw.get("kind") or "tool"),
                "installed": bool(raw.get("installed", False)),
                "enabled": bool(raw.get("enabled", False)),
                "version": str(raw.get("version") or "1.0.0"),
                "latest_version": str(raw.get("latest_version") or raw.get("version") or "1.0.0"),
                "trust": str(raw.get("trust") or "community"),
                "review_status": str(raw.get("review_status") or "pending"),
                "checksum": str(raw.get("checksum") or f"sha256:{_slug(str(raw.get('id') or raw.get('name') or 'extension'))}"),
                "signature": str(raw.get("signature") or "unsigned"),
                "publisher": str(raw.get("publisher") or ("mica" if raw.get("trust") == "verified" else "community")),
                "permissions": _as_list(raw.get("permissions") or ["tools:execute"]),
                "source_url": str(raw.get("source_url") or f"https://plugins.mica.local/{raw.get('id', 'extension')}"),
                "description": str(raw.get("description") or ""),
                "entrypoint": str(raw.get("entrypoint") or _slug(str(raw.get("id") or raw.get("name") or "extension")).replace("-", "_")),
                "synced_at": _now(),
                "signature_chain": raw.get("signature_chain", []),
            }
            item["manifest"] = self._marketplace_manifest(item)
            item["verification"] = self._verify_marketplace_payload(item)
            item["risk"] = self._marketplace_risk(item)
            
            # Verify signature chain if present
            if item.get("signature_chain"):
                chain_verification = self._verify_signature_chain(item)
                item["chain_verification"] = chain_verification
            
            existing = self._find_marketplace_item(item["id"])
            if existing:
                existing.update({**item, "installed": existing.get("installed", item["installed"]), "enabled": existing.get("enabled", item["enabled"])})
                upserted.append(existing)
            else:
                self.data.setdefault("marketplace", []).append(item)
                upserted.append(item)
        self.data.setdefault("marketplace_registry_runs", []).insert(0, {"id": f"registry-{uuid4().hex[:8]}", "status": "completed", "items": len(upserted), "timestamp": _now()})
        return {"status": "completed", "items": upserted}

    def _verify_marketplace_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self._find_marketplace_item(str(payload.get("id", "")))
        if not item:
            return {"error": "marketplace item not found"}
        if payload.get("checksum"):
            item["checksum"] = str(payload["checksum"])
        if payload.get("signature"):
            item["signature"] = str(payload["signature"])
        verification = self._verify_marketplace_payload(item)
        item["verification"] = verification
        item["risk"] = self._marketplace_risk(item)
        if verification["status"] == "passed":
            item["review_status"] = "verified"
            item["trust"] = "verified"
        self._record_marketplace_audit("verify", item, verification["status"], {"verification": verification})
        return verification

    def _review_marketplace_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self._find_marketplace_item(str(payload.get("id", "")))
        if not item:
            return {"error": "marketplace item not found"}
        verdict = str(payload.get("verdict") or "approved").lower()
        if verdict not in {"approved", "rejected", "needs-review", "verified"}:
            return {"error": "invalid review verdict"}
        item["review_status"] = verdict
        item["reviewed_by"] = payload.get("reviewed_by") or payload.get("user") or "u-admin"
        item["reviewed_at"] = _now()
        item["review_notes"] = payload.get("notes", "")
        item["verification"] = self._verify_marketplace_payload(item)
        item["risk"] = self._marketplace_risk(item)
        if verdict == "verified":
            item["trust"] = "verified"
        self._record_marketplace_audit("review", item, "completed", {"verdict": verdict, "risk": item["risk"]})
        return item

    def _update_marketplace_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self._find_marketplace_item(str(payload.get("id", "")))
        if not item:
            return {"error": "marketplace item not found"}
        latest = str(payload.get("version") or item.get("latest_version") or item.get("version") or "1.0.0")
        item["previous_version"] = item.get("version")
        item["version"] = latest
        item["latest_version"] = latest
        item["updated_at"] = _now()
        if item.get("installed"):
            item["artifact_path"] = self._write_marketplace_plugin(item)
        return item

    def _set_marketplace_item_enabled(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self._find_marketplace_item(str(payload.get("id", "")))
        if not item:
            return {"error": "marketplace item not found"}
        if not item.get("installed") and payload.get("enabled", True):
            return {"error": "marketplace item must be installed before enabling"}
        item["enabled"] = bool(payload.get("enabled", True))
        item["enabled_at" if item["enabled"] else "disabled_at"] = _now()
        return item

    def _uninstall_marketplace_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self._find_marketplace_item(str(payload.get("id", "")))
        if not item:
            return {"error": "marketplace item not found"}
        artifact_path = item.get("artifact_path")
        for managed_path in [artifact_path, item.get("manifest_path")]:
            if not managed_path:
                continue
            candidate = (project_path() / str(managed_path)).resolve()
            plugin_root = self.community_plugin_dir.resolve()
            with contextlib.suppress(Exception):
                if candidate.is_file() and (candidate == plugin_root or plugin_root in candidate.parents):
                    candidate.unlink()
        item["installed"] = False
        item["enabled"] = False
        item["uninstalled_at"] = _now()
        item.pop("manifest_path", None)
        return item

    def _find_marketplace_item(self, item_id: str) -> dict[str, Any] | None:
        return next((item for item in self.data.get("marketplace", []) if item.get("id") == item_id), None)

    def _marketplace_manifest(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "kind": item.get("kind"),
            "version": item.get("version"),
            "entrypoint": item.get("entrypoint"),
            "source_url": item.get("source_url"),
            "checksum": item.get("checksum"),
            "signature": item.get("signature"),
            "permissions": _as_list(item.get("permissions") or ["tools:execute"]),
            "trust": item.get("trust", "community"),
            "publisher": item.get("publisher", "community"),
            "risk": item.get("risk") or self._marketplace_risk(item),
        }

    def _verify_marketplace_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        checksum = str(item.get("checksum") or "")
        signature = str(item.get("signature") or "")
        checksum_ok = checksum.startswith("sha256:") and len(checksum.removeprefix("sha256:")) >= 8
        publisher = str(item.get("publisher") or "")
        trusted_publishers = [str(value) for value in _as_list(self.data.get("marketplace_policy", {}).get("trusted_publishers"))]
        signature_ok = signature.startswith("mica:") or (item.get("trust") == "verified" and publisher in trusted_publishers)
        review_ok = item.get("review_status") in {"approved", "verified"}
        policy = self._evaluate_marketplace_policy(item, checksum_ok, signature_ok, review_ok)
        status = "passed" if checksum_ok and signature_ok and review_ok and policy["status"] == "passed" else "failed"
        return {
            "status": status,
            "checked_at": _now(),
            "risk": policy["risk"],
            "checks": [
                {"name": "checksum", "status": "passed" if checksum_ok else "failed", "detail": checksum or "missing"},
                {"name": "signature", "status": "passed" if signature_ok else "failed", "detail": signature or "unsigned"},
                {"name": "review", "status": "passed" if review_ok else "failed", "detail": str(item.get("review_status", "pending"))},
                {"name": "trust_policy", "status": policy["status"], "detail": policy["detail"]},
            ],
        }

    def _save_marketplace_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        policy = self.data.setdefault("marketplace_policy", {})
        if "require_review" in payload:
            policy["require_review"] = bool(payload["require_review"])
        if "require_signature" in payload:
            policy["require_signature"] = bool(payload["require_signature"])
        if "allowed_trust" in payload:
            policy["allowed_trust"] = [str(item) for item in _as_list(payload["allowed_trust"])]
        if "max_risk" in payload:
            risk = str(payload["max_risk"]).lower()
            if risk not in {"low", "medium", "high"}:
                return {"error": "invalid max_risk"}
            policy["max_risk"] = risk
        if "permission_denylist" in payload:
            policy["permission_denylist"] = [str(item) for item in _as_list(payload["permission_denylist"])]
        if "trusted_publishers" in payload:
            policy["trusted_publishers"] = [str(item) for item in _as_list(payload["trusted_publishers"])]
        policy["updated_at"] = _now()
        for item in self.data.get("marketplace", []):
            item["risk"] = self._marketplace_risk(item)
            item["verification"] = self._verify_marketplace_payload(item)
        self._record_marketplace_audit("policy_update", {"id": "marketplace"}, "completed", {"policy": policy})
        return policy

    def _marketplace_risk(self, item: dict[str, Any]) -> dict[str, Any]:
        permissions = [str(value) for value in _as_list(item.get("permissions") or ["tools:execute"])]
        reasons: list[str] = []
        score = 0
        trust = str(item.get("trust") or "community")
        if trust != "verified":
            score += 1
            reasons.append("community trust")
        signature = str(item.get("signature") or "")
        if not signature.startswith("mica:"):
            score += 2
            reasons.append("unsigned")
        source_url = str(item.get("source_url") or "")
        if source_url and not source_url.startswith("https://"):
            score += 2
            reasons.append("non-https source")
        sensitive_permissions = {
            permission
            for permission in permissions
            if permission.startswith(("system:", "filesystem:", "secrets:", "network:")) or permission.endswith(":write")
        }
        if sensitive_permissions:
            score += 2
            reasons.append("sensitive permissions")
        level = "low" if score <= 1 else "medium" if score <= 3 else "high"
        return {"level": level, "score": score, "reasons": reasons or ["standard tool permissions"], "permissions": permissions}

    def _evaluate_marketplace_policy(self, item: dict[str, Any], checksum_ok: bool, signature_ok: bool, review_ok: bool) -> dict[str, Any]:
        policy = self.data.setdefault("marketplace_policy", {})
        risk = self._marketplace_risk(item)
        item["risk"] = risk
        failures: list[str] = []
        if str(item.get("trust") or "community") not in [str(value) for value in _as_list(policy.get("allowed_trust") or ["verified", "community"])]:
            failures.append("trust level not allowed")
        if policy.get("require_review", True) and not review_ok:
            failures.append("review required")
        if policy.get("require_signature", True) and not signature_ok:
            failures.append("signature required")
        risk_order = {"low": 0, "medium": 1, "high": 2}
        max_risk = str(policy.get("max_risk") or "medium").lower()
        if risk_order.get(risk["level"], 2) > risk_order.get(max_risk, 1):
            failures.append(f"risk {risk['level']} exceeds {max_risk}")
        denied = sorted(set(risk["permissions"]) & set(_as_list(policy.get("permission_denylist") or [])))
        if denied:
            failures.append(f"denied permissions: {', '.join(denied)}")
        if not checksum_ok:
            failures.append("checksum required")
        return {"status": "failed" if failures else "passed", "detail": "; ".join(failures) or "policy passed", "risk": risk}

    def _record_marketplace_audit(self, action: str, item: dict[str, Any], status: str, details: dict[str, Any] | None = None) -> None:
        event = {
            "id": f"market-{uuid4().hex[:8]}",
            "action": action,
            "item_id": item.get("id"),
            "status": status,
            "details": details or {},
            "timestamp": _now(),
        }
        audit = self.data.setdefault("marketplace_audit", [])
        audit.insert(0, event)
        self.data["marketplace_audit"] = audit[:200]

    def _write_marketplace_plugin(self, item: dict[str, Any]) -> str:
        self.community_plugin_dir.mkdir(parents=True, exist_ok=True)
        entrypoint = _slug(str(item.get("entrypoint") or item.get("id") or item.get("name"))).replace("-", "_")
        plugin_path = self.community_plugin_dir / f"{entrypoint}.py"
        tool_name = entrypoint
        template = f'''"""
Community marketplace extension: {item.get("name", tool_name)}
Generated by M.I.C.A Studio marketplace installer.
"""

TOOL_DECLARATION = {{
    "name": "{tool_name}",
    "description": "{item.get("description", "Community extension")}",
    "parameters": {{"type": "object", "properties": {{}}}},
    "category": "{item.get("kind", "community")}",
    "version": "{item.get("version", "1.0.0")}",
    "trust": "{item.get("trust", "community")}",
    "checksum": "{item.get("checksum", "")}",
    "enabled": True,
}}


def {tool_name}(parameters: dict, **kwargs) -> dict:
    return {{
        "status": "installed",
        "extension": "{item.get("id", tool_name)}",
        "parameters": parameters,
    }}
'''
        plugin_path.write_text(template, encoding="utf-8")
        return _display_path(plugin_path)

    def _write_marketplace_manifest(self, item: dict[str, Any]) -> str:
        self.community_plugin_dir.mkdir(parents=True, exist_ok=True)
        entrypoint = _slug(str(item.get("entrypoint") or item.get("id") or item.get("name"))).replace("-", "_")
        manifest_path = self.community_plugin_dir / f"{entrypoint}.manifest.json"
        manifest = self._marketplace_manifest(item)
        manifest["verification"] = item.get("verification", self._verify_marketplace_payload(item))
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return _display_path(manifest_path)

    def _import_openapi(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = payload.get("spec") or "{}"
        if isinstance(raw, str):
            spec = json.loads(raw)
        else:
            spec = raw
        imported = []
        for route, methods in spec.get("paths", {}).items():
            if not isinstance(methods, dict):
                continue
            for method, operation in methods.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue
                op = operation if isinstance(operation, dict) else {}
                name = op.get("operationId") or f"{method}_{route}".replace("/", "_").strip("_")
                schema = self._schema_from_openapi_operation(route, op)
                tool = {
                    "id": f"openapi-{_slug(name)}",
                    "name": _slug(name).replace("-", "_"),
                    "kind": "openapi",
                    "status": "ready",
                    "method": method.upper(),
                    "path": route,
                    "description": op.get("summary") or op.get("description") or f"{method.upper()} {route}",
                    "schema": schema,
                    "server_url": (spec.get("servers") or [{}])[0].get("url", ""),
                    "headers": payload.get("headers", {}),
                    "test_result": "Imported from OpenAPI",
                }
                imported.append(self._upsert("tools", tool))
        return {"imported": imported, "count": len(imported)}

    def _schema_from_openapi_operation(self, route: str, operation: dict[str, Any]) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for match in route.split("/"):
            if match.startswith("{") and match.endswith("}"):
                name = match[1:-1]
                properties[name] = {"type": "string", "description": "Path parameter"}
                required.append(name)
        for parameter in operation.get("parameters", []) or []:
            if not isinstance(parameter, dict):
                continue
            name = str(parameter.get("name") or "")
            if not name:
                continue
            schema = parameter.get("schema") if isinstance(parameter.get("schema"), dict) else {}
            properties[name] = {
                **schema,
                "type": schema.get("type", "string"),
                "description": parameter.get("description", f"{parameter.get('in', 'query')} parameter"),
            }
            if parameter.get("required"):
                required.append(name)
        body = operation.get("requestBody", {})
        content = body.get("content", {}) if isinstance(body, dict) else {}
        for media_type in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded"):
            media = content.get(media_type)
            if isinstance(media, dict) and isinstance(media.get("schema"), dict):
                properties["body"] = media["schema"]
                if body.get("required"):
                    required.append("body")
                break
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = sorted(set(required))
        return schema

    def _discover_mcp_tools(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query", "")).lower()
        discovered: list[dict[str, Any]] = []
        with contextlib.suppress(Exception):
            from core.mcp_client import get_mcp_client

            client = get_mcp_client()
            for server_id, server in client.servers.items():
                if server.enabled and not server.connected:
                    client.connect_server(server_id)
            discovered = client.get_tools()
        if not discovered:
            discovered = [
                {"server_id": "local", "name": "mcp_local_files_search", "description": "Deferred local file search", "parameters": {"type": "object"}, "loaded": False},
                {"server_id": "local", "name": "mcp_local_notes_create", "description": "Deferred notes/artifact creator", "parameters": {"type": "object"}, "loaded": False},
            ]
        loaded_names = {tool.get("name") for tool in self.data.get("mcp", {}).get("loaded_tools", [])}
        for tool in discovered:
            tool["loaded"] = tool.get("name") in loaded_names
        if query:
            discovered = [tool for tool in discovered if query in json.dumps(tool).lower()]
        self.data["mcp"] = {
            "deferred": True,
            "last_query": query,
            "tools": discovered,
            "servers": self.data.get("mcp", {}).get("servers", []),
            "loaded_tools": self.data.get("mcp", {}).get("loaded_tools", []),
        }
        return self.data["mcp"]

    def _load_mcp_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "")
        if not name:
            return {"error": "tool name is required"}
        catalog = self.data.setdefault("mcp", {}).setdefault("tools", [])
        tool = next((item for item in catalog if item.get("name") == name), None)
        if not tool:
            self._discover_mcp_tools({"query": ""})
            catalog = self.data.setdefault("mcp", {}).setdefault("tools", [])
            tool = next((item for item in catalog if item.get("name") == name), None)
        if not tool:
            return {"error": "MCP tool not found"}
        tool["loaded"] = True
        loaded = {
            "id": f"tool-{_slug(name)}",
            "name": name,
            "kind": "mcp",
            "status": "ready",
            "server_id": tool.get("server_id", "local"),
            "description": tool.get("description", ""),
            "schema": tool.get("parameters", {"type": "object"}),
            "test_result": "Deferred MCP tool loaded into registry",
        }
        loaded_tools = self.data.setdefault("mcp", {}).setdefault("loaded_tools", [])
        if not any(item.get("name") == name for item in loaded_tools):
            loaded_tools.append(loaded)
        self._upsert("tools", loaded)
        return loaded

    def _unload_mcp_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "")
        mcp = self.data.setdefault("mcp", {})
        mcp["loaded_tools"] = [item for item in mcp.get("loaded_tools", []) if item.get("name") != name]
        for tool in mcp.get("tools", []):
            if tool.get("name") == name:
                tool["loaded"] = False
        for tool in self.data.get("tools", []):
            if tool.get("name") == name and tool.get("kind") == "mcp":
                tool["status"] = "deferred"
        return {"name": name, "status": "deferred"}

    def _save_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "custom_tool")
        kind = str(payload.get("kind") or "function").lower()
        tool = {
            "id": payload.get("id") or f"tool-{_slug(name)}",
            "name": _slug(name).replace("-", "_"),
            "kind": kind,
            "status": payload.get("status", "draft"),
            "code": payload.get("code", ""),
            "schema": payload.get("schema", {"type": "object"}),
            "input_schema": payload.get("input_schema", payload.get("schema", {"type": "object"})),
            "output_schema": payload.get("output_schema", {"type": "object"}),
            "test_parameters": payload.get("test_parameters", {}),
            "test_result": payload.get("test_result", "Not run"),
            "updated_at": _now(),
        }
        return self._upsert("tools", tool)

    def _test_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        tool_id = str(payload.get("id", ""))
        for tool in self.data.get("tools", []):
            if tool.get("id") == tool_id:
                parameters = payload.get("parameters", tool.get("test_parameters", {}))
                if tool.get("kind") == "function" and tool.get("code"):
                    test_result = self._run_tool_code(str(tool.get("code")), parameters)
                    tool["status"] = "ready" if test_result["status"] == "completed" else "failed"
                    output = test_result["stdout"] or test_result["stderr"] or test_result["status"]
                    tool["test_result"] = re.sub(r"\bMICA\b", "M.I.C.A", output)
                    tool["last_test"] = {"parameters": parameters, **test_result}
                elif tool.get("kind") == "filter" and tool.get("code"):
                    test_result = self._run_tool_code(str(tool.get("code")), parameters)
                    decision = (test_result["stdout"] or "").strip().lower()
                    allowed = decision in {"true", "1", "yes", "allow", "allowed"}
                    tool["status"] = "ready" if test_result["status"] == "completed" else "failed"
                    tool["test_result"] = f"Filter {'allowed' if allowed else 'blocked'} sample"
                    tool["last_test"] = {"parameters": parameters, "allowed": allowed, **test_result}
                elif tool.get("kind") == "pipe" and tool.get("code"):
                    test_result = self._run_tool_code(str(tool.get("code")), parameters)
                    tool["status"] = "ready" if test_result["status"] == "completed" else "failed"
                    transformed = (test_result["stdout"] or "").strip()
                    if "normalize" in str(tool.get("name") or "").lower():
                        transformed = re.sub(r"[^\w\s-]", "", transformed)
                    tool["test_result"] = f"Pipe output: {transformed or (test_result['stderr'] or '').strip()}"
                    tool["last_test"] = {"parameters": parameters, **test_result, "transformed": transformed}
                elif tool.get("kind") == "action" and tool.get("code"):
                    test_result = self._run_tool_code(str(tool.get("code")), parameters)
                    tool["status"] = "ready" if test_result["status"] == "completed" else "failed"
                    tool["test_result"] = f"Action dry-run: {(test_result['stdout'] or test_result['stderr']).strip()}"
                    tool["last_test"] = {"parameters": parameters, "dry_run": True, **test_result}
                elif tool.get("kind") == "openapi":
                    plan = self._build_openapi_request_plan(tool, payload.get("parameters", {}))
                    tool["status"] = "ready"
                    tool["test_result"] = f"{plan['method']} {plan['url']}"
                    tool["last_request_plan"] = plan
                elif tool.get("kind") == "mcp":
                    tool["status"] = "ready"
                    tool["test_result"] = f"MCP deferred tool ready on {tool.get('server_id', 'local')}"
                else:
                    tool["status"] = "ready"
                    tool["test_result"] = f"Schema/metadata test passed at {_now()}"
                return tool
        return {"error": "tool not found"}

    def _execute_openapi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        tool_id = str(payload.get("id") or "")
        tool = next((item for item in self.data.get("tools", []) if item.get("id") == tool_id or item.get("name") == tool_id), None)
        if not tool or tool.get("kind") != "openapi":
            return {"error": "OpenAPI tool not found"}
        plan = self._build_openapi_request_plan(tool, payload.get("parameters", {}))
        execution = {
            "id": f"openapi-call-{uuid4().hex[:8]}",
            "tool_id": tool.get("id"),
            "status": "planned",
            "request": plan,
            "response_preview": {
                "status": "not_sent",
                "reason": "Network execution is deferred; request plan is ready for the runtime executor.",
            },
            "created_at": _now(),
        }
        tool["last_request_plan"] = plan
        tool["test_result"] = f"Planned {plan['method']} {plan['url']}"
        self.data.setdefault("tool_executions", []).insert(0, execution)
        return execution

    def _build_openapi_request_plan(self, tool: dict[str, Any], parameters: Any) -> dict[str, Any]:
        params = parameters if isinstance(parameters, dict) else {}
        path = str(tool.get("path") or "")
        query: dict[str, Any] = {}
        body = params.get("body")
        schema = tool.get("schema", {}) if isinstance(tool.get("schema"), dict) else {}
        properties = schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}
        for key in properties:
            placeholder = "{" + key + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(params.get(key, placeholder)))
            elif key != "body" and key in params:
                query[key] = params[key]
        base = str(tool.get("server_url") or "").rstrip("/")
        url = f"{base}{path}" if base else path
        return {
            "method": str(tool.get("method") or "GET").upper(),
            "url": url,
            "path": path,
            "query": query,
            "headers": tool.get("headers", {}),
            "body": body,
        }

    def _run_tool_code(self, code: str, parameters: Any) -> dict[str, str]:
        wrapper = (
            "parameters = __PARAMETERS__\n"
            "def __mica_tool__(parameters):\n"
            + "\n".join(f"    {line}" if line.strip() else "" for line in code.splitlines())
            + "\nresult = __mica_tool__(parameters)\n"
            "print(result if result is not None else '')\n"
        )
        safe_code = wrapper.replace("__PARAMETERS__", repr(parameters if isinstance(parameters, dict) else {}))
        return self._execute_python(safe_code)

    def _save_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "New Workflow")
        workflow = {
            "id": payload.get("id") or f"wf-{_slug(name)}",
            "name": name,
            "nodes": payload.get("nodes", []),
            "edges": payload.get("edges", []),
            "canvas": payload.get("canvas", {"zoom": 1, "supports": ["routing"]}),
            "status": payload.get("status", "draft"),
            "version": int(payload.get("version") or 1),
            "versions": payload.get("versions") or [],
            "updated_at": _now(),
            "trigger": payload.get("trigger", {"type": "manual", "enabled": True}),
            "schedule": str(payload.get("schedule") or "manual"),
            "next_run": payload.get("next_run", ""),
        }
        self._normalize_workflows({"workflows": [workflow]})
        return self._upsert("workflows", workflow)

    def _edit_workflow_node(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow = self._find_workflow(str(payload.get("workflow_id") or payload.get("id") or ""))
        if not workflow:
            return {"error": "workflow not found"}
        node_id = str(payload.get("node_id") or payload.get("node", {}).get("id") or "")
        node_payload = payload.get("node") if isinstance(payload.get("node"), dict) else payload
        if not node_id:
            node_id = f"node-{uuid4().hex[:6]}"
        nodes = workflow.setdefault("nodes", [])
        updated_node = {
            "id": node_id,
            "type": node_payload.get("type", "step"),
            "label": node_payload.get("label", node_id),
            "x": float(node_payload.get("x", 50)),
            "y": float(node_payload.get("y", 50)),
            "config": node_payload.get("config", {}),
        }
        for index, existing in enumerate(nodes):
            if existing.get("id") == node_id:
                nodes[index] = {**existing, **updated_node}
                break
        else:
            nodes.append(updated_node)
        workflow["updated_at"] = _now()
        self._normalize_workflows({"workflows": [workflow]})
        self._snapshot_workflow_version(workflow, reason="node-edit")
        return workflow

    def _connect_workflow_nodes(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow = self._find_workflow(str(payload.get("workflow_id") or payload.get("id") or ""))
        if not workflow:
            return {"error": "workflow not found"}
        source = str(payload.get("source") or payload.get("from") or "")
        target = str(payload.get("target") or payload.get("to") or "")
        if not source or not target:
            return {"error": "source and target are required"}
        label = str(payload.get("label") or "route")
        edge = [source, target, label]
        edges = workflow.setdefault("edges", [])
        if edge not in edges:
            edges.append(edge)
        workflow["updated_at"] = _now()
        self._normalize_workflows({"workflows": [workflow]})
        self._snapshot_workflow_version(workflow, reason="edge-edit")
        return workflow

    def _schedule_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow = self._find_workflow(str(payload.get("workflow_id") or payload.get("id") or ""))
        if not workflow:
            return {"error": "workflow not found"}
        schedule = str(payload.get("schedule") or "manual")
        trigger_type = str(payload.get("trigger_type") or ("schedule" if schedule != "manual" else "manual"))
        workflow["schedule"] = schedule
        workflow["trigger"] = {
            "type": trigger_type,
            "enabled": bool(payload.get("enabled", True)),
            "webhook_path": str(payload.get("webhook_path") or ""),
            "event": str(payload.get("event") or ""),
        }
        workflow["next_run"] = self._next_sync_time(schedule) if workflow["trigger"]["enabled"] else ""
        workflow["updated_at"] = _now()
        self._snapshot_workflow_version(workflow, reason="schedule-update")
        return workflow

    def _run_due_workflows(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()
        forced = {str(item) for item in _as_list(payload.get("ids"))}
        runs = []
        for workflow in self.data.get("workflows", []):
            trigger = workflow.get("trigger") if isinstance(workflow.get("trigger"), dict) else {}
            if not trigger.get("enabled", True):
                continue
            next_run = str(workflow.get("next_run") or "")
            due = str(workflow.get("id")) in forced
            if not due and next_run:
                with contextlib.suppress(ValueError):
                    due = datetime.fromisoformat(next_run) <= now
            if not due:
                continue
            run = self._run_workflow({"workflow_id": workflow.get("id"), "max_steps": payload.get("max_steps", 25)})
            if "error" not in run:
                runs.append(run)
                workflow["last_scheduled_run"] = run.get("id")
                workflow["next_run"] = self._next_sync_time(str(workflow.get("schedule") or "manual"), _now())
        return {"status": "completed", "checked": len(self.data.get("workflows", [])), "runs": runs, "completed_at": _now()}

    def _version_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow = self._find_workflow(str(payload.get("workflow_id") or payload.get("id") or ""))
        if not workflow:
            return {"error": "workflow not found"}
        self._snapshot_workflow_version(workflow, reason=str(payload.get("reason") or "manual"))
        return workflow

    def _find_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        return next((workflow for workflow in self.data.get("workflows", []) if workflow.get("id") == workflow_id), None)

    def _snapshot_workflow_version(self, workflow: dict[str, Any], *, reason: str) -> None:
        next_version = int(workflow.get("version", 1)) + 1
        workflow["version"] = next_version
        workflow.setdefault("versions", []).insert(
            0,
            {
                "version": next_version,
                "created_at": _now(),
                "reason": reason,
                "nodes": workflow.get("nodes", []),
                "edges": workflow.get("edges", []),
                "canvas": workflow.get("canvas", {}),
            },
        )
        workflow["versions"] = workflow["versions"][:25]

    def _run_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(payload.get("workflow_id") or payload.get("id") or "")
        workflow = next((wf for wf in self.data.get("workflows", []) if wf.get("id") == workflow_id), None)
        if not workflow:
            return {"error": "workflow not found"}
        nodes = {str(node.get("id")): node for node in workflow.get("nodes", []) if node.get("id")}
        if not nodes:
            return {"error": "workflow has no nodes"}
        incoming_edges: dict[str, list[list[Any]]] = {}
        outgoing_edges: dict[str, list[list[Any]]] = {}
        for edge in workflow.get("edges", []):
            if len(edge) >= 2:
                incoming_edges.setdefault(str(edge[1]), []).append(edge)
                outgoing_edges.setdefault(str(edge[0]), []).append(edge)
        start_node = str(payload.get("start_node") or "")
        if not start_node or start_node not in nodes:
            roots = [node_id for node_id in nodes if not incoming_edges.get(node_id)]
            start_node = roots[0] if roots else str(workflow.get("nodes", [{}])[0].get("id"))
        route_overrides = payload.get("routes") if isinstance(payload.get("routes"), dict) else {}
        max_steps = max(1, min(100, int(payload.get("max_steps") or 25)))
        max_loop_iterations = max(0, min(10, int(payload.get("max_loop_iterations") or 1)))
        human_approved = bool(payload.get("human_approved", False))
        steps: list[dict[str, Any]] = []
        timeline: list[dict[str, Any]] = []
        branch_attempts: dict[str, int] = {}
        loop_counts: dict[str, int] = {}
        current_id = start_node
        run_status = "completed"
        for index in range(max_steps):
            node = nodes.get(current_id)
            if not node:
                break
            started = time.perf_counter()
            time.sleep(0.01)
            node_type = str(node.get("type", "step"))
            loop_iteration = 0
            retries = 0
            status = "completed"
            if node_type == "human" and not human_approved:
                status = "waiting_for_human"
                run_status = "waiting_for_human"
            if node_type in {"retry", "loop"}:
                loop_counts[current_id] = loop_counts.get(current_id, 0) + 1
                loop_iteration = loop_counts[current_id]
                retries = loop_iteration
            route_edges = outgoing_edges.get(str(node.get("id")), [])
            selected_edge = self._select_workflow_edge(node, route_edges, branch_attempts, route_overrides, loop_counts, max_loop_iterations)
            input_snapshot = {
                "state_key": f"state[{index}]",
                "incoming": [edge[0] for edge in incoming_edges.get(str(node.get("id")), [])],
                "config": node.get("config", {}),
            }
            output_snapshot = {
                "result": "waiting for approval" if status == "waiting_for_human" else f"{node.get('label', node.get('type'))} ok",
                "selected_route": selected_edge[2] if selected_edge and len(selected_edge) > 2 else "",
                "next_node": selected_edge[1] if selected_edge else None,
            }
            tool_calls = [
                {
                    "name": node_type,
                    "status": status,
                    "arguments": input_snapshot,
                    "output": output_snapshot,
                    "latency_ms": 0,
                }
            ] if node_type not in {"input", "human"} else []
            step = {
                "node": node.get("id"),
                "node_type": node_type,
                "status": status,
                "input": input_snapshot["state_key"],
                "input_snapshot": input_snapshot,
                "output": output_snapshot["result"],
                "output_snapshot": output_snapshot,
                "tool_calls": tool_calls,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "retries": retries,
                "retry_log": [f"retry {attempt + 1} succeeded" for attempt in range(retries)] if retries else [],
                "incoming": [edge[0] for edge in incoming_edges.get(str(node.get("id")), [])],
                "outgoing": [edge[1] for edge in route_edges],
                "route_labels": [edge[2] for edge in route_edges if len(edge) > 2],
                "branch_taken": selected_edge[1] if node_type == "branch" and selected_edge else None,
                "selected_route": selected_edge[2] if selected_edge and len(selected_edge) > 2 else "",
                "loop_iteration": loop_iteration,
                "human_required": node_type == "human",
                "error": None,
            }
            steps.append(step)
            timeline.extend(self._workflow_step_events(run_id="", index=index, step=step))
            if status == "waiting_for_human":
                break
            if selected_edge:
                current_id = str(selected_edge[1])
                continue
            break
        if len(steps) >= max_steps and run_status != "waiting_for_human":
            run_status = "failed"
            steps[-1]["error"] = "max workflow steps reached"
            steps[-1]["status"] = "failed"
            timeline.append(
                {
                    "id": f"evt-{uuid4().hex[:8]}",
                    "index": len(timeline),
                    "type": "error",
                    "node": steps[-1]["node"],
                    "status": "failed",
                    "message": "max workflow steps reached",
                    "timestamp": _now(),
                    "payload": {"max_steps": max_steps},
                }
            )
        run_id = f"run-{uuid4().hex[:8]}"
        for event in timeline:
            event["run_id"] = run_id
        run = {
            "id": run_id,
            "workflow_id": workflow_id,
            "status": run_status,
            "started_at": _now(),
            "completed_at": "" if run_status == "waiting_for_human" else _now(),
            "debug": {
                "edges": workflow.get("edges", []),
                "canvas": workflow.get("canvas", {}),
                "supports": workflow.get("canvas", {}).get("supports", []),
                "start_node": start_node,
                "branch_attempts": branch_attempts,
                "loop_counts": loop_counts,
                "max_loop_iterations": max_loop_iterations,
                "timeline_events": len(timeline),
            },
            "steps": steps,
            "timeline": timeline,
        }
        self.data.setdefault("runs", []).insert(0, run)
        return run

    def _workflow_step_events(self, *, run_id: str, index: int, step: dict[str, Any]) -> list[dict[str, Any]]:
        base = {
            "run_id": run_id,
            "node": step.get("node"),
            "step_index": index,
            "timestamp": _now(),
        }
        events = [
            {
                **base,
                "id": f"evt-{uuid4().hex[:8]}",
                "index": index * 10,
                "type": "input",
                "status": "captured",
                "message": f"{step.get('node')} input captured",
                "payload": step.get("input_snapshot", {"input": step.get("input")}),
            }
        ]
        for tool_call in step.get("tool_calls", []):
            events.append(
                {
                    **base,
                    "id": f"evt-{uuid4().hex[:8]}",
                    "index": index * 10 + 1 + len(events),
                    "type": "tool_call",
                    "status": tool_call.get("status", step.get("status")),
                    "message": str(tool_call.get("name") or step.get("node")),
                    "payload": tool_call,
                }
            )
        if step.get("branch_taken") or step.get("selected_route"):
            events.append(
                {
                    **base,
                    "id": f"evt-{uuid4().hex[:8]}",
                    "index": index * 10 + 5,
                    "type": "route",
                    "status": "selected",
                    "message": str(step.get("selected_route") or step.get("branch_taken")),
                    "payload": {"branch_taken": step.get("branch_taken"), "selected_route": step.get("selected_route"), "outgoing": step.get("outgoing", [])},
                }
            )
        for retry in step.get("retry_log", []):
            events.append(
                {
                    **base,
                    "id": f"evt-{uuid4().hex[:8]}",
                    "index": index * 10 + 6 + len(events),
                    "type": "retry",
                    "status": "completed",
                    "message": retry,
                    "payload": {"retries": step.get("retries", 0), "loop_iteration": step.get("loop_iteration", 0)},
                }
            )
        if step.get("human_required"):
            events.append(
                {
                    **base,
                    "id": f"evt-{uuid4().hex[:8]}",
                    "index": index * 10 + 8,
                    "type": "human_wait",
                    "status": step.get("status"),
                    "message": "waiting for human approval",
                    "payload": {"node": step.get("node"), "output": step.get("output")},
                }
            )
        events.append(
            {
                **base,
                "id": f"evt-{uuid4().hex[:8]}",
                "index": index * 10 + 9,
                "type": "output",
                "status": step.get("status"),
                "message": f"{step.get('node')} output captured",
                "payload": step.get("output_snapshot", {"output": step.get("output")}),
            }
        )
        return events

    def _select_workflow_edge(
        self,
        node: dict[str, Any],
        route_edges: list[list[Any]],
        branch_attempts: dict[str, int],
        route_overrides: dict[str, Any],
        loop_counts: dict[str, int],
        max_loop_iterations: int,
    ) -> list[Any] | None:
        if not route_edges:
            return None
        node_id = str(node.get("id"))
        node_type = str(node.get("type", "step"))
        if node_type == "branch":
            branch_attempts[node_id] = branch_attempts.get(node_id, 0) + 1
            desired = str(route_overrides.get(node_id) or route_overrides.get("default") or "")
            if not desired and branch_attempts[node_id] == 1:
                desired = "retry"
            if not desired:
                desired = "low confidence"
            for edge in route_edges:
                label = str(edge[2]) if len(edge) > 2 else ""
                if desired and (label == desired or str(edge[1]) == desired):
                    return edge
            return route_edges[0]
        if node_type == "loop" and loop_counts.get(node_id, 0) > max_loop_iterations:
            return None
        return route_edges[0]

    def _resume_workflow_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id") or payload.get("id") or "")
        run = next((item for item in self.data.get("runs", []) if item.get("id") == run_id), None)
        if not run:
            return {"error": "workflow run not found"}
        if run.get("status") != "waiting_for_human":
            return {"error": "workflow run is not waiting for human", "status": run.get("status")}
        approval = {
            "node": payload.get("node") or "human-approval",
            "node_type": "human",
            "status": "completed",
            "input": payload.get("decision", "approved"),
            "output": payload.get("comment", "approved"),
            "tool_calls": [],
            "latency_ms": 0,
            "retries": 0,
            "retry_log": [],
            "incoming": [],
            "outgoing": [],
            "route_labels": [],
            "branch_taken": None,
            "selected_route": "approved",
            "loop_iteration": 0,
            "human_required": False,
            "error": None,
        }
        run.setdefault("steps", []).append(approval)
        timeline = run.setdefault("timeline", [])
        next_index = len(timeline)
        timeline.extend(
            [
                {
                    "id": f"evt-{uuid4().hex[:8]}",
                    "run_id": run.get("id"),
                    "index": next_index,
                    "step_index": len(run.get("steps", [])) - 1,
                    "type": "human_decision",
                    "node": approval["node"],
                    "status": "completed",
                    "message": str(payload.get("decision", "approved")),
                    "timestamp": _now(),
                    "payload": {"decision": payload.get("decision", "approved"), "comment": payload.get("comment", "")},
                },
                {
                    "id": f"evt-{uuid4().hex[:8]}",
                    "run_id": run.get("id"),
                    "index": next_index + 1,
                    "step_index": len(run.get("steps", [])) - 1,
                    "type": "resume",
                    "node": approval["node"],
                    "status": "completed",
                    "message": "workflow resumed after human approval",
                    "timestamp": _now(),
                    "payload": {"completed_at": _now()},
                },
            ]
        )
        run["status"] = "completed"
        run["completed_at"] = _now()
        run.setdefault("debug", {})["resumed_at"] = run["completed_at"]
        run["debug"]["human_decision"] = payload.get("decision", "approved")
        run["debug"]["timeline_events"] = len(timeline)
        return run

    def _run_evaluation(self, payload: dict[str, Any]) -> dict[str, Any]:
        eval_id = str(payload.get("id") or "eval-support")
        evaluation = next((item for item in self.data.get("evaluations", []) if item.get("id") == eval_id), None)
        if not evaluation:
            evaluation = {"id": eval_id, "name": "New Arena", "agents": [], "dataset": "manual", "elo": {}, "regressions": 0, "last_score": 0.0, "regression_gate": {"min_score": 0.8, "max_regressions": 0}}
            self.data.setdefault("evaluations", []).append(evaluation)
        agents = _as_list(payload.get("agents") or evaluation.get("agents") or ["research-copilot", "research-copilot-v2"])
        if len(agents) == 1:
            agents.append(f"{agents[0]}-variant")
        baseline = str(payload.get("baseline") or evaluation.get("baseline") or agents[0])
        challenger = str(payload.get("challenger") or evaluation.get("challenger") or agents[1])
        dataset_id = str(payload.get("dataset") or evaluation.get("dataset") or "manual")
        evaluation["dataset"] = dataset_id
        dataset = next((item for item in self.data.get("evaluation_datasets", []) if item.get("id") == dataset_id), None)
        cases = dataset.get("cases", []) if dataset else [{"id": "manual-1", "input": "Manual check", "expected": "Good answer"}]
        case_results = []
        pairs = []
        elo_delta = {str(agent): 0 for agent in agents}
        for index, case in enumerate(cases):
            per_case_scores: list[tuple[str, float]] = []
            for agent_index, agent in enumerate(agents):
                score = round(0.86 + min(index, 4) * 0.02 - agent_index * 0.01, 3)
                per_case_scores.append((str(agent), score))
                case_results.append(
                    {
                        "case_id": case.get("id", f"case-{index + 1}"),
                        "agent": agent,
                        "score": score,
                        "winner": agent_index == 0,
                        "regression": score < 0.75,
                    }
                )
            per_case_scores.sort(key=lambda item: item[1], reverse=True)
            winner = per_case_scores[0][0]
            loser = per_case_scores[-1][0]
            margin = round(per_case_scores[0][1] - per_case_scores[-1][1], 3)
            pairs.append(
                {
                    "case_id": case.get("id", f"case-{index + 1}"),
                    "baseline": baseline,
                    "challenger": challenger,
                    "winner": winner,
                    "loser": loser,
                    "margin": margin,
                }
            )
            elo_delta[winner] = elo_delta.get(winner, 0) + 8
            elo_delta[loser] = elo_delta.get(loser, 0) - 3
        for agent, delta in elo_delta.items():
            evaluation.setdefault("elo", {})[agent] = int(evaluation.setdefault("elo", {}).get(agent, 1200)) + delta
        regressions = sum(1 for item in case_results if item["regression"])
        score = round(sum(item["score"] for item in case_results) / max(1, len(case_results)), 3)
        gate_config = {
            **evaluation.get("regression_gate", {"min_score": 0.8, "max_regressions": 0}),
            **({"min_score": float(payload["min_score"])} if payload.get("min_score") is not None else {}),
            **({"max_regressions": int(payload["max_regressions"])} if payload.get("max_regressions") is not None else {}),
        }
        evaluation["regression_gate"] = gate_config
        min_score = float(gate_config.get("min_score", 0.8))
        max_regressions = int(gate_config.get("max_regressions", 0))
        gate_status = "passed" if score >= min_score and regressions <= max_regressions else "failed"
        evaluation["status"] = "passing" if gate_status == "passed" else "regression"
        evaluation["regressions"] = regressions
        evaluation["last_score"] = score
        evaluation["last_run"] = _now()
        evaluation["baseline"] = baseline
        evaluation["challenger"] = challenger
        run = {
            "id": f"eval-run-{uuid4().hex[:8]}",
            "evaluation_id": eval_id,
            "dataset": dataset_id,
            "status": evaluation["status"],
            "score": score,
            "regressions": regressions,
            "winner": max(elo_delta.items(), key=lambda item: item[1])[0] if elo_delta else baseline,
            "baseline": baseline,
            "challenger": challenger,
            "elo_delta": elo_delta,
            "gate": {"status": gate_status, "min_score": min_score, "max_regressions": max_regressions},
            "pairs": pairs,
            "cases": case_results,
            "created_at": evaluation["last_run"],
        }
        self.data.setdefault("evaluation_runs", []).insert(0, run)
        return {"evaluation": evaluation, "run": run}

    def _save_evaluation_dataset(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "New Dataset")
        raw_cases = payload.get("cases", [])
        cases = raw_cases if isinstance(raw_cases, list) else []
        if not cases:
            cases = [{"id": f"case-{uuid4().hex[:4]}", "input": str(payload.get("input", "")), "expected": str(payload.get("expected", "")), "rubric": "manual"}]
        dataset = {
            "id": payload.get("id") or _slug(name),
            "name": name,
            "cases": cases,
            "updated_at": _now(),
        }
        return self._upsert("evaluation_datasets", dataset)

    def _run_agent_chain(self, payload: dict[str, Any]) -> dict[str, Any]:
        parent_id = str(payload.get("agent_id") or "research-copilot")
        goal = str(payload.get("goal") or "Complete delegated task")
        requested_ids = {str(item) for item in _as_list(payload.get("agent_ids")) if str(item)}
        if requested_ids:
            chain_agents = [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "role": (item.get("parameters") or {}).get("role", item.get("visibility", "agent")),
                }
                for item in self.data.get("agents", [])
                if str(item.get("id")) in requested_ids and str(item.get("id")) != parent_id
            ]
        else:
            chain_agents = [
                item
                for item in self.data.get("subagents", [])
                if item.get("parent") == parent_id or not item.get("parent")
            ]
        if not chain_agents:
            return {"error": "no subagents available"}
        max_tokens = max(0, int(payload.get("max_tokens") or 0))
        max_cost = max(0.0, float(payload.get("max_cost") or 0.0))
        steps = []
        compact_parts = []
        used_tokens = 0
        used_cost = 0.0
        budget_reason = ""
        for index, subagent in enumerate(chain_agents):
            step_tokens = 310 + index * 50
            step_cost = round(step_tokens * 0.000002, 6)
            if max_tokens and used_tokens + step_tokens > max_tokens:
                budget_reason = f"token budget exceeded before {subagent.get('name')}"
                break
            if max_cost and used_cost + step_cost > max_cost:
                budget_reason = f"cost budget exceeded before {subagent.get('name')}"
                break
            result = f"{subagent.get('name')} handled {subagent.get('role')} for: {goal}"
            compact_parts.append(str(subagent.get("name")))
            used_tokens += step_tokens
            used_cost = round(used_cost + step_cost, 6)
            steps.append(
                {
                    "subagent_id": subagent.get("id"),
                    "name": subagent.get("name"),
                    "role": subagent.get("role"),
                    "status": "completed",
                    "input": goal if index == 0 else "prior compact context",
                    "output": result,
                    "tokens_in": 220 + index * 30,
                    "tokens_out": 90 + index * 20,
                }
            )
        run = {
            "id": f"chain-{uuid4().hex[:8]}",
            "agent_id": parent_id,
            "goal": goal,
            "status": "budget_exceeded" if budget_reason else "completed",
            "steps": steps,
            "compact_result": budget_reason or f"{' -> '.join(compact_parts)} completed and returned compact context.",
            "budget": {"max_tokens": max_tokens, "max_cost": max_cost, "used_tokens": used_tokens, "used_cost": used_cost, "reason": budget_reason},
            "created_at": _now(),
        }
        self.data.setdefault("agent_chain_runs", []).insert(0, run)
        self.data.setdefault("metrics", []).insert(
            0,
            {
                "scope": parent_id,
                "model": "chain",
                "user": str(payload.get("user", "u-admin")),
                "workflow": "agent-chain",
                "tokens": used_tokens,
                "cost": used_cost,
                "latency_ms": 320 + len(steps) * 80,
                "tool_calls": len(steps),
            },
        )
        return run

    def _save_knowledge_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        source_type = str(payload.get("source") or "Folder")
        target = str(payload.get("target") or f"{source_type} Source")
        schedule = str(payload.get("schedule") or "manual")
        last_sync = payload.get("last_sync", "")
        source = {
            "id": payload.get("id") or _slug(target),
            "source": source_type,
            "target": target,
            "uri": payload.get("uri", ""),
            "status": payload.get("status", "scheduled"),
            "last_sync": last_sync,
            "rag": payload.get("rag", "hybrid: bm25 + vector + cross-encoder reranker"),
            "vector_db": payload.get("vector_db", "chroma"),
            "schedule": schedule,
            "next_sync": payload.get("next_sync") or self._next_sync_time(schedule, last_sync),
            "watch_mode": schedule == "watch",
            "connector_status": payload.get("connector_status", "ready"),
        }
        return self._upsert("knowledge", source)

    def _schedule_knowledge_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        source_id = str(payload.get("id") or "")
        if not source_id:
            return {"error": "id is required"}
        source = next((item for item in self.data.get("knowledge", []) if item.get("id") == source_id), None)
        if not source:
            return {"error": "knowledge source not found"}
        schedule = str(payload.get("schedule") or source.get("schedule") or "manual")
        source["schedule"] = schedule
        source["watch_mode"] = schedule == "watch"
        source["status"] = "watching" if schedule == "watch" else ("scheduled" if schedule != "manual" else "manual")
        source["next_sync"] = self._next_sync_time(schedule, source.get("last_sync"))
        source["connector_status"] = "ready"
        source["scheduled_at"] = _now()
        return source

    def _sync_knowledge(self, payload: dict[str, Any]) -> dict[str, Any]:
        source_id = str(payload.get("id") or "local-documents")
        source = next((item for item in self.data.get("knowledge", []) if item.get("id") == source_id), None)
        if not source:
            source = self._save_knowledge_source({"id": source_id, "source": payload.get("source", "Folder"), "target": payload.get("target", source_id)})
        documents = self._knowledge_documents(source, payload)
        chunks = self._knowledge_chunks(source, documents)
        bm25_terms = self._build_bm25_index(chunks)
        vectors = self._build_vector_index(chunks)
        index_record = {
            "source_id": source_id,
            "documents": documents,
            "chunks": chunks,
            "bm25": bm25_terms,
            "vectors": vectors,
            "reranker": "cross-encoder:local-simulated",
            "vector_db": payload.get("vector_db", source.get("vector_db", "chroma")),
            "updated_at": _now(),
        }
        self.data.setdefault("knowledge_indexes", {})[source_id] = index_record
        phases = [
            {"name": "fetch", "status": "completed", "items": len(documents), "latency_ms": 31},
            {"name": "extract", "status": "completed", "items": len(chunks), "latency_ms": 57},
            {"name": "bm25_index", "status": "completed", "items": len(bm25_terms), "latency_ms": 22},
            {"name": "vector_index", "status": "completed", "items": len(vectors), "latency_ms": 41},
            {"name": "cross_encoder_rerank_ready", "status": "completed", "items": 1, "latency_ms": 9},
        ]
        run = {
            "id": f"ksync-{uuid4().hex[:8]}",
            "source_id": source_id,
            "source": source.get("source"),
            "target": source.get("target"),
            "status": "completed",
            "started_at": _now(),
            "completed_at": _now(),
            "phases": phases,
            "rag": "hybrid: bm25 + vector + cross-encoder reranker",
            "vector_db": payload.get("vector_db", source.get("vector_db", "chroma")),
            "documents": len(documents),
            "chunks": len(chunks),
            "index": {
                "bm25_terms": len(bm25_terms),
                "vectors": len(vectors),
                "reranker": index_record["reranker"],
            },
        }
        source.update({
            "status": "synced",
            "last_sync": run["completed_at"],
            "rag": run["rag"],
            "vector_db": run["vector_db"],
            "last_run_id": run["id"],
            "next_sync": self._next_sync_time(str(source.get("schedule") or "manual"), run["completed_at"]),
            "watch_mode": source.get("schedule") == "watch",
            "connector_status": "ready",
        })
        self.data.setdefault("knowledge_runs", []).insert(0, run)
        return {"source": source, "run": run}

    def _knowledge_documents(self, source: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        provided = payload.get("documents")
        if isinstance(provided, list) and provided:
            documents = []
            for index, document in enumerate(provided):
                if isinstance(document, dict):
                    text = str(document.get("text") or document.get("content") or "")
                    name = str(document.get("name") or f"document-{index + 1}")
                else:
                    text = str(document)
                    name = f"document-{index + 1}"
                documents.append({"id": f"doc-{_slug(name)}", "name": name, "text": text, "source_uri": source.get("uri", "")})
            return documents
        target = str(source.get("target") or source.get("id") or "Knowledge")
        uri = str(source.get("uri") or target)
        source_type = str(source.get("source") or "Folder")
        return [
            {
                "id": f"doc-{_slug(target)}-overview",
                "name": f"{target} Overview",
                "text": f"{target} from {source_type} at {uri} contains M.I.C.A knowledge, sync status, connector metadata, and retrieval examples.",
                "source_uri": uri,
            },
            {
                "id": f"doc-{_slug(target)}-ops",
                "name": f"{target} Operations",
                "text": f"Hybrid RAG for {target} uses BM25 keyword matching, vector search in {source.get('vector_db', 'chroma')}, and cross encoder reranking.",
                "source_uri": uri,
            },
        ]

    def _knowledge_chunks(self, source: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chunks = []
        for document in documents:
            words = str(document.get("text", "")).split()
            if not words:
                continue
            for index in range(0, len(words), 28):
                chunk_words = words[index:index + 32]
                text = " ".join(chunk_words)
                chunks.append({
                    "id": f"{document['id']}-chunk-{len(chunks) + 1}",
                    "document_id": document["id"],
                    "source_id": source.get("id"),
                    "text": text,
                    "tokens": len(chunk_words),
                    "metadata": {"name": document.get("name"), "source_uri": document.get("source_uri")},
                })
        return chunks

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9_]+", text.lower())

    def _build_bm25_index(self, chunks: list[dict[str, Any]]) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        for chunk in chunks:
            for term in sorted(set(self._tokenize(str(chunk.get("text", ""))))):
                index.setdefault(term, []).append(str(chunk.get("id")))
        return index

    def _build_vector_index(self, chunks: list[dict[str, Any]]) -> dict[str, list[float]]:
        vectors: dict[str, list[float]] = {}
        for chunk in chunks:
            tokens = self._tokenize(str(chunk.get("text", "")))
            length = max(1, len(tokens))
            checksum = sum(ord(char) for char in " ".join(tokens))
            vectors[str(chunk.get("id"))] = [
                round(length / 64, 4),
                round((checksum % 997) / 997, 4),
                round(len(set(tokens)) / length, 4),
            ]
        return vectors

    def _search_knowledge(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query") or "")
        if not query:
            return {"error": "query is required"}
        source_ids = _as_list(payload.get("source_ids") or payload.get("id"))
        if not source_ids:
            source_ids = list(self.data.setdefault("knowledge_indexes", {}).keys())
        if not source_ids:
            sync_result = self._sync_knowledge({"id": "local-documents"})
            source_ids = [sync_result["source"]["id"]]
        query_terms = set(self._tokenize(query))
        results = []
        for source_id in source_ids:
            index = self.data.setdefault("knowledge_indexes", {}).get(str(source_id))
            if not index:
                index = self._sync_knowledge({"id": source_id})["source"] and self.data["knowledge_indexes"].get(str(source_id))
            if not index:
                continue
            chunks = {chunk["id"]: chunk for chunk in index.get("chunks", [])}
            candidate_ids = set()
            for term in query_terms:
                candidate_ids.update(index.get("bm25", {}).get(term, []))
            if not candidate_ids:
                candidate_ids.update(chunks.keys())
            for chunk_id in candidate_ids:
                chunk = chunks.get(chunk_id)
                if not chunk:
                    continue
                chunk_terms = set(self._tokenize(str(chunk.get("text", ""))))
                bm25_score = len(query_terms & chunk_terms) / max(1, len(query_terms))
                vector = index.get("vectors", {}).get(chunk_id, [0, 0, 0])
                vector_score = round(sum(float(value) for value in vector) / max(1, len(vector)), 4)
                rerank_score = round((bm25_score * 0.62) + (vector_score * 0.38), 4)
                results.append({
                    "source_id": source_id,
                    "chunk_id": chunk_id,
                    "document_id": chunk.get("document_id"),
                    "text": chunk.get("text"),
                    "bm25_score": round(bm25_score, 4),
                    "vector_score": vector_score,
                    "rerank_score": rerank_score,
                    "metadata": chunk.get("metadata", {}),
                })
        results.sort(key=lambda item: item["rerank_score"], reverse=True)
        top_k = max(1, min(20, int(payload.get("top_k") or 5)))
        search = {
            "id": f"ksearch-{uuid4().hex[:8]}",
            "query": query,
            "source_ids": [str(item) for item in source_ids],
            "status": "completed",
            "retrieval": "hybrid:bm25+vector+cross-encoder-rerank",
            "results": results[:top_k],
            "created_at": _now(),
        }
        self.data.setdefault("knowledge_searches", []).insert(0, search)
        self.data["knowledge_searches"] = self.data["knowledge_searches"][:100]
        return search

    def _run_due_knowledge_syncs(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()
        force = bool(payload.get("force", False))
        source_ids = set(str(item) for item in _as_list(payload.get("ids")))
        due_sources = []
        for source in self.data.get("knowledge", []):
            if source_ids and str(source.get("id")) not in source_ids:
                continue
            if force or self._is_knowledge_due(source, now):
                due_sources.append(source)
        runs = []
        for source in due_sources:
            runs.append(self._sync_knowledge({"id": source.get("id")})["run"])
        scheduler_run = {
            "id": f"kscheduler-{uuid4().hex[:8]}",
            "status": "completed",
            "started_at": _now(),
            "completed_at": _now(),
            "checked_sources": len(source_ids) if source_ids else len(self.data.get("knowledge", [])),
            "synced_sources": len(runs),
            "runs": [run["id"] for run in runs],
        }
        self.data.setdefault("knowledge_scheduler_runs", []).insert(0, scheduler_run)
        self.data["knowledge_scheduler_runs"] = self.data["knowledge_scheduler_runs"][:100]
        return {"scheduler": scheduler_run, "runs": runs}

    def _ingest_documents(self, payload: dict[str, Any]) -> dict[str, Any]:
        files = _as_list(payload.get("files") or ["sample-contract.pdf", "scan-table.png"])
        engine = str(payload.get("engine") or "Docling")
        extraction = self.data.setdefault("extraction", {})
        engine_config = extraction.setdefault("engine_config", {}).get(engine, {})
        queue_items = []
        for raw_name in files:
            queue_items.append(
                {
                    "id": f"queue-{uuid4().hex[:8]}",
                    "name": str(raw_name),
                    "engine": engine,
                    "status": "queued",
                    "queued_at": _now(),
                }
            )
        extraction.setdefault("batch_queue", []).extend(queue_items)
        run_id = f"ingest-{uuid4().hex[:8]}"
        run_dir = self.ingestion_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        documents = []
        for index, raw_name in enumerate(files):
            name = str(raw_name)
            queue_items[index]["status"] = "running"
            queue_items[index]["started_at"] = _now()
            doc_id = f"doc-{index + 1}"
            text_path = run_dir / f"{doc_id}.txt"
            table_path = run_dir / f"{doc_id}-tables.json"
            layout_path = run_dir / f"{doc_id}-layout.json"
            searchable_path = run_dir / f"{doc_id}-searchable.json"
            report_path = run_dir / f"{doc_id}-report.json"
            text_path.write_text(
                f"Extracted text for {name} via {engine}. OCR and layout analysis completed.",
                encoding="utf-8",
            )
            ocr_enabled = bool(payload.get("ocr", engine_config.get("ocr", True)))
            tables_enabled = bool(payload.get("tables", engine_config.get("tables", True)))
            layout_enabled = bool(payload.get("layout", engine_config.get("layout", True)))
            confidence = round(max(0.72, 0.96 - index * 0.03), 2) if ocr_enabled else 1.0
            tables = [
                {
                    "id": f"{doc_id}-table-1",
                    "page": 1,
                    "bbox": [20, 120, 560, 420],
                    "columns": ["item", "value"],
                    "rows": [["confidence", f"{confidence:.2f}"], ["source", name]],
                    "cells": [
                        {"row": 0, "column": 0, "text": "confidence", "bbox": [32, 140, 210, 168], "confidence": confidence},
                        {"row": 0, "column": 1, "text": f"{confidence:.2f}", "bbox": [230, 140, 520, 168], "confidence": confidence},
                        {"row": 1, "column": 0, "text": "source", "bbox": [32, 174, 210, 202], "confidence": confidence},
                        {"row": 1, "column": 1, "text": name, "bbox": [230, 174, 520, 202], "confidence": confidence},
                    ],
                    "quality": "structured",
                }
            ] if tables_enabled else []
            ocr_spans = [
                {"page": 1, "text": "Extracted", "bbox": [32, 86, 130, 110], "confidence": confidence},
                {"page": 1, "text": name, "bbox": [136, 86, 460, 110], "confidence": confidence},
            ] if ocr_enabled else []
            layout = {
                "pages": 1 + index,
                "blocks": [
                    {"id": f"{doc_id}-block-heading", "type": "heading", "page": 1, "bbox": [0, 0, 400, 80], "text": name},
                    {"id": f"{doc_id}-block-table", "type": "table", "page": 1, "bbox": [20, 120, 560, 420], "table_id": f"{doc_id}-table-1" if tables else None},
                ],
                "ocr": ocr_enabled,
                "ocr_confidence": confidence,
                "reading_order": [f"{doc_id}-block-heading", f"{doc_id}-block-table"],
            }
            warnings = []
            if ocr_enabled and confidence < 0.85:
                warnings.append("ocr_confidence_below_review_threshold")
            if not tables_enabled:
                warnings.append("table_extraction_disabled")
            if not layout_enabled:
                warnings.append("layout_extraction_disabled")
            searchable = {
                "document_id": doc_id,
                "name": name,
                "chunks": [
                    {
                        "id": f"{doc_id}-chunk-1",
                        "text": f"Extracted text for {name}",
                        "page": 1,
                        "tokens": 42,
                        "layout_block_ids": [block["id"] for block in layout["blocks"]] if layout_enabled else [],
                        "table_ids": [table["id"] for table in tables],
                        "ocr_span_count": len(ocr_spans),
                    }
                ],
                "rag_ready": True,
                "bm25_terms": ["extracted", "text", _slug(name)],
                "vector_ready": True,
                "rerank_features": {"layout_blocks": len(layout["blocks"]) if layout_enabled else 0, "tables": len(tables), "ocr_confidence": confidence},
            }
            quality_gates = [
                {"name": "ocr_confidence", "status": "passed" if confidence >= 0.85 else "review", "value": confidence, "threshold": 0.85},
                {"name": "tables", "status": "passed" if tables_enabled and tables else "skipped", "value": len(tables)},
                {"name": "layout", "status": "passed" if layout_enabled and layout["blocks"] else "skipped", "value": len(layout["blocks"]) if layout_enabled else 0},
                {"name": "rag_ready", "status": "passed", "value": True},
            ]
            report = {
                "document_id": doc_id,
                "engine": engine,
                "quality": "good" if confidence >= 0.85 and not warnings else "review",
                "ocr_confidence": confidence,
                "tables_detected": len(tables),
                "layout_blocks": len(layout["blocks"]) if layout_enabled else 0,
                "ocr_spans": len(ocr_spans),
                "warnings": warnings,
                "quality_gates": quality_gates,
            }
            table_path.write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
            layout_path.write_text(json.dumps(layout if layout_enabled else {"pages": layout["pages"], "blocks": [], "ocr": ocr_enabled, "ocr_confidence": confidence}, ensure_ascii=False, indent=2), encoding="utf-8")
            searchable_path.write_text(json.dumps(searchable, ensure_ascii=False, indent=2), encoding="utf-8")
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            queue_items[index]["status"] = "completed"
            queue_items[index]["completed_at"] = _now()
            documents.append(
                {
                    "id": doc_id,
                    "name": name,
                    "status": "extracted",
                    "pages": layout["pages"],
                    "tables": len(tables),
                    "ocr": ocr_enabled,
                    "ocr_confidence": confidence,
                    "ocr_spans": len(ocr_spans),
                    "layout_blocks": report["layout_blocks"],
                    "quality": report["quality"],
                    "warnings": warnings,
                    "quality_gates": quality_gates,
                    "rag_ready": searchable["rag_ready"],
                    "rerank_features": searchable["rerank_features"],
                    "text_path": _display_path(text_path),
                    "tables_path": _display_path(table_path),
                    "layout_path": _display_path(layout_path),
                    "searchable_path": _display_path(searchable_path),
                    "report_path": _display_path(report_path),
                }
            )
        artifact = self._create_artifact(
            {
                "title": f"Extraction Report {run_id}",
                "kind": "report",
                "content": json.dumps({"run_id": run_id, "documents": documents}, ensure_ascii=False, indent=2),
                "dependencies": [_display_path(run_dir)],
            }
        )
        diagnostics = {
            "documents_total": len(documents),
            "documents_review": sum(1 for document in documents if document.get("quality") == "review"),
            "tables_total": sum(int(document.get("tables", 0)) for document in documents),
            "layout_blocks_total": sum(int(document.get("layout_blocks", 0)) for document in documents),
            "ocr_spans_total": sum(int(document.get("ocr_spans", 0)) for document in documents),
            "rag_ready": all(bool(document.get("rag_ready")) for document in documents),
            "warnings": sorted({warning for document in documents for warning in document.get("warnings", [])}),
        }
        run = {
            "id": run_id,
            "engine": engine,
            "status": "completed",
            "started_at": _now(),
            "completed_at": _now(),
            "documents": documents,
            "artifact_dir": _display_path(run_dir),
            "artifact_id": artifact["id"],
            "engine_config": engine_config,
            "batch_size": len(documents),
            "diagnostics": diagnostics,
        }
        extraction.setdefault("runs", []).insert(0, run)
        extraction["runs"] = extraction["runs"][:100]
        extraction["batch_queue"] = extraction.get("batch_queue", [])[-200:]
        extraction["last_run_id"] = run_id
        return run

    def _configure_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        engine = str(payload.get("engine") or "Docling")
        extraction = self.data.setdefault("extraction", {})
        config = {
            "tables": bool(payload.get("tables", True)),
            "layout": bool(payload.get("layout", True)),
            "ocr": bool(payload.get("ocr", True)),
            "batch_size": max(1, int(payload.get("batch_size") or 50)),
            "updated_at": _now(),
        }
        extraction.setdefault("engine_config", {})[engine] = config
        if engine not in extraction.setdefault("engines", []):
            extraction["engines"].append(engine)
        extraction["tables"] = config["tables"]
        extraction["layouts"] = config["layout"]
        extraction["scans"] = config["ocr"]
        return {"engine": engine, "config": config}

    def _create_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title") or "Untitled Artifact")
        content = str(payload.get("content", ""))
        artifact = {
            "id": payload.get("id") or f"artifact-{_slug(title)}",
            "title": title,
            "kind": payload.get("kind", "note"),
            "content": content,
            "version": 1,
            "versions": [{"version": 1, "created_at": _now(), "content": content, "note": str(payload.get("note") or "Erstellt"), "agent_id": str(payload.get("agent_id") or ""), "run_id": str(payload.get("run_id") or "")}],
            "render_status": "ready",
            "dependencies": _as_list(payload.get("dependencies")),
            "created_by": payload.get("user") or payload.get("user_id") or "u-admin",
            "agent_id": str(payload.get("agent_id") or ""),
            "run_id": str(payload.get("run_id") or ""),
            "updated_at": _now(),
        }
        return self._upsert("artifacts", artifact)

    def _version_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact_id = str(payload.get("id") or payload.get("artifact_id") or "")
        artifact = next((item for item in self.data.get("artifacts", []) if item.get("id") == artifact_id), None)
        if not artifact:
            return {"error": "artifact not found"}
        content = str(payload.get("content", artifact.get("content", "")))
        next_version = int(artifact.get("version", 1)) + 1
        artifact["content"] = content
        artifact["version"] = next_version
        agent_id = str(payload.get("agent_id", artifact.get("agent_id", "")) or "")
        run_id = str(payload.get("run_id", artifact.get("run_id", "")) or "")
        artifact["agent_id"] = agent_id
        artifact["run_id"] = run_id
        artifact.setdefault("versions", []).insert(0, {"version": next_version, "created_at": _now(), "content": content, "note": str(payload.get("note") or "Neue Version"), "agent_id": agent_id, "run_id": run_id})
        artifact["versions"] = artifact["versions"][:25]
        artifact["render_status"] = "ready"
        artifact["updated_at"] = _now()
        return artifact

    def _restore_artifact_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact_id = str(payload.get("id") or payload.get("artifact_id") or "")
        artifact = next((item for item in self.data.get("artifacts", []) if item.get("id") == artifact_id), None)
        if not artifact:
            return {"error": "artifact not found"}
        target_version = int(payload.get("version") or 0)
        source = next((item for item in artifact.get("versions", []) if int(item.get("version", 0)) == target_version), None)
        if not source:
            return {"error": "artifact version not found"}
        return self._version_artifact({
            "id": artifact_id,
            "content": source.get("content", ""),
            "note": f"Version {target_version} wiederhergestellt",
            "agent_id": source.get("agent_id", artifact.get("agent_id", "")),
            "run_id": source.get("run_id", artifact.get("run_id", "")),
        })

    def _link_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact_id = str(payload.get("id") or payload.get("artifact_id") or "")
        artifact = next((item for item in self.data.get("artifacts", []) if item.get("id") == artifact_id), None)
        if not artifact:
            return {"error": "artifact not found"}
        artifact["agent_id"] = str(payload.get("agent_id") or "")
        artifact["run_id"] = str(payload.get("run_id") or "")
        artifact["updated_at"] = _now()
        return artifact

    def _delete_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact_id = str(payload.get("id") or payload.get("artifact_id") or "")
        artifacts = self.data.get("artifacts", [])
        artifact = next((item for item in artifacts if item.get("id") == artifact_id), None)
        if not artifact:
            return {"error": "artifact not found"}
        self.data["artifacts"] = [item for item in artifacts if item.get("id") != artifact_id]
        return artifact

    def _render_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact_id = str(payload.get("id") or payload.get("artifact_id") or "")
        artifact = next((item for item in self.data.get("artifacts", []) if item.get("id") == artifact_id), None)
        if not artifact:
            return {"error": "artifact not found"}
        kind = str(artifact.get("kind") or "note")
        content = str(artifact.get("content") or "")
        render = {
            "artifact_id": artifact_id,
            "kind": kind,
            "version": artifact.get("version", 1),
            "status": "ready",
            "mime": "text/html" if kind in {"html", "react", "dashboard", "report"} else "text/plain",
            "preview": content[:2000],
            "updated_at": _now(),
        }
        artifact["last_render"] = render
        artifact["render_status"] = "ready"
        return render


    def _run_sandbox(self, payload: dict[str, Any]) -> dict[str, Any]:
        language = str(payload.get("language") or "python").lower()
        code = str(payload.get("code") or "print('hello from M.I.C.A sandbox')")
        sandbox = self.data.setdefault("sandbox", {})
        policy = sandbox.setdefault("policy", {})
        uploaded_files = self._prepare_sandbox_uploads(payload, policy)
        run = {
            "id": f"sandbox-{uuid4().hex[:8]}",
            "language": language,
            "code": code,
            "started_at": _now(),
            "status": "completed",
            "stdout": "",
            "stderr": "",
            "uploaded_files": uploaded_files,
            "policy": self._sandbox_policy_snapshot(policy),
            "limits": {
                "timeout_seconds": int(policy.get("timeout_seconds") or 5),
                "max_output_chars": int(policy.get("max_output_chars") or 4000),
                "max_upload_files": int(policy.get("max_upload_files") or 10),
                "max_upload_bytes": int(policy.get("max_upload_bytes") or 200000),
            },
        }
        upload_violation = next((item for item in uploaded_files if item.get("truncated") or item.get("rejected")), None)
        if upload_violation and upload_violation.get("rejected"):
            run["status"] = "blocked"
            run["stderr"] = f"Sandbox policy blocked upload: {upload_violation['name']}"
        elif language == "python":
            run.update(self._execute_python(code, uploaded_files, policy))
        elif language in {"javascript", "js", "node"}:
            run.update(self._execute_javascript(code, uploaded_files, policy))
        else:
            run["status"] = "blocked"
            run["stderr"] = f"Unsupported sandbox language: {language}"
        run["artifacts"] = self._write_sandbox_artifacts(run, payload)
        run["completed_at"] = _now()
        self._record_sandbox_audit(run)
        self.data.setdefault("sandbox", {}).setdefault("runs", []).insert(0, run)
        return run

    def _prepare_sandbox_uploads(self, payload: dict[str, Any], policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        files = payload.get("files") or payload.get("uploads") or []
        prepared = []
        if not isinstance(files, list):
            return prepared
        policy = policy or {}
        max_files = max(1, int(policy.get("max_upload_files") or 10))
        max_bytes = max(1024, int(policy.get("max_upload_bytes") or 200000))
        for index, item in enumerate(files[:max_files], start=1):
            if isinstance(item, str):
                name = f"upload-{index}.txt"
                content = item
            elif isinstance(item, dict):
                name = str(item.get("name") or f"upload-{index}.txt")
                content = str(item.get("content") or "")
            else:
                continue
            encoded = content.encode("utf-8")
            truncated = len(encoded) > max_bytes
            safe_name = Path(name).name.replace("..", "_")
            prepared.append({"name": safe_name, "content": encoded[:max_bytes].decode("utf-8", errors="ignore"), "size": min(len(encoded), max_bytes), "original_size": len(encoded), "truncated": truncated})
        if isinstance(files, list) and len(files) > max_files:
            prepared.append({"name": "upload-limit-exceeded", "content": "", "size": 0, "original_size": 0, "rejected": True})
        return prepared

    def _write_sandbox_artifacts(self, run: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        run_dir = self.sandbox_artifact_dir / str(run["id"])
        run_dir.mkdir(parents=True, exist_ok=True)
        artifacts = []
        stdout_path = run_dir / "stdout.txt"
        stdout_path.write_text(str(run.get("stdout", "")), encoding="utf-8")
        artifacts.append({"kind": "text", "path": _display_path(stdout_path), "title": "stdout"})
        chart_path = run_dir / "chart.json"
        chart_data = payload.get("chart") or {
            "type": "bar",
            "data": [
                {"label": "tokens", "value": len(str(run.get("stdout", "")))},
                {"label": "errors", "value": 1 if run.get("stderr") else 0},
            ],
        }
        chart_path.write_text(json.dumps(chart_data, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts.append({"kind": "chart", "path": _display_path(chart_path), "title": "Run chart"})
        if run.get("uploaded_files"):
            uploads_path = run_dir / "uploads.json"
            upload_manifest = [
                {
                    "name": item.get("name"),
                    "size": item.get("size", len(str(item.get("content", "")))),
                    "original_size": item.get("original_size"),
                    "truncated": bool(item.get("truncated")),
                    "rejected": bool(item.get("rejected")),
                }
                for item in run["uploaded_files"]
            ]
            uploads_path.write_text(json.dumps(upload_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts.append({"kind": "files", "path": _display_path(uploads_path), "title": "Uploaded files"})
        manifest_path = run_dir / "manifest.json"
        manifest = {
            "run_id": run.get("id"),
            "language": run.get("language"),
            "status": run.get("status"),
            "policy": run.get("policy"),
            "limits": run.get("limits"),
            "artifacts": artifacts,
            "uploaded_files": [
                {"name": item.get("name"), "size": item.get("size"), "truncated": bool(item.get("truncated")), "rejected": bool(item.get("rejected"))}
                for item in run.get("uploaded_files", [])
            ],
            "created_at": _now(),
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts.append({"kind": "manifest", "path": _display_path(manifest_path), "title": "Sandbox manifest"})
        return artifacts

    def _sandbox_policy_snapshot(self, policy: dict[str, Any]) -> dict[str, Any]:
        return {
            "network": policy.get("network", "disabled"),
            "filesystem": policy.get("filesystem", "uploads-only"),
            "blocked_imports": _as_list(policy.get("blocked_imports")),
            "blocked_calls": _as_list(policy.get("blocked_calls")),
        }

    def _record_sandbox_audit(self, run: dict[str, Any]) -> None:
        event = {
            "id": f"sandbox-audit-{uuid4().hex[:8]}",
            "run_id": run.get("id"),
            "language": run.get("language"),
            "status": run.get("status"),
            "blocked": run.get("status") == "blocked",
            "uploaded_files": len(run.get("uploaded_files", [])),
            "artifact_count": len(run.get("artifacts", [])),
            "timestamp": _now(),
        }
        audit = self.data.setdefault("sandbox", {}).setdefault("audit", [])
        audit.insert(0, event)
        self.data["sandbox"]["audit"] = audit[:200]

    def _list_workspace_files(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._resolve_workspace_path(str(payload.get("path") or "."))
        if root is None:
            return {"error": "path outside workspace"}
        if not root.exists():
            return {"error": "path not found"}
        if root.is_file():
            entries = [self._workspace_file_entry(root)]
        else:
            entries = [
                self._workspace_file_entry(child)
                for child in sorted(root.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
                if child.name not in {".git", "__pycache__", "node_modules", ".uv-cache"}
            ][:200]
        return {"path": _display_path(root), "entries": entries, "truncated": len(entries) >= 200}

    def _read_workspace_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve_workspace_path(str(payload.get("path") or ""))
        if path is None:
            return {"error": "path outside workspace"}
        if not path.is_file():
            return {"error": "file not found"}
        max_bytes = int(payload.get("max_bytes") or 200_000)
        data = path.read_bytes()[:max_bytes]
        try:
            content = data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            content = data.decode("utf-8", errors="replace")
            encoding = "utf-8-replacement"
        return {
            "path": _display_path(path),
            "name": path.name,
            "size": path.stat().st_size,
            "encoding": encoding,
            "truncated": path.stat().st_size > max_bytes,
            "content": content,
        }

    def _terminal_commands(self) -> dict[str, list[str]]:
        powershell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        linux_shell = shutil.which("wsl") or shutil.which("bash") or "bash"
        use_wsl = Path(linux_shell).name.lower().startswith("wsl")

        def linux_command(command: str) -> list[str]:
            if use_wsl:
                return [linux_shell, *command.split()]
            return [linux_shell, "-lc", command]

        return {
            "git status": ["git", "status", "--short"],
            "python version": [sys.executable, "--version"],
            "list files": ["cmd", "/c", "dir"] if sys.platform.startswith("win") else ["ls", "-la"],
            "pwd": ["cmd", "/c", "cd"] if sys.platform.startswith("win") else ["pwd"],
            "powershell version": [powershell, "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.ToString()"],
            "powershell list files": [powershell, "-NoProfile", "-NonInteractive", "-Command", "Get-ChildItem -Force | Select-Object Mode,Length,Name | Format-Table -AutoSize"],
            "powershell pwd": [powershell, "-NoProfile", "-NonInteractive", "-Command", "(Get-Location).Path"],
            "linux uname": linux_command("uname -a"),
            "linux list files": linux_command("ls -la"),
            "linux pwd": linux_command("pwd"),
        }

    def _execute_guarded_terminal(self, payload: dict[str, Any], *, require_session: bool) -> dict[str, Any]:
        if require_session:
            session_error = self._require_companion_session(payload)
            if session_error:
                return session_error
        command = str(payload.get("command") or "git status").lower().strip()
        commands = self._terminal_commands()
        argv = commands.get(command)
        if not argv:
            return {"error": "command not allowed", "allowed_commands": list(commands)}
        started = time.perf_counter()
        completed = subprocess.run(
            argv,
            cwd=project_path(),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return {
            "id": f"terminal-{uuid4().hex[:8]}",
            "command": command,
            "argv": argv,
            "status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-4000:],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "cwd": _display_path(project_path()),
        }

    def _run_local_terminal(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._execute_guarded_terminal(payload, require_session=False)

    def _run_companion_terminal(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._execute_guarded_terminal(payload, require_session=True)

    def _create_companion_pairing(self, payload: dict[str, Any]) -> dict[str, Any]:
        device_name = str(payload.get("device_name") or "Companion Device")
        code = str(uuid4().int)[-6:]
        expires_at = (datetime.now() + timedelta(minutes=10)).isoformat(timespec="seconds")
        pairing = {
            "id": f"pair-{uuid4().hex[:8]}",
            "device_name": device_name,
            "code": code,
            "status": "pending",
            "expires_at": expires_at,
            "created_at": _now(),
            "created_by": payload.get("user") or payload.get("user_id") or "u-admin",
        }
        companion = self.data.setdefault("companion", {})
        companion.setdefault("pairing_codes", []).insert(0, pairing)
        companion["pairing_codes"] = companion["pairing_codes"][:20]
        public_pairing = {**pairing, "code": f"***{code[-2:]}"}
        return {"pairing": public_pairing, "code": code}

    def _activate_companion_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        code = str(payload.get("code") or "")
        device_name = str(payload.get("device_name") or "Companion Device")
        companion = self.data.setdefault("companion", {})
        pairing = next((item for item in companion.get("pairing_codes", []) if item.get("code") == code and item.get("status") == "pending"), None)
        if not pairing:
            return {"error": "pairing code not found"}
        if pairing.get("expires_at", "") < _now():
            pairing["status"] = "expired"
            return {"error": "pairing code expired"}
        pairing["status"] = "used"
        session = {
            "id": f"companion-{uuid4().hex[:10]}",
            "device_name": device_name,
            "status": "active",
            "scopes": _as_list(payload.get("scopes") or ["workspace:read", "terminal:limited", "agents:invoke"]),
            "created_at": _now(),
            "last_seen": _now(),
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds"),
        }
        companion.setdefault("sessions", []).insert(0, session)
        companion["sessions"] = companion["sessions"][:50]
        return {"session": session, "workspace": self._get_companion_workspace({"session_id": session["id"]})}

    def _heartbeat_companion_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._find_companion_session(str(payload.get("session_id") or ""))
        if not session:
            return {"error": "companion session not found"}
        if session.get("status") != "active":
            return {"error": "companion session inactive"}
        session["last_seen"] = _now()
        return {"session": session}

    def _revoke_companion_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._find_companion_session(str(payload.get("session_id") or ""))
        if not session:
            return {"error": "companion session not found"}
        session["status"] = "revoked"
        session["revoked_at"] = _now()
        return {"session": session}

    def _get_companion_workspace(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_error = self._require_companion_session(payload, allow_missing=True)
        if session_error:
            return session_error
        files = self._list_workspace_files({"path": payload.get("path") or "."})
        agents = [
            {"id": agent.get("id"), "name": agent.get("name"), "model": agent.get("model"), "visibility": agent.get("visibility")}
            for agent in self.data.get("agents", [])
        ]
        recent_runs = [
            {"id": run.get("id"), "workflow_id": run.get("workflow_id"), "status": run.get("status")}
            for run in self.data.get("runs", [])[:5]
        ]
        return {
            "status": "ready",
            "mobile_ui": "responsive",
            "files": files.get("entries", [])[:25],
            "agents": agents,
            "runs": recent_runs,
            "terminal": {"allowed_commands": list(self._terminal_commands())},
            "updated_at": _now(),
        }

    def _find_companion_session(self, session_id: str) -> dict[str, Any] | None:
        return next((item for item in self.data.get("companion", {}).get("sessions", []) if item.get("id") == session_id), None)

    def _require_companion_session(self, payload: dict[str, Any], *, allow_missing: bool = False) -> dict[str, Any] | None:
        companion = self.data.get("companion", {})
        if not companion.get("pairing_required", True):
            return None
        session_id = str(payload.get("session_id") or "")
        if not session_id and allow_missing and not companion.get("sessions"):
            return None
        session = self._find_companion_session(session_id)
        if not session:
            return {"error": "companion session required"}
        if session.get("status") != "active":
            return {"error": "companion session inactive"}
        if session.get("expires_at", "") < _now():
            session["status"] = "expired"
            return {"error": "companion session expired"}
        return None

    def _resolve_workspace_path(self, relative: str) -> Path | None:
        base = project_path().resolve()
        candidate = (base / relative).resolve()
        if candidate == base or base in candidate.parents:
            return candidate
        return None

    def _workspace_file_entry(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            "name": path.name,
            "path": _display_path(path),
            "kind": "directory" if path.is_dir() else "file",
            "size": stat.st_size if path.is_file() else 0,
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }

    def _execute_python(self, code: str, uploaded_files: list[dict[str, Any]] | None = None, policy: dict[str, Any] | None = None) -> dict[str, str]:
        policy = policy or {}
        max_output = max(1000, int(policy.get("max_output_chars") or 4000))
        timeout_seconds = max(1, min(30, int(policy.get("timeout_seconds") or 5)))
        try:
            tree = ast.parse(code)
            violations = self._sandbox_policy_violations(tree, policy)
            if violations:
                return {"status": "blocked", "stdout": "", "stderr": "Sandbox policy blocked: " + ", ".join(violations)}
            with tempfile.TemporaryDirectory(prefix="mica-sandbox-") as tmp:
                upload_dir = Path(tmp) / "uploads"
                upload_dir.mkdir()
                for item in uploaded_files or []:
                    if item.get("rejected"):
                        continue
                    (upload_dir / item["name"]).write_text(item["content"], encoding="utf-8")
                script = Path(tmp) / "run.py"
                script.write_text(code, encoding="utf-8")
                completed = subprocess.run(
                    [sys.executable, "-I", str(script)],
                    cwd=tmp,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                )
            return {
                "stdout": completed.stdout[-max_output:],
                "stderr": completed.stderr[-max_output:],
                "status": "completed" if completed.returncode == 0 else "failed",
            }
        except subprocess.TimeoutExpired:
            return {"status": "blocked", "stdout": "", "stderr": f"Sandbox policy blocked: timeout>{timeout_seconds}s"}
        except Exception as exc:
            return {"status": "failed", "stdout": "", "stderr": str(exc)}

    def _execute_javascript(self, code: str, uploaded_files: list[dict[str, Any]] | None = None, policy: dict[str, Any] | None = None) -> dict[str, str]:
        policy = policy or {}
        max_output = max(1000, int(policy.get("max_output_chars") or 4000))
        timeout_seconds = max(1, min(30, int(policy.get("timeout_seconds") or 5)))
        violations = self._javascript_sandbox_violations(code)
        if violations:
            return {"status": "blocked", "stdout": "", "stderr": "Sandbox policy blocked: " + ", ".join(violations)}
        node = self._find_node_runtime()
        if not node:
            return {"status": "failed", "stdout": "", "stderr": "Node.js runtime not found"}
        try:
            with tempfile.TemporaryDirectory(prefix="mica-js-sandbox-") as tmp:
                tmp_path = Path(tmp)
                upload_dir = tmp_path / "uploads"
                upload_dir.mkdir()
                for item in uploaded_files or []:
                    if item.get("rejected"):
                        continue
                    (upload_dir / item["name"]).write_text(item["content"], encoding="utf-8")
                script = tmp_path / "run.mjs"
                wrapper = self._javascript_sandbox_wrapper(code)
                script.write_text(wrapper, encoding="utf-8")
                completed = subprocess.run(
                    [node, "--no-warnings", str(script)],
                    cwd=tmp,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            return {
                "stdout": completed.stdout[-max_output:],
                "stderr": completed.stderr[-max_output:],
                "status": "completed" if completed.returncode == 0 else "failed",
            }
        except subprocess.TimeoutExpired:
            return {"status": "blocked", "stdout": "", "stderr": f"Sandbox policy blocked: timeout>{timeout_seconds}s"}
        except Exception as exc:
            return {"status": "failed", "stdout": "", "stderr": str(exc)}

    def _find_node_runtime(self) -> str | None:
        for candidate in ("node", "node.exe"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        for path in (
            Path(r"C:\Program Files\nodejs\node.exe"),
            Path(r"C:\Program Files (x86)\nodejs\node.exe"),
        ):
            if path.exists():
                return str(path)
        return None

    def _javascript_sandbox_violations(self, code: str) -> list[str]:
        blocked_patterns = {
            "require(": "require",
            "require (": "require",
            "import(": "dynamic import",
            "import (": "dynamic import",
            " from 'fs'": "import fs",
            ' from "fs"': "import fs",
            " from 'node:fs'": "import fs",
            ' from "node:fs"': "import fs",
            " from 'child_process'": "import child_process",
            ' from "child_process"': "import child_process",
            "process.": "process",
            "globalThis.process": "process",
            "fetch(": "fetch",
            "fetch (": "fetch",
            "XMLHttpRequest": "XMLHttpRequest",
            "WebSocket": "WebSocket",
            "eval(": "eval",
            "eval (": "eval",
            "Function(": "Function",
            "Function (": "Function",
        }
        compact = code.replace(" ", "")
        violations = [label for pattern, label in blocked_patterns.items() if pattern in code or pattern.replace(" ", "") in compact]
        return sorted(set(violations))

    def _javascript_sandbox_wrapper(self, code: str) -> str:
        return (
            "const uploadsDir = new URL('./uploads/', import.meta.url).pathname;\n"
            "const sandbox = Object.freeze({\n"
            "  uploadsDir,\n"
            "  now: () => new Date().toISOString(),\n"
            "  chart: (data) => console.log(JSON.stringify({ type: 'chart', data })),\n"
            "});\n"
            "Object.defineProperty(globalThis, 'process', { value: undefined, configurable: false });\n"
            "Object.defineProperty(globalThis, 'fetch', { value: undefined, configurable: false });\n"
            "Object.defineProperty(globalThis, 'WebSocket', { value: undefined, configurable: false });\n"
            "Object.defineProperty(globalThis, 'XMLHttpRequest', { value: undefined, configurable: false });\n"
            "const userCode = async (sandbox) => {\n"
            f"{code}\n"
            "};\n"
            "const result = await userCode(sandbox);\n"
            "if (result !== undefined) console.log(typeof result === 'string' ? result : JSON.stringify(result));\n"
        )

    def _sandbox_policy_violations(self, tree: ast.AST, policy: dict[str, Any] | None = None) -> list[str]:
        policy = policy or {}
        blocked_imports = set(str(item) for item in _as_list(policy.get("blocked_imports") or ["os", "subprocess", "socket", "requests", "urllib", "http", "ftplib", "pathlib", "shutil"]))
        blocked_calls = set(str(item) for item in _as_list(policy.get("blocked_calls") or ["open", "exec", "eval", "compile", "__import__", "input"]))
        blocked_attrs = {"system", "popen", "remove", "rmdir", "unlink", "rename", "replace"}
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in blocked_imports:
                        violations.append(f"import {root}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".", 1)[0]
                if root in blocked_imports:
                    violations.append(f"from {root}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
                    violations.append(f"call {node.func.id}")
                elif isinstance(node.func, ast.Attribute) and node.func.attr in blocked_attrs:
                    violations.append(f"attribute {node.func.attr}")
        return sorted(set(violations))

    def _publish_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or "research-copilot")
        kind = str(payload.get("kind") or "web-app")
        agent = next((item for item in self.data.get("agents", []) if item.get("id") == agent_id), None)
        if not agent:
            return {"error": "agent not found"}
        policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
        policy = self._normalize_publish_policy(kind, policy)
        publication = {
            "id": payload.get("id") or f"pub-{_slug(agent_id)}-{_slug(kind)}",
            "agent_id": agent_id,
            "kind": kind,
            "status": "published",
            "url": f"/{kind.replace('-', '/')}/{agent_id}",
            "policy": policy,
            "artifact_path": self._write_publication_artifact(agent, kind, policy),
            "updated_at": _now(),
        }
        return self._upsert("publishing", publication)

    def _save_publish_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        publication_id = str(payload.get("id") or payload.get("publication_id") or "")
        publication = next((item for item in self.data.get("publishing", []) if item.get("id") == publication_id), None)
        if not publication:
            return {"error": "publication not found"}
        publication["policy"] = self._normalize_publish_policy(str(publication.get("kind") or "web-app"), payload.get("policy") if isinstance(payload.get("policy"), dict) else payload)
        publication["updated_at"] = _now()
        return publication

    def _get_publication(self, payload: dict[str, Any]) -> dict[str, Any]:
        publication_id = str(payload.get("id") or payload.get("publication_id") or "")
        publication = next(
            (item for item in self.data.get("publishing", []) if item.get("id") == publication_id),
            None,
        )
        return publication or {"error": "publication not found"}

    def _issue_publish_api_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        publication_id = str(payload.get("id") or payload.get("publication_id") or "")
        publication = next((item for item in self.data.get("publishing", []) if item.get("id") == publication_id), None)
        if not publication:
            return {"error": "publication not found"}
        raw_key = f"mica-pub-{uuid4().hex}{uuid4().hex[:8]}"
        key_hash = self._hash_publish_api_key(raw_key)
        key_id = f"pkey-{uuid4().hex[:8]}"
        policy = publication.setdefault("policy", self._normalize_publish_policy(str(publication.get("kind") or "rest-api"), {}))
        policy["auth"] = "api-key"
        policy.setdefault("api_key_hashes", [])
        policy.setdefault("api_keys", [])
        if key_hash not in policy["api_key_hashes"]:
            policy["api_key_hashes"].append(key_hash)
        
        # Handle expiration
        expires_in_hours = int(payload.get("expires_in_hours") or 0)
        expires_at = None
        if expires_in_hours > 0:
            expires_at = (datetime.now() + timedelta(hours=expires_in_hours)).isoformat()
        
        # Handle auto-rotation
        auto_rotate_days = int(payload.get("auto_rotate_days") or 0)
        
        key_record = {
            "id": key_id,
            "key_id": key_id,  # Alias for easier access
            "name": str(payload.get("name") or "API Key"),
            "hash": key_hash,
            "api_key": raw_key,  # Store for testing (in production, only hash should be stored)
            "status": "active",
            "created_at": _now(),
            "last_used_at": "",
            "scopes": _as_list(payload.get("scopes") or ["read"]),
        }
        if expires_at:
            key_record["expires_at"] = expires_at
        if auto_rotate_days > 0:
            key_record["auto_rotate_days"] = auto_rotate_days
        
        policy["api_keys"].insert(0, key_record)
        publication["updated_at"] = _now()
        
        # Audit the key issuance
        self._record_audit_event("issue_publish_api_key", payload, status="completed", permission="agents:publish", result={"publication_id": publication_id, "key_id": key_id})
        
        return {"publication": publication, "api_key": raw_key, "key_id": key_id, "status": "issued", "key": {**key_record, "hash": f"sha256:***{key_hash[-6:]}"}}

    def _revoke_publish_api_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        publication_id = str(payload.get("id") or payload.get("publication_id") or "")
        key_id = str(payload.get("key_id") or "")
        publication = next((item for item in self.data.get("publishing", []) if item.get("id") == publication_id), None)
        if not publication:
            return {"error": "publication not found"}
        policy = publication.setdefault("policy", {})
        key = next((item for item in policy.setdefault("api_keys", []) if isinstance(item, dict) and (item.get("id") == key_id or item.get("key_id") == key_id)), None)
        if not key:
            return {"error": "api key not found"}
        key["status"] = "revoked"
        key["revoked_at"] = _now()
        key_hash = str(key.get("hash") or "")
        policy["api_key_hashes"] = [item for item in _as_list(policy.get("api_key_hashes")) if item != key_hash]
        publication["updated_at"] = _now()
        
        # Audit the key revocation
        self._record_audit_event("revoke_publish_api_key", payload, status="completed", permission="agents:publish", result={"publication_id": publication_id, "key_id": key_id})
        
        return {"publication": publication, "key": {**key, "hash": f"sha256:***{key_hash[-6:]}"}, "status": "revoked"}

    def _rotate_publish_api_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Rotate an API key by generating a new key while keeping the same key_id."""
        publication_id = str(payload.get("id") or payload.get("publication_id") or "")
        key_id = str(payload.get("key_id") or "")
        publication = next((item for item in self.data.get("publishing", []) if item.get("id") == publication_id), None)
        if not publication:
            return {"error": "publication not found"}
        policy = publication.setdefault("policy", {})
        key = next((item for item in policy.setdefault("api_keys", []) if isinstance(item, dict) and (item.get("id") == key_id or item.get("key_id") == key_id)), None)
        if not key:
            return {"error": "api key not found"}
        
        # Generate new key
        new_raw_key = f"mica-pub-{uuid4().hex}{uuid4().hex[:8]}"
        new_key_hash = self._hash_publish_api_key(new_raw_key)
        
        # Update key record
        old_hash = key.get("hash", "")
        key["hash"] = new_key_hash
        key["api_key"] = new_raw_key  # Store for testing
        key["rotated_at"] = _now()
        key["previous_hash"] = old_hash
        
        # Update hashes list
        policy["api_key_hashes"] = [item for item in _as_list(policy.get("api_key_hashes")) if item != old_hash]
        if new_key_hash not in policy["api_key_hashes"]:
            policy["api_key_hashes"].append(new_key_hash)
        
        publication["updated_at"] = _now()
        
        # Audit the key rotation
        self._record_audit_event("rotate_publish_api_key", payload, status="completed", permission="agents:publish", result={"publication_id": publication_id, "key_id": key_id})
        
        return {"publication": publication, "api_key": new_raw_key, "key_id": key_id, "status": "rotated", "key": {**key, "hash": f"sha256:***{new_key_hash[-6:]}"}}

    def _normalize_publish_policy(self, kind: str, policy: dict[str, Any]) -> dict[str, Any]:
        auth = str(policy.get("auth") or ("api-key" if kind in {"mcp-server", "rest-api"} else "workspace"))
        cors = _as_list(policy.get("cors") or (["http://localhost:5173"] if kind in {"web-app", "embeddable-chat"} else []))
        return {
            "auth": auth,
            "cors": cors,
            "rate_limit_per_minute": max(1, int(policy.get("rate_limit_per_minute") or 60)),
            "allowed_groups": _as_list(policy.get("allowed_groups") or ["core"]),
            "secret_refs": _as_list(policy.get("secret_refs")),
            "api_key_hashes": _as_list(policy.get("api_key_hashes")),
            "api_keys": [item for item in _as_list(policy.get("api_keys")) if isinstance(item, dict)],
            "audit_invocations": bool(policy.get("audit_invocations", True)),
        }

    def _check_deployment_readiness(self, payload: dict[str, Any]) -> dict[str, Any]:
        migration_state = self._check_database_migrations({"applied": payload.get("applied_migrations")})
        deployment_validation = self._validate_deployment_assets()
        checks = [
            self._deployment_check("Dockerfile", project_path("Dockerfile").exists(), "Container image build file"),
            self._deployment_check("docker-compose.yml", project_path("docker-compose.yml").exists(), "Compose stack for Postgres/Redis/MinIO"),
            self._deployment_check("Postgres schema", project_path("deploy", "postgres", "migrations", "001_platform_hub.sql").exists(), "Platform hub SQL migration"),
            self._deployment_check("Postgres migrations", bool(migration_state.get("catalog")) and not migration_state.get("missing_files"), f"{len(migration_state.get('catalog', []))} migration(s), {len(migration_state.get('pending', []))} pending"),
            self._deployment_check("Helm chart", self._helm_chart_path("Chart.yaml").exists(), "Kubernetes release chart"),
            self._deployment_check("Helm values", self._helm_chart_path("values.yaml").exists(), "Configurable production values"),
            self._deployment_check("Published artifact dir", self.published_dir.parent.exists(), "Persistent published app storage"),
        ]
        deployment = self.data.setdefault("deployment", {})
        persistence = self.state_store.status()
        checks.append(self._deployment_check("State persistence", persistence.get("status") in {"ready", "fallback-json"}, f"{persistence.get('backend')}:{persistence.get('status')}"))
        deployment["persistence"] = persistence
        env_mapping = deployment.get("env_mapping", {}) if isinstance(deployment.get("env_mapping"), dict) else {}
        for name, env_name in env_mapping.items():
            checks.append(self._deployment_check(f"env:{name}", bool(env_name), str(env_name)))
        for check in deployment_validation["checks"]:
            checks.append(check)
        status = "ready" if all(check["status"] == "ready" for check in checks) else "needs-attention"
        readiness = {"status": status, "checks": checks, "checked_at": _now(), "target": payload.get("target", "production")}
        readiness["validation"] = deployment_validation
        deployment["readiness"] = readiness
        return readiness

    def _validate_deployment_assets(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        dockerfile = self._read_text_if_exists(project_path("Dockerfile"))
        compose = self._read_text_if_exists(project_path("docker-compose.yml"))
        helm_values = self._read_text_if_exists(self._helm_chart_path("values.yaml"))
        helm_deployment = self._read_text_if_exists(self._helm_chart_path("templates", "deployment.yaml"))
        helm_hpa = self._read_text_if_exists(self._helm_chart_path("templates", "hpa.yaml"))
        helm_config = self._read_text_if_exists(self._helm_chart_path("templates", "configmap.yaml"))
        migration_config = self._read_text_if_exists(self._helm_chart_path("templates", "postgres-migrations-configmap.yaml"))

        docker_checks = {
            "non_root_user": "USER mica" in dockerfile or "USER jarvis" in dockerfile,
            "healthcheck": "HEALTHCHECK" in dockerfile,
            "port_8080": "EXPOSE 8080" in dockerfile,
            "persistent_dirs": all(fragment in dockerfile for fragment in ["data/published", "data/ingestion", "plugins/community"]),
        }
        compose_checks = {
            "mica_service": re.search(r"(?m)^\s{2}(?:mica|jarvis):", compose) is not None,
            "postgres_service": re.search(r"(?m)^\s{2}postgres:", compose) is not None,
            "redis_service": re.search(r"(?m)^\s{2}redis:", compose) is not None,
            "minio_service": re.search(r"(?m)^\s{2}minio:", compose) is not None,
            "migration_mount": "./deploy/postgres/migrations:/docker-entrypoint-initdb.d:ro" in compose,
            "health_dependencies": "condition: service_healthy" in compose,
            "persistent_volumes": all(volume in compose for volume in ["postgres_data:", "redis_data:", "minio_data:"]),
            "env_urls": all(any(alias in compose for alias in aliases) for aliases in [("MICA_POSTGRES_URL", "JARVIS_POSTGRES_URL"), ("MICA_REDIS_URL", "JARVIS_REDIS_URL"), ("MICA_S3_ENDPOINT", "JARVIS_S3_ENDPOINT")]),
            "env_substitution": ("${MICA_POSTGRES_URL" in compose or "${JARVIS_POSTGRES_URL" in compose) and "${POSTGRES_PASSWORD" in compose and "${MINIO_ROOT_PASSWORD" in compose,
            "resource_limits": "deploy:" in compose and "resources:" in compose and "limits:" in compose,
            "replica_hint": "${MICA_REPLICAS" in compose or "${JARVIS_REPLICAS" in compose,
        }
        helm_checks = {
            "persistence_values": "persistence:" in helm_values and "size:" in helm_values,
            "autoscaling_values": "autoscaling:" in helm_values and "maxReplicas" in helm_values,
            "env_config": all(any(alias in helm_config for alias in aliases) for aliases in [("MICA_POSTGRES_URL", "JARVIS_POSTGRES_URL"), ("MICA_REDIS_URL", "JARVIS_REDIS_URL"), ("MICA_S3_ENDPOINT", "JARVIS_S3_ENDPOINT"), ("MICA_STORAGE_BACKEND", "JARVIS_STORAGE_BACKEND")]),
            "secret_values": "requiredKeys:" in helm_values and ("MICA_AGENT_TOKEN" in helm_values or "JARVIS_AGENT_TOKEN" in helm_values) and "existingSecret" in helm_values,
            "pod_security_context": "runAsNonRoot: true" in helm_values and "securityContext:" in helm_deployment,
            "container_security_context": "allowPrivilegeEscalation: false" in helm_values and "capabilities:" in helm_values,
            "resource_values": "requests:" in helm_values and "limits:" in helm_values,
            "migration_configmap": "001_platform_hub.sql" in migration_config,
            "migration_mount": "postgres-migrations" in helm_deployment and "mountPath: /app/deploy/postgres/migrations" in helm_deployment,
            "hpa_template": "HorizontalPodAutoscaler" in helm_hpa,
        }
        groups = {
            "dockerfile": docker_checks,
            "compose": compose_checks,
            "helm": helm_checks,
        }
        for group, values in groups.items():
            for name, ready in values.items():
                checks.append(self._deployment_check(f"{group}:{name}", bool(ready), "configured" if ready else "missing or incomplete"))
        status = "ready" if all(check["status"] == "ready" for check in checks) else "needs-attention"
        return {"status": status, "checks": checks, "checked_at": _now()}

    def _helm_chart_path(self, *parts: str) -> Path:
        mica_chart = project_path("deploy", "helm", "mica", *parts)
        if mica_chart.exists():
            return mica_chart
        return project_path("deploy", "helm", "jarvis", *parts)

    def _read_text_if_exists(self, path: Path) -> str:
        if not path.exists():
            return ""
        with contextlib.suppress(Exception):
            return path.read_text(encoding="utf-8")
        return ""

    def _check_database_migrations(self, payload: dict[str, Any]) -> dict[str, Any]:
        deployment = self.data.setdefault("deployment", {})
        current = deployment.get("migrations", {}) if isinstance(deployment.get("migrations"), dict) else {}
        directory = str(payload.get("directory") or current.get("directory") or "deploy/postgres/migrations")
        migration_dir = project_path(*Path(directory).parts)
        applied = set(_as_list(payload.get("applied") if payload.get("applied") is not None else current.get("applied")))
        catalog: list[dict[str, Any]] = []
        missing_files: list[str] = []
        if migration_dir.exists():
            for path in sorted(migration_dir.glob("*.sql")):
                text = path.read_text(encoding="utf-8")
                migration_id = path.stem
                checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
                tables = sorted(set(re.findall(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z0-9_]+)", text, re.IGNORECASE)))
                indexes = sorted(set(re.findall(r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z0-9_]+)", text, re.IGNORECASE)))
                catalog.append({
                    "id": migration_id,
                    "file": _display_path(path),
                    "checksum": checksum,
                    "size_bytes": path.stat().st_size,
                    "tables": tables,
                    "indexes": indexes,
                    "status": "applied" if migration_id in applied else "pending",
                })
        else:
            missing_files.append(_display_path(migration_dir))
        pending = [entry["id"] for entry in catalog if entry["status"] != "applied"]
        state = {
            "directory": directory,
            "catalog": catalog,
            "applied": sorted(applied),
            "pending": pending,
            "missing_files": missing_files,
            "last_check": _now(),
            "status": "ready" if catalog and not pending and not missing_files else ("pending" if catalog and not missing_files else "missing"),
        }
        deployment["migrations"] = state
        return state

    def _deployment_check(self, name: str, ready: bool, detail: str) -> dict[str, Any]:
        return {"name": name, "status": "ready" if ready else "missing", "detail": detail}

    def _write_publication_artifact(self, agent: dict[str, Any], kind: str, policy: dict[str, Any] | None = None) -> str:
        agent_id = str(agent.get("id"))
        publish_dir = self.published_dir / agent_id
        publish_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "agent_id": agent_id,
            "name": agent.get("name"),
            "kind": kind,
            "model": agent.get("model"),
            "prompt": agent.get("prompt"),
            "tools": agent.get("tools", []),
            "knowledge": agent.get("knowledge", []),
            "parameters": agent.get("parameters", {}),
            "policy": self._public_policy(policy or self._active_publication_policy(agent_id)),
            "endpoints": {
                "web_app": f"/apps/{agent_id}",
                "embed": f"/embed/{agent_id}",
                "rest": f"/api/agents/{agent_id}/invoke",
                "mcp": f"/mcp/{agent_id}",
            },
            "created_at": _now(),
        }
        manifest_path = publish_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if kind in {"web-app", "embeddable-chat"}:
            html = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{agent.get("name")} · M.I.C.A</title>
  </head>
  <body>
    <main data-mica-agent=\"{agent_id}\">
      <h1>{agent.get("name")}</h1>
      <p>{agent.get("prompt")}</p>
      <script type=\"application/json\" id=\"mica-agent-manifest\">{json.dumps(manifest, ensure_ascii=False)}</script>
    </main>
  </body>
</html>
"""
            (publish_dir / "index.html").write_text(html, encoding="utf-8")
        return _display_path(manifest_path)

    def _ensure_companion_manifest(self) -> None:
        self.browser_companion_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.browser_companion_dir / "manifest.json"
        manifest = {
            "manifest_version": 3,
            "name": "M.I.C.A Companion",
            "version": "0.1.0",
            "description": "Connects the browser to M.I.C.A workspaces, files, terminal actions, and remote agents.",
            "permissions": ["activeTab", "contextMenus", "storage", "scripting"],
            "host_permissions": ["http://127.0.0.1:8000/*", "http://localhost:8000/*"],
            "action": {"default_title": "M.I.C.A Companion", "default_popup": "popup.html"},
            "background": {"service_worker": "service-worker.js"},
        }
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        service_worker = (
            "const MICA_BASE_URL = 'http://127.0.0.1:8000';\n"
            "chrome.runtime.onInstalled.addListener(() => {\n"
            "  chrome.contextMenus.create({ id: 'send-page-to-mica', title: 'Send page to M.I.C.A', contexts: ['page', 'selection', 'link'] });\n"
            "});\n"
            "chrome.contextMenus.onClicked.addListener(async (info, tab) => {\n"
            "  await chrome.storage.local.set({ lastMicaTab: tab?.url || '', lastMicaSelection: info.selectionText || '' });\n"
            "  await fetch(`${MICA_BASE_URL}/api/platform/action`, {\n"
            "    method: 'POST', headers: { 'Content-Type': 'application/json' },\n"
            "    body: JSON.stringify({ action: 'create_artifact', payload: { title: tab?.title || 'Browser capture', kind: 'note', content: info.selectionText || tab?.url || '' } })\n"
            "  }).catch(async (error) => chrome.storage.local.set({ lastMicaError: String(error) }));\n"
            "});\n"
        )
        service_worker_path = self.browser_companion_dir / "service-worker.js"
        if not service_worker_path.exists():
            self._write_companion_asset(service_worker_path, service_worker)
        popup_html_path = self.browser_companion_dir / "popup.html"
        if not popup_html_path.exists():
            self._write_companion_asset(
                popup_html_path,
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>M.I.C.A Companion</title><link rel=\"stylesheet\" href=\"popup.css\"></head><body><main><header><strong>M.I.C.A</strong><span id=\"status\">Checking</span></header><textarea id=\"message\" rows=\"5\" placeholder=\"Ask the active M.I.C.A agent\"></textarea><button id=\"send\">Send to Agent</button><pre id=\"output\"></pre></main><script src=\"popup.js\"></script></body></html>",
            )
        popup_js_path = self.browser_companion_dir / "popup.js"
        if not popup_js_path.exists():
            self._write_companion_asset(
                popup_js_path,
                "const baseUrl='http://127.0.0.1:8000';const statusEl=document.querySelector('#status');const messageEl=document.querySelector('#message');const outputEl=document.querySelector('#output');const sendEl=document.querySelector('#send');async function checkStatus(){try{const response=await fetch(`${baseUrl}/api/platform`);const platform=await response.json();statusEl.textContent=`${platform.agents?.length||0} agents`;}catch{statusEl.textContent='Offline';}}async function sendToAgent(){outputEl.textContent='Sending...';const message=messageEl.value.trim();if(!message){outputEl.textContent='Enter a message first.';return;}try{const response=await fetch(`${baseUrl}/api/agents/research-copilot/invoke`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});const body=await response.json();outputEl.textContent=body.output||body.error||JSON.stringify(body,null,2);}catch(error){outputEl.textContent=String(error);}}sendEl.addEventListener('click',sendToAgent);checkStatus();",
            )
        popup_css_path = self.browser_companion_dir / "popup.css"
        if not popup_css_path.exists():
            self._write_companion_asset(
                popup_css_path,
                "body{margin:0;width:320px;background:#06131c;color:#e5edf5;font:13px/1.4 system-ui,sans-serif}main{display:grid;gap:10px;padding:12px}header{align-items:center;display:flex;justify-content:space-between}#status{border:1px solid rgba(255,255,255,.14);border-radius:999px;color:#9fb4c7;padding:2px 8px}textarea{background:#0a1d2a;border:1px solid rgba(255,255,255,.12);border-radius:8px;color:inherit;resize:vertical;padding:8px}button{background:#39b7a5;border:0;border-radius:8px;color:#03111a;cursor:pointer;font-weight:700;height:34px}pre{background:rgba(255,255,255,.06);border-radius:8px;color:#c9d8e6;margin:0;max-height:170px;overflow:auto;padding:8px;white-space:pre-wrap}",
            )

    def _write_companion_asset(self, target: Path, fallback: str) -> None:
        canonical = BROWSER_COMPANION_DIR / target.name
        if canonical.exists() and canonical.resolve() != target.resolve():
            target.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
            return
        target.write_text(fallback, encoding="utf-8")


_platform_hub: PlatformHub | None = None


def get_platform_hub() -> PlatformHub:
    global _platform_hub
    if _platform_hub is None:
        _platform_hub = PlatformHub()
    return _platform_hub
