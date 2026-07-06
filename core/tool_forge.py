"""Controlled tool forging and personality proposal workflows for M.I.C.A."""

from __future__ import annotations

import difflib
import importlib.util
import json
import py_compile
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path, resolve_project_root


ROOT = resolve_project_root()
ALLOWED_PERMISSION_PREFIXES = (
    "text:",
    "files:read",
    "network:http",
    "ui:",
    "time:",
    "memory:",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _slug(value: str, default: str = "generated_tool") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value.lower()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned:
        cleaned = default
    if cleaned[0].isdigit():
        cleaned = f"tool_{cleaned}"
    return cleaned[:64]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class ForgeValidation:
    ok: bool
    checks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "checks": self.checks}


class ToolForge:
    """Plans, creates, validates, and activates generated M.I.C.A plugins."""

    def __init__(self, root: Path | None = None):
        self.root = (root or ROOT).resolve()
        self.generated_dir = self.root / "plugins" / "generated"
        self.plan_dir = self.root / "data" / "tool_forge" / "plans"
        self.personality_dir = self.root / "memory" / "personality"
        self.personality_proposal_dir = self.personality_dir / "proposals"
        self.personality_versions_dir = self.personality_dir / "versions"

    def plan_tool(self, description: str, tool_name: str = "", permissions: list[str] | None = None) -> dict[str, Any]:
        name = _slug(tool_name or description)
        requested_permissions = permissions or ["text:read"]
        plan_id = f"{_stamp()}_{name}"
        plugin_dir = self.generated_dir / name
        plugin_spec = {
            "manifest": {
                "id": name,
                "entrypoint": "plugin.py",
                "enabled": False,
                "permissions": requested_permissions,
            },
            "tool_declaration": {
                "name": name,
                "category": "generated",
                "parameters": {"type": "OBJECT", "properties": {}, "required": []},
            },
            "handler": f"def {name}(parameters: dict, **_kwargs) -> str",
        }
        payload = {
            "plan_id": plan_id,
            "tool_name": name,
            "description": description.strip(),
            "status": "planned",
            "plugin_spec": plugin_spec,
            "quarantine_dir": str(plugin_dir),
            "files": [
                str(plugin_dir / "plugin.json"),
                str(plugin_dir / "plugin.py"),
                str(plugin_dir / "tests" / "test_plugin.py"),
            ],
            "dependencies": [],
            "dependency_installation": "No packages will be installed by this MVP forge flow.",
            "permissions": requested_permissions,
            "risks": self._risk_notes(requested_permissions),
            "approval_required": {
                "before_code_generation": True,
                "before_activation": True,
            },
            "next_action": "Call tool_forge with action=forge, plan_id, and approved_plan=true.",
            "created_at": datetime.now().isoformat(),
        }
        _write_json(self.plan_dir / f"{plan_id}.json", payload)
        return payload

    def forge_tool(
        self,
        plan_id: str,
        *,
        approved_plan: bool,
        plugin_code: str = "",
        test_code: str = "",
        use_model: bool = False,
    ) -> dict[str, Any]:
        if not approved_plan:
            return {"ok": False, "error": "Plan approval is required before code generation."}

        plan = self._load_plan(plan_id)
        name = _slug(str(plan["tool_name"]))
        plugin_dir = self.generated_dir / name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "tests").mkdir(exist_ok=True)

        manifest = {
            "id": name,
            "name": name.replace("_", " ").title(),
            "entrypoint": "plugin.py",
            "permissions": list(plan.get("permissions", [])),
            "enabled": False,
            "generated_by": "mica_tool_forge",
            "plan_id": plan_id,
            "created_at": datetime.now().isoformat(),
        }
        (plugin_dir / "plugin.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (plugin_dir / "plugin.py").write_text(
            plugin_code.strip()
            or self._model_plugin_code(name, str(plan.get("description", "")), plan, use_model)
            or self._default_plugin_code(name, str(plan.get("description", ""))),
            encoding="utf-8",
        )
        (plugin_dir / "tests" / "test_plugin.py").write_text(
            test_code.strip()
            or self._model_test_code(name, str(plan.get("description", "")), plan, use_model)
            or self._default_test_code(name),
            encoding="utf-8",
        )

        plan["status"] = "forged"
        plan["forged_at"] = datetime.now().isoformat()
        _write_json(self.plan_dir / f"{plan_id}.json", plan)
        validation = self.validate_tool(name)
        return {
            "ok": validation.ok,
            "tool_name": name,
            "quarantine_dir": str(plugin_dir),
            "enabled": False,
            "validation": validation.to_dict(),
            "next_action": "If validation is ok, call action=activate with activation_approved=true.",
        }

    def validate_tool(self, tool_name: str) -> ForgeValidation:
        name = _slug(tool_name)
        plugin_dir = self.generated_dir / name
        checks: list[dict[str, Any]] = []

        def add(check: str, ok: bool, detail: str = "") -> None:
            checks.append({"check": check, "ok": ok, "detail": detail})

        manifest_path = plugin_dir / "plugin.json"
        plugin_path = plugin_dir / "plugin.py"
        test_path = plugin_dir / "tests" / "test_plugin.py"

        manifest: dict[str, Any] = {}
        try:
            manifest = _read_json(manifest_path)
            required = {"id", "name", "entrypoint", "permissions", "enabled"}
            missing = sorted(required - set(manifest))
            add("manifest_schema", not missing, f"missing={missing}" if missing else "")
        except Exception as exc:
            add("manifest_schema", False, str(exc))

        permissions = manifest.get("permissions", [])
        permission_ok = isinstance(permissions, list) and all(
            self._permission_allowed(str(permission)) for permission in permissions
        )
        add("permission_check", permission_ok, ", ".join(map(str, permissions)))

        try:
            py_compile.compile(str(plugin_path), doraise=True)
            add("syntax_plugin", True)
        except Exception as exc:
            add("syntax_plugin", False, str(exc))

        try:
            py_compile.compile(str(test_path), doraise=True)
            add("syntax_tests", True)
        except Exception as exc:
            add("syntax_tests", False, str(exc))

        try:
            spec = importlib.util.spec_from_file_location(f"mica_forge_{name}", plugin_path)
            if spec is None or spec.loader is None:
                raise ImportError("Could not build import spec.")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            declaration = getattr(module, "TOOL_DECLARATION", None)
            handler = getattr(module, name, None)
            if not isinstance(declaration, dict):
                raise ValueError("TOOL_DECLARATION missing or invalid.")
            if declaration.get("name") != name:
                raise ValueError("TOOL_DECLARATION name does not match manifest id.")
            if not callable(handler):
                raise ValueError(f"Handler function {name} is missing.")
            add("import_check", True)
        except Exception as exc:
            add("import_check", False, str(exc))

        return ForgeValidation(ok=all(check["ok"] for check in checks), checks=checks)

    def activate_tool(self, tool_name: str, *, activation_approved: bool) -> dict[str, Any]:
        if not activation_approved:
            return {"ok": False, "error": "Second approval is required before activation."}

        validation = self.validate_tool(tool_name)
        if not validation.ok:
            return {"ok": False, "validation": validation.to_dict(), "error": "Validation failed."}

        name = _slug(tool_name)
        manifest_path = self.generated_dir / name / "plugin.json"
        manifest = _read_json(manifest_path)
        manifest["enabled"] = True
        manifest["activated_at"] = datetime.now().isoformat()
        _write_json(manifest_path, manifest)
        registered = self._register_active_plugin(self.generated_dir / name)

        return {
            "ok": True,
            "tool_name": name,
            "enabled": True,
            "registered": registered,
            "validation": validation.to_dict(),
            "note": (
                "Registered in the current plugin manager."
                if registered
                else "Plugin enabled; reload M.I.C.A or reload plugins for the tool to appear."
            ),
        }

    def status(self) -> dict[str, Any]:
        tools = []
        if self.generated_dir.exists():
            for manifest_path in sorted(self.generated_dir.glob("*/plugin.json")):
                try:
                    manifest = _read_json(manifest_path)
                except Exception:
                    continue
                tools.append(
                    {
                        "id": manifest.get("id"),
                        "enabled": bool(manifest.get("enabled")),
                        "permissions": manifest.get("permissions", []),
                        "path": str(manifest_path.parent),
                    }
                )
        return {"generated_dir": str(self.generated_dir), "tools": tools}

    def propose_personality_change(self, request: str, proposed_content: str = "") -> dict[str, Any]:
        soul_path = self._ensure_soul_file()
        current = soul_path.read_text(encoding="utf-8")
        proposed = proposed_content.strip() or self._append_personality_request(current, request)
        proposal_id = f"{_stamp()}_soul"
        diff = "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile="memory/personality/soul.md",
                tofile="memory/personality/soul.md.proposed",
            )
        )
        payload = {
            "proposal_id": proposal_id,
            "request": request,
            "soul_path": str(soul_path),
            "diff": diff,
            "proposed_content": proposed,
            "created_at": datetime.now().isoformat(),
            "status": "proposed",
            "next_action": "Call action=personality_apply with proposal_id and approved=true.",
        }
        _write_json(self.personality_proposal_dir / f"{proposal_id}.json", payload)
        return {k: v for k, v in payload.items() if k != "proposed_content"}

    def apply_personality_change(self, proposal_id: str, *, approved: bool) -> dict[str, Any]:
        if not approved:
            return {"ok": False, "error": "Approval is required before changing soul.md."}

        proposal_path = self.personality_proposal_dir / f"{proposal_id}.json"
        proposal = _read_json(proposal_path)
        soul_path = self._ensure_soul_file()
        self.personality_versions_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self.personality_versions_dir / f"soul_{_stamp()}.md"
        shutil.copy2(soul_path, backup_path)
        soul_path.write_text(str(proposal["proposed_content"]), encoding="utf-8")
        proposal["status"] = "applied"
        proposal["applied_at"] = datetime.now().isoformat()
        proposal["backup_path"] = str(backup_path)
        _write_json(proposal_path, proposal)
        return {
            "ok": True,
            "soul_path": str(soul_path),
            "backup_path": str(backup_path),
            "proposal_id": proposal_id,
        }

    def _load_plan(self, plan_id: str) -> dict[str, Any]:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]+", "", plan_id)
        path = self.plan_dir / f"{safe_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Unknown forge plan: {plan_id}")
        return _read_json(path)

    def _permission_allowed(self, permission: str) -> bool:
        return permission.startswith(ALLOWED_PERMISSION_PREFIXES)

    def _risk_notes(self, permissions: list[str]) -> list[str]:
        notes = [
            "Generated code is written only under plugins/generated/<tool_name>/ first.",
            "The plugin manifest is disabled until activation approval.",
            "Activation requires manifest, permission, syntax, and import validation.",
        ]
        denied = [p for p in permissions if not self._permission_allowed(str(p))]
        if denied:
            notes.append(f"Requested permissions outside the default allowlist: {denied}")
        return notes

    def _default_plugin_code(self, name: str, description: str) -> str:
        safe_description = description.replace('"""', '\\"\\"\\"')
        return f'''"""Generated M.I.C.A plugin: {name}."""

TOOL_DECLARATION = {{
    "name": "{name}",
    "description": """{safe_description}""",
    "parameters": {{
        "type": "OBJECT",
        "properties": {{
            "text": {{"type": "STRING", "description": "Input text for the generated tool."}}
        }},
        "required": [],
    }},
    "category": "generated",
    "enabled": True,
}}


def {name}(parameters: dict, **_kwargs) -> str:
    text = str((parameters or {{}}).get("text", "")).strip()
    if text:
        return f"{name} received: {{text[:500]}}"
    return "{name} is installed and ready."
'''

    def _model_plugin_code(
        self, name: str, description: str, plan: dict[str, Any], use_model: bool
    ) -> str:
        if not use_model:
            return ""
        try:
            from core.model_runner import get_routed_model

            model = get_routed_model(intent="code_edit", use_cache=False)
            prompt = f"""Write a complete M.I.C.A plugin.py file.

Tool name: {name}
Description: {description}
Plan JSON:
{json.dumps(plan, indent=2, ensure_ascii=False)}

Rules:
- Output only raw Python code.
- Define TOOL_DECLARATION with name "{name}".
- Define a callable function named "{name}" that accepts parameters: dict and **_kwargs.
- Do not install packages, spawn subprocesses, read secrets, or write outside the plugin directory.
- Keep the implementation minimal and deterministic.
"""
            return str(model.generate_content(prompt).text).strip()
        except Exception:
            return ""

    def _model_test_code(
        self, name: str, description: str, plan: dict[str, Any], use_model: bool
    ) -> str:
        if not use_model:
            return ""
        try:
            from core.model_runner import get_routed_model

            model = get_routed_model(intent="code_edit", use_cache=False)
            prompt = f"""Write a complete pytest file for a generated M.I.C.A plugin.

Tool name: {name}
Description: {description}
Plan JSON:
{json.dumps(plan, indent=2, ensure_ascii=False)}

Rules:
- Output only raw Python code.
- Import ../plugin.py using importlib.util.
- Assert TOOL_DECLARATION["name"] == "{name}".
- Call the handler and assert it returns a non-empty string.
"""
            return str(model.generate_content(prompt).text).strip()
        except Exception:
            return ""

    def _default_test_code(self, name: str) -> str:
        return f'''import importlib.util
from pathlib import Path


def test_generated_plugin_imports_and_runs():
    plugin_path = Path(__file__).resolve().parents[1] / "plugin.py"
    spec = importlib.util.spec_from_file_location("generated_{name}", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.TOOL_DECLARATION["name"] == "{name}"
    assert getattr(module, "{name}")({{"text": "hello"}})
'''

    def _ensure_soul_file(self) -> Path:
        self.personality_dir.mkdir(parents=True, exist_ok=True)
        soul_path = self.personality_dir / "soul.md"
        if not soul_path.exists():
            soul_path.write_text(
                "# M.I.C.A Soul\n\n"
                "M.I.C.A should be concise, useful, calm, and aligned with the user's preferences.\n",
                encoding="utf-8",
            )
        return soul_path

    def _append_personality_request(self, current: str, request: str) -> str:
        request = request.strip()
        if not request:
            request = "Adjust tone based on the user's latest preference."
        addition = f"\n\n## Proposed Style Adjustment\n- {request}\n"
        return current.rstrip() + addition

    def _register_active_plugin(self, plugin_dir: Path) -> bool:
        if self.root != ROOT:
            return False
        try:
            from core.plugin_system import get_plugin_manager

            manager = get_plugin_manager()
            tool = manager.load_plugin(plugin_dir)
            if tool:
                manager.tools[tool.name] = tool
                return True
        except Exception:
            return False
        return False


_tool_forge: ToolForge | None = None


def get_tool_forge() -> ToolForge:
    global _tool_forge
    if _tool_forge is None:
        _tool_forge = ToolForge(project_path())
    return _tool_forge
