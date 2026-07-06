from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config.startup_config import get_startup_defaults
from core.permission_profiles import get_disabled_actions

REQUIRED_MODULES = {
    "google.genai": "Gemini live client",
    "sounddevice": "Audio input/output",
    "PyQt6": "Desktop UI",
}

OPTIONAL_MODULES = {
    "playwright": "Browser automation",
    "cv2": "Computer vision",
    "mss": "Screen capture",
    "chromadb": "Semantic search database",
    "sentence_transformers": "Embeddings",
    "ollama": "Local LLM fallback",
    "aiohttp": "Async HTTP integrations",
    "websockets": "VS Code bridge",
    "librosa": "Voice emotion analysis",
    "googleapiclient": "Gmail integration",
}


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def _load_legacy_api_key(base_dir: Path) -> str:
    api_file = base_dir / "config" / "api_keys.json"
    if not api_file.exists():
        return ""
    try:
        data = json.loads(api_file.read_text(encoding="utf-8"))
        return str(data.get("gemini_api_key", "")).strip()
    except Exception:
        return ""


def _feature_status(config: Any) -> dict[str, bool]:
    if config is None:
        return {}
    return {
        "ollama": bool(config.get("ollama.enabled", False)),
        "passive_vision": bool(config.get("passive_vision.enabled", False)),
        "rag": bool(config.get("rag.enabled", False)),
        "hud": bool(config.get("hud.enabled", False)),
        "proactive": bool(config.get("proactive.enabled", False)),
        "emotion": bool(config.get("emotion.enabled", False)),
        "vscode": bool(config.get("vscode.bridge_enabled", False)),
        "gmail": bool(config.get("gmail.enabled", False)),
        "obsidian": bool(config.get("obsidian.enabled", False)),
        "telegram": bool(config.get("cross_device.telegram.enabled", False)),
        "discord": bool(config.get("cross_device.discord.enabled", False)),
        "spotify": bool(config.get("spotify.enabled", False)),
    }


def _audio_status() -> dict[str, Any]:
    """Check audio/microphone status."""
    status = {
        "sounddevice_available": False,
        "input_devices": 0,
        "output_devices": 0,
        "default_input": None,
        "default_output": None,
    }

    try:
        import sounddevice as sd

        status["sounddevice_available"] = True

        devices = sd.query_devices()
        status["input_devices"] = sum(1 for d in devices if d["max_input_channels"] > 0)
        status["output_devices"] = sum(1 for d in devices if d["max_output_channels"] > 0)

        try:
            status["default_input"] = (
                sd.query_devices(kind="input")["name"] if status["input_devices"] > 0 else None
            )
        except Exception:
            pass

        try:
            status["default_output"] = (
                sd.query_devices(kind="output")["name"] if status["output_devices"] > 0 else None
            )
        except Exception:
            pass

    except ImportError:
        status["sounddevice_available"] = False
    except Exception as e:
        status["error"] = str(e)

    return status


def _memory_status(base_dir: Path) -> dict[str, Any]:
    """Check memory and backup status."""
    memory_file = base_dir / "memory" / "long_term.json"
    backup_dir = base_dir / "memory" / "backups"

    status = {
        "memory_file_exists": memory_file.exists(),
        "memory_file_size_kb": 0,
        "backup_dir_exists": backup_dir.exists(),
        "backup_count": 0,
        "latest_backup": None,
    }

    if memory_file.exists():
        try:
            status["memory_file_size_kb"] = memory_file.stat().st_size / 1024
        except Exception:
            pass

    if backup_dir.exists():
        try:
            backups = list(backup_dir.glob("*.json"))
            status["backup_count"] = len(backups)
            if backups:
                latest = max(backups, key=lambda p: p.stat().st_mtime)
                status["latest_backup"] = latest.name
        except Exception:
            pass

    return status


def _integration_status(config: Any, base_dir: Path) -> dict[str, Any]:
    """Check integration status (Gmail, Obsidian, VS Code, etc.)."""
    status = {}

    # Gmail
    status["gmail"] = {
        "enabled": bool(config.get("gmail.enabled", False)) if config else False,
        "credentials_exist": (base_dir / "config" / "gmail_credentials.json").exists(),
    }

    # Obsidian
    status["obsidian"] = {
        "enabled": bool(config.get("obsidian.enabled", False)) if config else False,
        "vault_path": config.get("obsidian.vault_path", "") if config else "",
    }

    # VS Code
    status["vscode"] = {
        "enabled": bool(config.get("vscode.bridge_enabled", False)) if config else False,
        "port": config.get("vscode.port", 0) if config else 0,
    }

    # Spotify
    status["spotify"] = {
        "enabled": bool(config.get("spotify.enabled", False)) if config else False,
        "client_configured": bool(config.get("spotify.client_id", "") if config else ""),
    }

    # MCP
    mcp_file = base_dir / "config" / "mcp_servers.json"
    status["mcp"] = {
        "config_exists": mcp_file.exists(),
        "server_count": 0,
    }
    if mcp_file.exists():
        try:
            import json

            with open(mcp_file, "r") as f:
                mcp_config = json.load(f)
                status["mcp"]["server_count"] = len(mcp_config.get("mcpServers", {}))
        except Exception:
            pass

    return status


def _safety_status(config: Any) -> dict[str, Any]:
    """Return approval/safety settings in a UI/API-friendly shape."""
    defaults = get_startup_defaults()
    permission_profile = (
        config.get("security.permission_profile", defaults["security.permission_profile"])
        if config
        else defaults["security.permission_profile"]
    )
    confirmation = {
        "medium_risk": (
            bool(config.get("security.confirmation_medium_risk", defaults["security.confirmation_medium_risk"]))
            if config
            else defaults["security.confirmation_medium_risk"]
        ),
        "high_risk": (
            bool(config.get("security.confirmation_high_risk", defaults["security.confirmation_high_risk"]))
            if config
            else defaults["security.confirmation_high_risk"]
        ),
    }
    configured_disabled = (
        list(config.get("security.disabled_actions", defaults["security.disabled_actions"]))
        if config
        else list(defaults["security.disabled_actions"])
    )
    disabled_actions = sorted(set(configured_disabled) | get_disabled_actions())
    return {
        "permission_profile": permission_profile,
        "confirmation": confirmation,
        "disabled_actions": disabled_actions,
        "action_history_enabled": (
            bool(config.get("security.action_history_enabled", defaults["security.action_history_enabled"]))
            if config
            else defaults["security.action_history_enabled"]
        ),
        "defaults": {
            "medium_confirmation_default": defaults["security.confirmation_medium_risk"],
            "high_confirmation_default": defaults["security.confirmation_high_risk"],
        },
    }


def build_runtime_report(
    base_dir: Path,
    config: Any | None = None,
    plugin_manager: Any | None = None,
    tool_declarations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base_dir = Path(base_dir)

    required_modules = {
        name: {
            "label": label,
            "available": _module_available(name),
        }
        for name, label in REQUIRED_MODULES.items()
    }
    optional_modules = {
        name: {
            "label": label,
            "available": _module_available(name),
        }
        for name, label in OPTIONAL_MODULES.items()
    }

    files = {
        "config_yaml": (base_dir / "config.yaml").exists(),
        "prompt_txt": (base_dir / "core" / "prompt.txt").exists(),
        "memory_json": (base_dir / "memory" / "long_term.json").exists(),
        "plugins_dir": (base_dir / "plugins").exists(),
        "gmail_credentials": (base_dir / "config" / "gmail_credentials.json").exists(),
    }

    api_key = ""
    if config is not None:
        try:
            api_key = str(config.get_api_key("gemini") or "").strip()
        except Exception:
            api_key = ""
    if not api_key:
        api_key = _load_legacy_api_key(base_dir)

    plugin_names: list[str] = []
    if plugin_manager is not None:
        try:
            plugin_names = sorted(tool.name for tool in plugin_manager.get_all_tools())
        except Exception:
            plugin_names = []

    feature_status = _feature_status(config)
    missing_required = [
        details["label"] for details in required_modules.values() if not details["available"]
    ]

    warnings: list[str] = []
    if not files["prompt_txt"]:
        warnings.append("System prompt file is missing.")
    if feature_status.get("gmail") and not files["gmail_credentials"]:
        warnings.append("Gmail is enabled but credentials file is missing.")

    # Extended status checks
    audio_status = _audio_status()
    memory_status = _memory_status(base_dir)
    integration_status = _integration_status(config, base_dir)
    safety_status = _safety_status(config)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_dir": str(base_dir),
        "api_key_present": bool(api_key),
        "required_modules": required_modules,
        "optional_modules": optional_modules,
        "files": files,
        "features": feature_status,
        "plugins": plugin_names,
        "tool_count": len(tool_declarations or []),
        "ready": not missing_required and bool(api_key) and files["prompt_txt"],
        "missing_required": missing_required,
        "warnings": warnings,
        "audio": audio_status,
        "memory": memory_status,
        "integrations": integration_status,
        "safety": safety_status,
        "startup_defaults": get_startup_defaults(),
    }


def format_runtime_report(report: dict[str, Any], verbose: bool = False) -> str:
    lines = [
        f"Runtime ready: {'yes' if report['ready'] else 'no'}",
        f"Gemini API key present: {'yes' if report['api_key_present'] else 'no'}",
        f"Registered tools: {report['tool_count']}",
        f"Plugins loaded: {len(report['plugins'])}",
    ]

    enabled_features = [name for name, enabled in report["features"].items() if enabled]
    lines.append(
        "Enabled features: " + (", ".join(enabled_features) if enabled_features else "none")
    )

    if report["missing_required"]:
        lines.append("Missing required modules: " + ", ".join(report["missing_required"]))

    if report["warnings"]:
        lines.append("Warnings: " + " | ".join(report["warnings"]))
    if report.get("safety"):
        safety = report["safety"]
        confirmation = safety.get("confirmation", {})
        lines.append(
            "Safety: "
            f"profile={safety.get('permission_profile')}, "
            f"medium_confirm={'on' if confirmation.get('medium_risk') else 'off'}, "
            f"high_confirm={'on' if confirmation.get('high_risk') else 'off'}"
        )

    # Extended status in verbose mode
    if verbose:
        # Audio status
        if "audio" in report:
            audio = report["audio"]
            lines.append(
                f"Audio: {'available' if audio.get('sounddevice_available') else 'not available'}"
            )
            if audio.get("sounddevice_available"):
                lines.append(
                    f"  Input devices: {audio.get('input_devices', 0)}, Output devices: {audio.get('output_devices', 0)}"
                )

        # Memory status
        if "memory" in report:
            mem = report["memory"]
            lines.append(f"Memory: {'ok' if mem.get('memory_file_exists') else 'missing'}")
            lines.append(
                f"  Size: {mem.get('memory_file_size_kb', 0):.1f} KB, Backups: {mem.get('backup_count', 0)}"
            )

        # Integration status
        if "integrations" in report:
            lines.append("Integrations:")
            for name, status in report["integrations"].items():
                enabled = "enabled" if status.get("enabled") else "disabled"
                lines.append(f"  {name}: {enabled}")

        required = ", ".join(
            f"{name}={'ok' if info['available'] else 'missing'}"
            for name, info in report["required_modules"].items()
        )
        optional = ", ".join(
            f"{name}={'ok' if info['available'] else 'missing'}"
            for name, info in report["optional_modules"].items()
        )
        lines.append("Required modules: " + required)
        lines.append("Optional modules: " + optional)

    return "\n".join(lines)


def format_diagnostic_report(report: dict[str, Any]) -> str:
    """
    Format a comprehensive diagnostic report for the health panel.

    Args:
        report: Runtime report from build_runtime_report

    Returns:
        Formatted diagnostic string
    """
    lines = []
    lines.append("=" * 70)
    lines.append("M.I.C.A DIAGNOSTIC REPORT")
    lines.append("=" * 70)
    lines.append(f"Generated: {report.get('generated_at', 'N/A')}")
    lines.append(f"Base Directory: {report.get('base_dir', 'N/A')}")
    lines.append("")

    # Overall Status
    ready = report.get("ready", False)
    status_icon = "✓" if ready else "✗"
    lines.append(f"OVERALL STATUS: {status_icon} {'READY' if ready else 'NOT READY'}")
    lines.append("")

    # API Key Status
    api_key_present = report.get("api_key_present", False)
    api_icon = "✓" if api_key_present else "✗"
    lines.append(f"API Key: {api_icon} {'Present' if api_key_present else 'Missing'}")
    lines.append("")

    # Required Modules
    lines.append("REQUIRED MODULES:")
    lines.append("-" * 70)
    required = report.get("required_modules", {})
    for name, info in required.items():
        icon = "✓" if info.get("available") else "✗"
        label = info.get("label", name)
        lines.append(f"  {icon} {label:30s} {'OK' if info.get('available') else 'MISSING'}")
    lines.append("")

    # Optional Modules
    lines.append("OPTIONAL MODULES:")
    lines.append("-" * 70)
    optional = report.get("optional_modules", {})
    for name, info in optional.items():
        icon = "✓" if info.get("available") else "○"
        label = info.get("label", name)
        lines.append(f"  {icon} {label:30s} {'OK' if info.get('available') else 'MISSING'}")
    lines.append("")

    # Audio Status
    if "audio" in report:
        audio = report["audio"]
        lines.append("AUDIO STATUS:")
        lines.append("-" * 70)
        audio_ok = audio.get("sounddevice_available", False)
        audio_icon = "✓" if audio_ok else "✗"
        lines.append(f"  {audio_icon} Sounddevice: {'Available' if audio_ok else 'Not Available'}")
        if audio_ok:
            lines.append(f"     Input Devices: {audio.get('input_devices', 0)}")
            lines.append(f"     Output Devices: {audio.get('output_devices', 0)}")
            if audio.get("default_input"):
                lines.append(f"     Default Input: {audio.get('default_input')}")
            if audio.get("default_output"):
                lines.append(f"     Default Output: {audio.get('default_output')}")
        lines.append("")

    # Memory Status
    if "memory" in report:
        mem = report["memory"]
        lines.append("MEMORY STATUS:")
        lines.append("-" * 70)
        mem_ok = mem.get("memory_file_exists", False)
        mem_icon = "✓" if mem_ok else "✗"
        lines.append(f"  {mem_icon} Memory File: {'Exists' if mem_ok else 'Missing'}")
        if mem_ok:
            lines.append(f"     Size: {mem.get('memory_file_size_kb', 0):.1f} KB")
        backup_ok = mem.get("backup_dir_exists", False)
        backup_icon = "✓" if backup_ok else "○"
        lines.append(f"  {backup_icon} Backup Directory: {'Exists' if backup_ok else 'Not Found'}")
        lines.append(f"     Backup Count: {mem.get('backup_count', 0)}")
        if mem.get("latest_backup"):
            lines.append(f"     Latest Backup: {mem.get('latest_backup')}")
        lines.append("")

    # Integration Status
    if "integrations" in report:
        integrations = report["integrations"]
        lines.append("INTEGRATION STATUS:")
        lines.append("-" * 70)
        for name, status in integrations.items():
            enabled = status.get("enabled", False)
            icon = "✓" if enabled else "○"
            lines.append(f"  {icon} {name.capitalize():15s} {'Enabled' if enabled else 'Disabled'}")

            # Add integration-specific details
            if name == "gmail" and status.get("credentials_exist"):
                lines.append("     ✓ Credentials configured")
            if name == "obsidian" and status.get("vault_path"):
                lines.append(f"     Vault: {status.get('vault_path')}")
            if name == "vscode" and status.get("port"):
                lines.append(f"     Port: {status.get('port')}")
            if name == "mcp" and status.get("server_count"):
                lines.append(f"     Servers: {status.get('server_count')}")
        lines.append("")

    # Feature Status
    features = report.get("features", {})
    enabled_features = [name for name, enabled in features.items() if enabled]
    lines.append("ENABLED FEATURES:")
    lines.append("-" * 70)
    if enabled_features:
        for feature in enabled_features:
            lines.append(f"  ✓ {feature}")
    else:
        lines.append("  (none enabled)")
    lines.append("")

    # Tools and Plugins
    lines.append("TOOLS AND PLUGINS:")
    lines.append("-" * 70)
    lines.append(f"  Registered Tools: {report.get('tool_count', 0)}")
    lines.append(f"  Loaded Plugins: {len(report.get('plugins', []))}")
    if report.get("plugins"):
        for plugin in report["plugins"][:5]:  # Show first 5
            lines.append(f"    - {plugin}")
        if len(report["plugins"]) > 5:
            lines.append(f"    ... and {len(report['plugins']) - 5} more")
    lines.append("")

    # Warnings
    warnings = report.get("warnings", [])
    if warnings:
        lines.append("WARNINGS:")
        lines.append("-" * 70)
        for warning in warnings:
            lines.append(f"  ⚠ {warning}")
        lines.append("")

    # Missing Required
    missing = report.get("missing_required", [])
    if missing:
        lines.append("MISSING REQUIRED:")
        lines.append("-" * 70)
        for item in missing:
            lines.append(f"  ✗ {item}")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


if __name__ == "__main__":
    try:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        tool_declarations = None
        from config.config_loader import get_config
        from core.plugin_system import get_plugin_manager

        base = Path(__file__).resolve().parent.parent
        config = get_config()
        plugins = get_plugin_manager()
        plugins.load_all_plugins()
        try:
            import main as main_module

            tool_declarations = list(main_module.TOOL_DECLARATIONS) + list(
                main_module.FEATURE_TOOL_DECLARATIONS
            )
        except Exception:
            tool_declarations = None
        report = build_runtime_report(
            base,
            config=config,
            plugin_manager=plugins,
            tool_declarations=tool_declarations,
        )
        print(format_runtime_report(report, verbose=True))
    except Exception as exc:
        print(f"Health check failed: {exc}")
