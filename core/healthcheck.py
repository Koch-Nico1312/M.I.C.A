from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


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
    return importlib.util.find_spec(module_name) is not None


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
        details["label"]
        for details in required_modules.values()
        if not details["available"]
    ]

    warnings: list[str] = []
    if not files["prompt_txt"]:
        warnings.append("System prompt file is missing.")
    if feature_status.get("gmail") and not files["gmail_credentials"]:
        warnings.append("Gmail is enabled but credentials file is missing.")

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
        "Enabled features: "
        + (", ".join(enabled_features) if enabled_features else "none")
    )

    if report["missing_required"]:
        lines.append("Missing required modules: " + ", ".join(report["missing_required"]))

    if report["warnings"]:
        lines.append("Warnings: " + " | ".join(report["warnings"]))

    if verbose:
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
