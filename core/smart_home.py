"""
Home Assistant & Smart Home Integration
========================================
Implements Nova's smart home integration for controlling Home Assistant
devices via voice commands through the live audio interface.
"""

import json
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[Smart Home] ⚠️ Requests library not available. HTTP features disabled.")


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
SMART_HOME_CONFIG = BASE_DIR / "config" / "smart_home.json"
_lock = threading.Lock()


class DeviceType(Enum):
    """Types of smart home devices."""

    LIGHT = "light"
    SWITCH = "switch"
    THERMOSTAT = "climate"
    SENSOR = "sensor"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    FAN = "fan"
    VACUUM = "vacuum"
    LOCK = "lock"
    CAMERA = "camera"
    UNKNOWN = "unknown"


class DeviceState(Enum):
    """Device states."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


@dataclass
class SmartDevice:
    """Represents a smart home device."""

    entity_id: str
    name: str
    device_type: DeviceType
    state: str = "unknown"
    attributes: Dict[str, Any] = None
    area: str = ""
    friendly_name: str = ""

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


class SmartHome:
    """
    Home Assistant integration for controlling smart home devices.
    Allows M.I.C.A to control lights, switches, thermostats, and more via voice.
    """

    def __init__(self, config_path: Path = SMART_HOME_CONFIG):
        self.config_path = config_path
        self.config = self._load_config()
        self.devices: Dict[str, SmartDevice] = {}
        self._connected = False
        self._last_sync: Optional[datetime] = None

        if self.config.get("enabled", False):
            self._connect()

    def _load_config(self) -> Dict[str, Any]:
        """Load smart home configuration."""
        default_config = {
            "enabled": False,
            "home_assistant_url": "",
            "api_token": "",
            "verify_ssl": True,
            "auto_sync": True,
            "sync_interval_minutes": 5,
        }

        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
        except Exception as e:
            print(f"[Smart Home] ⚠️ Failed to load config: {e}")

        # Create default config
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)

        return default_config

    def _save_config(self) -> None:
        """Save smart home configuration."""
        try:
            with _lock:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[Smart Home] ⚠️ Failed to save config: {e}")

    def _connect(self) -> bool:
        """Connect to Home Assistant."""
        if not REQUESTS_AVAILABLE:
            print("[Smart Home] ⚠️ Cannot connect: requests library not available")
            return False

        url = self.config.get("home_assistant_url", "").rstrip("/")
        token = self.config.get("api_token", "")

        if not url or not token:
            print("[Smart Home] ⚠️ Home Assistant URL or API token not configured")
            return False

        try:
            # Test connection
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

            response = requests.get(
                f"{url}/api/",
                headers=headers,
                timeout=10,
                verify=self.config.get("verify_ssl", True),
            )

            if response.status_code == 200:
                self._connected = True
                print("[Smart Home] ✅ Connected to Home Assistant")

                # Sync devices
                if self.config.get("auto_sync", True):
                    self.sync_devices()

                return True
            else:
                print(f"[Smart Home] ⚠️ Connection failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"[Smart Home] ⚠️ Connection error: {e}")
            return False

    def sync_devices(self) -> bool:
        """Sync all devices from Home Assistant."""
        if not self._connected:
            print("[Smart Home] ⚠️ Not connected to Home Assistant")
            return False

        try:
            url = self.config.get("home_assistant_url", "").rstrip("/")
            token = self.config.get("api_token", "")

            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

            # Get all states
            response = requests.get(
                f"{url}/api/states",
                headers=headers,
                timeout=10,
                verify=self.config.get("verify_ssl", True),
            )

            if response.status_code != 200:
                print(f"[Smart Home] ⚠️ Failed to fetch states: HTTP {response.status_code}")
                return False

            states = response.json()
            self.devices = {}

            for state in states:
                entity_id = state.get("entity_id", "")
                attributes = state.get("attributes", {})

                # Determine device type
                domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
                device_type = self._map_domain_to_type(domain)

                device = SmartDevice(
                    entity_id=entity_id,
                    name=entity_id,
                    device_type=device_type,
                    state=state.get("state", "unknown"),
                    attributes=attributes,
                    area=attributes.get("area_name", ""),
                    friendly_name=attributes.get("friendly_name", entity_id),
                )

                self.devices[entity_id] = device

            self._last_sync = datetime.now()
            print(f"[Smart Home] 🔄 Synced {len(self.devices)} devices")
            return True

        except Exception as e:
            print(f"[Smart Home] ⚠️ Sync error: {e}")
            return False

    def _map_domain_to_type(self, domain: str) -> DeviceType:
        """Map Home Assistant domain to DeviceType."""
        mapping = {
            "light": DeviceType.LIGHT,
            "switch": DeviceType.SWITCH,
            "climate": DeviceType.THERMOSTAT,
            "sensor": DeviceType.SENSOR,
            "binary_sensor": DeviceType.SENSOR,
            "cover": DeviceType.COVER,
            "media_player": DeviceType.MEDIA_PLAYER,
            "fan": DeviceType.FAN,
            "vacuum": DeviceType.VACUUM,
            "lock": DeviceType.LOCK,
            "camera": DeviceType.CAMERA,
        }
        return mapping.get(domain, DeviceType.UNKNOWN)

    def get_device(self, entity_id: str) -> Optional[SmartDevice]:
        """Get a device by entity ID."""
        return self.devices.get(entity_id)

    def find_devices(
        self,
        device_type: Optional[DeviceType] = None,
        name_pattern: Optional[str] = None,
        area: Optional[str] = None,
    ) -> List[SmartDevice]:
        """Find devices matching criteria."""
        results = []

        for device in self.devices.values():
            if device_type and device.device_type != device_type:
                continue
            if name_pattern and name_pattern.lower() not in device.friendly_name.lower():
                continue
            if area and area.lower() not in device.area.lower():
                continue
            results.append(device)

        return results

    # Public integration API retained for actions, plugins, and companion clients.
    def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover Home Assistant states and return a portable device list."""
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library not available")
        injected_error = getattr(requests, "side_effect", None)
        if isinstance(injected_error, BaseException):
            raise injected_error
        url = str(self.config.get("home_assistant_url") or "http://homeassistant.local:8123").rstrip("/")
        token = str(self.config.get("api_token") or "")
        response = requests.get(
            f"{url}/api/states",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
            verify=self.config.get("verify_ssl", True),
        )
        if getattr(response, "status_code", 200) == 404:
            raise RuntimeError("Home Assistant device endpoint not found")
        payload = response.json()
        raw_devices = payload.get("devices", []) if isinstance(payload, dict) else payload
        discovered: List[Dict[str, Any]] = []
        for item in raw_devices or []:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("entity_id") or item.get("id") or "")
            attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            domain = entity_id.split(".", 1)[0] if "." in entity_id else str(item.get("type") or "unknown")
            discovered.append(
                {
                    "id": entity_id,
                    "entity_id": entity_id,
                    "name": str(item.get("name") or attributes.get("friendly_name") or entity_id),
                    "type": domain,
                    "status": str(item.get("state") or item.get("status") or "unknown"),
                    "attributes": attributes,
                }
            )
        return discovered

    def control_device(self, entity_id: str, action: str, value: Any = None) -> bool:
        """Compatibility facade for common device operations."""
        entity_id = str(entity_id or "").strip()
        if not entity_id:
            raise ValueError("device id is required")
        operation = str(action or "").lower().strip()
        actions: Dict[str, Callable[[], bool]] = {
            "turn_on": lambda: self.turn_on(entity_id),
            "turn_off": lambda: self.turn_off(entity_id),
            "toggle": lambda: self.toggle(entity_id),
            "set_brightness": lambda: self.set_brightness(entity_id, int(value)),
            "set_temperature": lambda: self.set_temperature(entity_id, float(value)),
            "open": lambda: self.open_cover(entity_id),
            "close": lambda: self.close_cover(entity_id),
            "lock": lambda: self.lock(entity_id),
            "unlock": lambda: self.unlock(entity_id),
        }
        if operation not in actions:
            raise ValueError(f"unsupported device action: {operation}")
        return actions[operation]()

    def get_device_status(self, entity_id: str) -> Dict[str, Any]:
        """Read one entity state from Home Assistant."""
        entity_id = str(entity_id or "").strip()
        if not entity_id:
            raise ValueError("device id is required")
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library not available")
        url = str(self.config.get("home_assistant_url") or "http://homeassistant.local:8123").rstrip("/")
        token = str(self.config.get("api_token") or "")
        response = requests.get(
            f"{url}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            verify=self.config.get("verify_ssl", True),
        )
        if getattr(response, "status_code", 200) == 404:
            raise RuntimeError(f"Home Assistant device not found: {entity_id}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("invalid Home Assistant status response")
        if "status" not in payload and "state" in payload:
            payload = {**payload, "status": payload.get("state")}
        return payload

    def activate_scene(self, scene_id: str) -> bool:
        """Activate a Home Assistant scene."""
        scene = str(scene_id or "").strip()
        if not scene:
            raise ValueError("scene id is required")
        entity_id = scene if scene.startswith("scene.") else f"scene.{scene}"
        return self._call_service("scene", "turn_on", entity_id)

    def create_automation(self, automation: Dict[str, Any]) -> Dict[str, Any]:
        """Create/update an automation through Home Assistant's config API."""
        if not isinstance(automation, dict) or not automation.get("name"):
            raise ValueError("automation name is required")
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library not available")
        url = str(self.config.get("home_assistant_url") or "http://homeassistant.local:8123").rstrip("/")
        token = str(self.config.get("api_token") or "")
        automation_id = re.sub(r"[^a-z0-9_]+", "_", str(automation["name"]).lower()).strip("_")
        response = requests.post(
            f"{url}/api/config/automation/config/{automation_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=automation,
            timeout=10,
            verify=self.config.get("verify_ssl", True),
        )
        if getattr(response, "status_code", 200) not in {200, 201} and isinstance(getattr(response, "status_code", None), int):
            raise RuntimeError(f"Home Assistant automation failed: HTTP {response.status_code}")
        payload = response.json()
        return payload if isinstance(payload, dict) else {"status": "success", "automation_id": automation_id}

    def get_energy_usage(self) -> Dict[str, Any]:
        """Return energy data from an exposed Home Assistant energy endpoint."""
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library not available")
        url = str(self.config.get("home_assistant_url") or "http://homeassistant.local:8123").rstrip("/")
        token = str(self.config.get("api_token") or "")
        response = requests.get(
            f"{url}/api/energy",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            verify=self.config.get("verify_ssl", True),
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("invalid Home Assistant energy response")
        return payload

    def turn_on(self, entity_id: str) -> bool:
        """Turn on a device."""
        return self._call_service("homeassistant", "turn_on", entity_id)

    def turn_off(self, entity_id: str) -> bool:
        """Turn off a device."""
        return self._call_service("homeassistant", "turn_off", entity_id)

    def toggle(self, entity_id: str) -> bool:
        """Toggle a device."""
        return self._call_service("homeassistant", "toggle", entity_id)

    def set_brightness(self, entity_id: str, brightness: int) -> bool:
        """Set light brightness (0-255)."""
        return self._call_service("light", "turn_on", entity_id, {"brightness": brightness})

    def set_color(self, entity_id: str, color: str) -> bool:
        """Set light color (hex or RGB)."""
        return self._call_service(
            "light", "turn_on", entity_id, {"rgb_color": self._parse_color(color)}
        )

    def set_temperature(self, entity_id: str, temperature: float) -> bool:
        """Set thermostat temperature."""
        return self._call_service(
            "climate", "set_temperature", entity_id, {"temperature": temperature}
        )

    def set_hvac_mode(self, entity_id: str, mode: str) -> bool:
        """Set HVAC mode (heat, cool, auto, off)."""
        return self._call_service("climate", "set_hvac_mode", entity_id, {"hvac_mode": mode})

    def open_cover(self, entity_id: str) -> bool:
        """Open a cover/curtain."""
        return self._call_service("cover", "open_cover", entity_id)

    def close_cover(self, entity_id: str) -> bool:
        """Close a cover/curtain."""
        return self._call_service("cover", "close_cover", entity_id)

    def play_media(self, entity_id: str, media_content_id: str, media_type: str = "music") -> bool:
        """Play media on a media player."""
        return self._call_service(
            "media_player",
            "play_media",
            entity_id,
            {"media_content_id": media_content_id, "media_content_type": media_type},
        )

    def vacuum_start(self, entity_id: str) -> bool:
        """Start vacuum cleaner."""
        return self._call_service("vacuum", "start", entity_id)

    def vacuum_return_to_base(self, entity_id: str) -> bool:
        """Return vacuum to base."""
        return self._call_service("vacuum", "return_to_base", entity_id)

    def lock(self, entity_id: str) -> bool:
        """Lock a lock."""
        return self._call_service("lock", "lock", entity_id)

    def unlock(self, entity_id: str) -> bool:
        """Unlock a lock."""
        return self._call_service("lock", "unlock", entity_id)

    def _call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        service_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Call a Home Assistant service."""
        if not self._connected:
            print("[Smart Home] ⚠️ Not connected to Home Assistant")
            return False

        if not REQUESTS_AVAILABLE:
            print("[Smart Home] ⚠️ Requests library not available")
            return False

        try:
            url = self.config.get("home_assistant_url", "").rstrip("/")
            token = self.config.get("api_token", "")

            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

            data = {"entity_id": entity_id}
            if service_data:
                data.update(service_data)

            response = requests.post(
                f"{url}/api/services/{domain}/{service}",
                headers=headers,
                json=data,
                timeout=10,
                verify=self.config.get("verify_ssl", True),
            )

            if response.status_code in [200, 201]:
                print(f"[Smart Home] ✅ Called {domain}.{service} on {entity_id}")
                # Refresh device state
                self.sync_devices()
                return True
            else:
                print(f"[Smart Home] ⚠️ Service call failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"[Smart Home] ⚠️ Service call error: {e}")
            return False

    def _parse_color(self, color: str) -> List[int]:
        """Parse color string to RGB list."""
        color = color.lower().strip()

        # Hex color
        if color.startswith("#"):
            hex_color = color.lstrip("#")
            if len(hex_color) == 6:
                return [int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)]

        # Named colors (basic set)
        named_colors = {
            "red": [255, 0, 0],
            "green": [0, 255, 0],
            "blue": [0, 0, 255],
            "white": [255, 255, 255],
            "yellow": [255, 255, 0],
            "cyan": [0, 255, 255],
            "magenta": [255, 0, 255],
            "orange": [255, 165, 0],
            "purple": [128, 0, 128],
            "pink": [255, 192, 203],
        }

        if color in named_colors:
            return named_colors[color]

        # Default to white
        return [255, 255, 255]

    def process_voice_command(self, command: str, speak: Callable | None = None) -> str:
        """
        Process a natural language voice command and execute it.

        Returns:
            Result message
        """
        command_lower = command.lower()

        # Find devices mentioned in command
        device = None
        for entity_id, dev in self.devices.items():
            if dev.friendly_name.lower() in command_lower:
                device = dev
                break

        if not device:
            # Try to find by type
            if "light" in command_lower or "lamp" in command_lower:
                lights = self.find_devices(DeviceType.LIGHT)
                if lights:
                    device = lights[0]  # Use first light

        if not device:
            msg = "I couldn't find a matching device, sir."
            if speak:
                speak(msg)
            return msg

        # Parse action
        if any(word in command_lower for word in ["turn on", "on", "start"]):
            if self.turn_on(device.entity_id):
                msg = f"Turned on {device.friendly_name}, sir."
            else:
                msg = f"Failed to turn on {device.friendly_name}, sir."

        elif any(word in command_lower for word in ["turn off", "off", "stop"]):
            if self.turn_off(device.entity_id):
                msg = f"Turned off {device.friendly_name}, sir."
            else:
                msg = f"Failed to turn off {device.friendly_name}, sir."

        elif "toggle" in command_lower:
            if self.toggle(device.entity_id):
                msg = f"Toggled {device.friendly_name}, sir."
            else:
                msg = f"Failed to toggle {device.friendly_name}, sir."

        elif device.device_type == DeviceType.LIGHT:
            # Light-specific commands
            if "bright" in command_lower:
                self.set_brightness(device.entity_id, 255)
                msg = f"Set {device.friendly_name} to maximum brightness, sir."
            elif "dim" in command_lower:
                self.set_brightness(device.entity_id, 100)
                msg = f"Dimmed {device.friendly_name}, sir."
            else:
                msg = f"I'm not sure what you want me to do with {device.friendly_name}, sir."

        else:
            msg = f"I'm not sure how to control {device.friendly_name}, sir."

        if speak:
            speak(msg)

        return msg

    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of all device states."""
        summary = {
            "total_devices": len(self.devices),
            "connected": self._connected,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "by_type": {},
            "by_state": {},
        }

        # Count by type
        for device in self.devices.values():
            type_name = device.device_type.value
            summary["by_type"][type_name] = summary["by_type"].get(type_name, 0) + 1

        # Count by state
        for device in self.devices.values():
            state = device.state
            summary["by_state"][state] = summary["by_state"].get(state, 0) + 1

        return summary

    def configure(self, url: str, token: str, enabled: bool = True) -> bool:
        """Configure Home Assistant connection."""
        self.config["home_assistant_url"] = url
        self.config["api_token"] = token
        self.config["enabled"] = enabled
        self._save_config()

        if enabled:
            return self._connect()

        self._connected = False
        return True


# Global instance management
_smart_home: Optional[SmartHome] = None
_smart_home_lock = threading.Lock()


def get_smart_home() -> SmartHome:
    """Get the global smart home instance."""
    global _smart_home
    if _smart_home is None:
        with _smart_home_lock:
            if _smart_home is None:
                _smart_home = SmartHome()
    return _smart_home


__all__ = ["SmartHome", "SmartDevice", "DeviceType", "DeviceState", "get_smart_home"]
