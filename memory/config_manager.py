import json
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def config_exists() -> bool:
    return CONFIG_FILE.exists()


def save_api_keys(
    gemini_api_key: str = "",
    *,
    openai_api_key: str = "",
    ollama_base_url: str = "",
) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    if gemini_api_key.strip():
        data["gemini_api_key"] = gemini_api_key.strip()
    if openai_api_key.strip():
        data["openai_api_key"] = openai_api_key.strip()
    if ollama_base_url.strip():
        data["ollama_base_url"] = ollama_base_url.strip()

    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}


def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")


def is_valid_gemini_key(api_key: str | None) -> bool:
    """Return True when the value looks like a Gemini API key."""
    key = str(api_key or "").strip()
    return (key.startswith("AIza") or key.startswith("AQ.")) and len(key) >= 30


def save_setup_config(
    *,
    gemini_api_key: str = "",
    openai_api_key: str = "",
    ollama_base_url: str = "",
    preferred_model: str = "fast",
    model_scope: str = "linked",
) -> dict:
    """Persist first-run API key and model choices."""
    save_api_keys(
        gemini_api_key,
        openai_api_key=openai_api_key,
        ollama_base_url=ollama_base_url,
    )

    try:
        from config.config_loader import get_config

        settings = {
            "model_router": {
                "preferred_profile": preferred_model or "fast",
                "model_scope": model_scope if model_scope in {"all", "linked"} else "linked",
            }
        }
        return get_config().update_local_settings(settings)
    except Exception:
        return {
            "model_router": {
                "preferred_profile": preferred_model or "fast",
                "model_scope": model_scope if model_scope in {"all", "linked"} else "linked",
            }
        }


def is_configured() -> bool:
    key = get_gemini_key()
    return is_valid_gemini_key(key)
