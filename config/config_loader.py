"""
Unified Configuration Loader for M.I.C.A
Loads configuration from .env and config.yaml
"""

import json
import os
from typing import Any, Dict, Optional

import yaml

from core.paths import resolve_project_root

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


class Config:
    """Unified configuration manager"""

    _instance: Optional["Config"] = None
    _config: Dict[str, Any] = {}

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._config:
            self._load_config()

    def _load_config(self):
        """Load configuration from all sources"""
        # Resolve the project root once so config and asset paths stay stable
        # even when the app is launched from a shortcut or packaged executable.
        self.base_dir = resolve_project_root()

        # Load .env file
        if DOTENV_AVAILABLE:
            env_path = self.base_dir / ".env"
            if env_path.exists():
                load_dotenv(env_path)

        # Load config.yaml
        yaml_path = self.base_dir / "config.yaml"
        yaml_config = {}
        if yaml_path.exists():
            try:
                with open(yaml_path, "r", encoding="utf-8", errors="ignore") as f:
                    yaml_config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"[Config] Warning: Could not load config.yaml: {e}")

        # Load API keys from JSON (legacy support)
        api_config_path = self.base_dir / "config" / "api_keys.json"
        api_keys = {}
        if api_config_path.exists():
            try:
                with open(api_config_path, "r", encoding="utf-8") as f:
                    api_keys = json.load(f)
            except Exception:
                pass

        # Load UI overrides/settings
        self.local_settings_path = self.base_dir / "config" / "ui_settings.json"
        local_settings = {}
        if self.local_settings_path.exists():
            try:
                with open(self.local_settings_path, "r", encoding="utf-8") as f:
                    local_settings = json.load(f) or {}
            except Exception as e:
                print(f"[Config] Warning: Could not load ui_settings.json: {e}")

        # Merge all configurations with priority:
        # api_keys.json < config.yaml < ui_settings.json < .env
        merged: Dict[str, Any] = {}
        self._deep_merge(merged, self._api_keys_to_dict(api_keys))
        self._deep_merge(merged, yaml_config)
        self._deep_merge(merged, local_settings)
        self._deep_merge(merged, self._env_to_dict())
        self._config = merged

        # Set paths
        self._config.setdefault("paths", {})["base_dir"] = str(self.base_dir)

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge one dictionary into another."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
        return target

    def _env_to_dict(self) -> Dict[str, Any]:
        """Convert environment variables to nested dict"""
        env_dict = {}

        # API Keys
        if os.getenv("GEMINI_API_KEY"):
            env_dict["api_keys"] = {"gemini_api_key": os.getenv("GEMINI_API_KEY")}

        # Models
        if os.getenv("LIVE_MODEL"):
            env_dict.setdefault("models", {})["live"] = os.getenv("LIVE_MODEL")
        if os.getenv("TEXT_MODEL"):
            env_dict.setdefault("models", {})["text"] = os.getenv("TEXT_MODEL")
        if os.getenv("VISION_MODEL"):
            env_dict.setdefault("models", {})["vision"] = os.getenv("VISION_MODEL")
        if os.getenv("CONTEXT_WINDOW"):
            env_dict.setdefault("models", {})["context_window"] = int(os.getenv("CONTEXT_WINDOW"))

        # Model router profile overrides (optional, backward-compatible)
        router_env = {
            "MODEL_ROUTER_COST_MODE": ("cost_mode", str),
            "MODEL_ROUTER_LONG_CONTEXT_CHARS": ("long_context_chars", int),
            "MODEL_ROUTER_FAST_MODEL": ("models.fast.model_id", str),
            "MODEL_ROUTER_REASONING_MODEL": ("models.reasoning.model_id", str),
            "MODEL_ROUTER_VISION_MODEL": ("models.vision.model_id", str),
            "MODEL_ROUTER_LONG_CONTEXT_MODEL": ("models.long_context.model_id", str),
            "MODEL_ROUTER_LOCAL_MODEL": ("models.local.model_id", str),
        }
        for env_name, (path, caster) in router_env.items():
            raw = os.getenv(env_name)
            if raw is None:
                continue
            target = env_dict.setdefault("model_router", {})
            parts = path.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = caster(raw)

        # Ollama
        if os.getenv("OLLAMA_ENABLED"):
            env_dict.setdefault("ollama", {})["enabled"] = (
                os.getenv("OLLAMA_ENABLED").lower() == "true"
            )
        if os.getenv("OLLAMA_BASE_URL"):
            env_dict.setdefault("ollama", {})["base_url"] = os.getenv("OLLAMA_BASE_URL")
        if os.getenv("OLLAMA_MODEL"):
            env_dict.setdefault("ollama", {})["model"] = os.getenv("OLLAMA_MODEL")

        # Audio
        if os.getenv("CHANNELS"):
            env_dict.setdefault("audio", {})["channels"] = int(os.getenv("CHANNELS"))
        if os.getenv("SEND_SAMPLE_RATE"):
            env_dict.setdefault("audio", {})["send_sample_rate"] = int(
                os.getenv("SEND_SAMPLE_RATE")
            )
        if os.getenv("RECEIVE_SAMPLE_RATE"):
            env_dict.setdefault("audio", {})["receive_sample_rate"] = int(
                os.getenv("RECEIVE_SAMPLE_RATE")
            )
        if os.getenv("CHUNK_SIZE"):
            env_dict.setdefault("audio", {})["chunk_size"] = int(os.getenv("CHUNK_SIZE"))

        # Passive Vision
        if os.getenv("PASSIVE_VISION_ENABLED"):
            env_dict.setdefault("passive_vision", {})["enabled"] = (
                os.getenv("PASSIVE_VISION_ENABLED").lower() == "true"
            )
        if os.getenv("PASSIVE_VISION_INTERVAL"):
            env_dict.setdefault("passive_vision", {})["interval_seconds"] = int(
                os.getenv("PASSIVE_VISION_INTERVAL")
            )

        # RAG
        if os.getenv("RAG_ENABLED"):
            env_dict.setdefault("rag", {})["enabled"] = os.getenv("RAG_ENABLED").lower() == "true"
        if os.getenv("RAG_VECTOR_DB"):
            env_dict.setdefault("rag", {})["vector_db"] = os.getenv("RAG_VECTOR_DB")

        # HUD
        if os.getenv("HUD_ENABLED"):
            env_dict.setdefault("hud", {})["enabled"] = os.getenv("HUD_ENABLED").lower() == "true"
        if os.getenv("HUD_TRANSPARENCY"):
            env_dict.setdefault("hud", {})["transparency"] = float(os.getenv("HUD_TRANSPARENCY"))

        # Proactive
        if os.getenv("PROACTIVE_SUGGESTIONS_ENABLED"):
            env_dict.setdefault("proactive", {})["enabled"] = (
                os.getenv("PROACTIVE_SUGGESTIONS_ENABLED").lower() == "true"
            )

        # Emotion
        if os.getenv("EMOTION_ANALYSIS_ENABLED"):
            env_dict.setdefault("emotion", {})["enabled"] = (
                os.getenv("EMOTION_ANALYSIS_ENABLED").lower() == "true"
            )

        # Cross-device
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            env_dict.setdefault("cross_device", {}).setdefault("telegram", {})["bot_token"] = (
                os.getenv("TELEGRAM_BOT_TOKEN")
            )
        if os.getenv("TELEGRAM_CHAT_ID"):
            env_dict.setdefault("cross_device", {}).setdefault("telegram", {})["chat_id"] = (
                os.getenv("TELEGRAM_CHAT_ID")
            )
        if os.getenv("DISCORD_BOT_TOKEN"):
            env_dict.setdefault("cross_device", {}).setdefault("discord", {})["bot_token"] = (
                os.getenv("DISCORD_BOT_TOKEN")
            )
        if os.getenv("DISCORD_CHANNEL_ID"):
            env_dict.setdefault("cross_device", {}).setdefault("discord", {})["channel_id"] = (
                os.getenv("DISCORD_CHANNEL_ID")
            )

        # VS Code
        if os.getenv("VSCODE_BRIDGE_ENABLED"):
            env_dict.setdefault("vscode", {})["bridge_enabled"] = (
                os.getenv("VSCODE_BRIDGE_ENABLED").lower() == "true"
            )
        if os.getenv("VSCODE_PORT"):
            env_dict.setdefault("vscode", {})["port"] = int(os.getenv("VSCODE_PORT"))

        # Spotify
        if os.getenv("SPOTIFY_CLIENT_ID"):
            env_dict.setdefault("spotify", {})["client_id"] = os.getenv("SPOTIFY_CLIENT_ID")
        if os.getenv("SPOTIFY_CLIENT_SECRET"):
            env_dict.setdefault("spotify", {})["client_secret"] = os.getenv("SPOTIFY_CLIENT_SECRET")
        if os.getenv("SPOTIFY_REDIRECT_URI"):
            env_dict.setdefault("spotify", {})["redirect_uri"] = os.getenv("SPOTIFY_REDIRECT_URI")
        if os.getenv("SPOTIFY_ENABLED"):
            env_dict.setdefault("spotify", {})["enabled"] = (
                os.getenv("SPOTIFY_ENABLED").lower() == "true"
            )

        # System
        if os.getenv("STEALTH_MODE"):
            env_dict.setdefault("system", {})["stealth_mode"] = (
                os.getenv("STEALTH_MODE").lower() == "true"
            )

        return env_dict

    def _api_keys_to_dict(self, api_keys: Dict) -> Dict[str, Any]:
        """Convert legacy API keys JSON to config format"""
        if not api_keys:
            return {}
        return {"api_keys": api_keys}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_api_key(self, service: str = "gemini") -> Optional[str]:
        """Get API key for a service"""
        api_keys = self._config.get("api_keys", {})
        return api_keys.get(f"{service}_api_key")

    def reload(self):
        """Reload configuration from files"""
        self._config.clear()
        self._load_config()

    def update_local_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Persist UI settings overrides to config/ui_settings.json."""
        current = {}
        if getattr(self, "local_settings_path", None) and self.local_settings_path.exists():
            try:
                with open(self.local_settings_path, "r", encoding="utf-8") as f:
                    current = json.load(f) or {}
            except Exception:
                current = {}

        self._deep_merge(current, updates)
        self.local_settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.local_settings_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self.local_settings_path)
        self.reload()
        return current

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance"""
    return config
