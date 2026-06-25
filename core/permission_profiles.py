"""
Permission Profiles System for Mark-XXXIX
==========================================
Defines permission levels (safe, normal, admin) and checks if actions are allowed.
Extended with tool metadata and configurable action disabling.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Set


class PermissionLevel(Enum):
    SAFE = "safe"  # Read-only, no modifications
    NORMAL = "normal"  # Modification allowed, dangerous actions require confirmation
    ADMIN = "admin"  # No restrictions


@dataclass
class ToolMetadata:
    """Metadata for a tool/action."""

    name: str
    description: str
    risk_level: str  # low, medium, high
    requires_confirmation: bool = True
    requires_permission: bool = False
    reversible: bool = False
    tags: Set[str] = field(default_factory=set)
    enabled: bool = True


# Actions that are considered dangerous and require confirmation in NORMAL mode,
# or are completely blocked in SAFE mode.
DESTRUCTIVE_ACTIONS = {
    # System settings
    "shutdown",
    "restart",
    "toggle_wifi",
    "sleep_display",
    "lock_screen",
    # File Controller
    "delete",
    "delete_file",
    # Computer Control / Input automation
    "type",
    "type_text",
    "press",
    "press_key",
    "hotkey",
    "click",
    "double_click",
    "right_click",
    "screen_click",
}


# Tool metadata registry
TOOL_METADATA: Dict[str, ToolMetadata] = {
    "web_search": ToolMetadata(
        name="web_search",
        description="Searches the web for information",
        risk_level="low",
        requires_confirmation=False,
        reversible=False,
        tags={"search", "web", "information"},
    ),
    "weather_report": ToolMetadata(
        name="weather_report",
        description="Provides weather information",
        risk_level="low",
        requires_confirmation=False,
        reversible=False,
        tags={"weather", "information"},
    ),
    "open_app": ToolMetadata(
        name="open_app",
        description="Opens applications on the computer",
        risk_level="medium",
        requires_confirmation=False,
        reversible=False,
        tags={"application", "system"},
    ),
    "browser_control": ToolMetadata(
        name="browser_control",
        description="Controls web browser operations",
        risk_level="medium",
        requires_confirmation=True,
        reversible=False,
        tags={"browser", "web", "automation"},
    ),
    "file_controller": ToolMetadata(
        name="file_controller",
        description="Manages files and folders",
        risk_level="medium",
        requires_confirmation=True,
        reversible=True,
        tags={"file", "system", "data"},
    ),
    "send_message": ToolMetadata(
        name="send_message",
        description="Sends messages via messaging platforms",
        risk_level="high",
        requires_confirmation=True,
        reversible=False,
        tags={"communication", "messaging"},
    ),
    "gmail_manager": ToolMetadata(
        name="gmail_manager",
        description="Manages Gmail emails",
        risk_level="high",
        requires_confirmation=True,
        reversible=False,
        tags={"email", "communication", "integration"},
    ),
    "calendar_manager": ToolMetadata(
        name="calendar_manager",
        description="Manages Google Calendar events",
        risk_level="high",
        requires_confirmation=True,
        reversible=True,
        tags={"calendar", "scheduling", "integration"},
    ),
    "contact_manager": ToolMetadata(
        name="contact_manager",
        description="Manages local contacts",
        risk_level="high",
        requires_confirmation=True,
        reversible=True,
        tags={"contacts", "communication", "integration"},
    ),
    "computer_settings": ToolMetadata(
        name="computer_settings",
        description="Controls computer settings",
        risk_level="high",
        requires_confirmation=True,
        reversible=True,
        tags={"system", "settings"},
    ),
    "delete": ToolMetadata(
        name="delete",
        description="Deletes files or folders",
        risk_level="high",
        requires_confirmation=True,
        reversible=False,
        tags={"file", "destructive"},
    ),
    "self_dev_agent": ToolMetadata(
        name="self_dev_agent",
        description="Controlled repository self-development with branch, diff, and test gates",
        risk_level="high",
        requires_confirmation=True,
        reversible=True,
        tags={"development", "git", "testing", "self-dev"},
    ),
    "daily_mode": ToolMetadata(
        name="daily_mode",
        description="Applies daily-driver configuration presets",
        risk_level="medium",
        requires_confirmation=True,
        reversible=True,
        tags={"configuration", "mode", "safety"},
    ),
}


# Disabled actions (can be configured at runtime)
DISABLED_ACTIONS: Set[str] = set()


def check_action(profile: str, action: str, parameters: dict = None) -> tuple[bool, str]:
    """
    Checks if an action is allowed under the current permission profile.
    Also checks if action is disabled.

    Returns:
        (is_allowed, status_message)
    """
    if parameters is None:
        parameters = {}

    profile_lower = str(profile).lower().strip()
    action_lower = str(action).lower().strip()

    # Check if action is disabled
    if action_lower in DISABLED_ACTIONS:
        return False, f"Action '{action}' is disabled by configuration."

    # Admin has absolute access (unless disabled)
    if profile_lower == PermissionLevel.ADMIN.value:
        return True, "Allowed"

    # Safe blocks all destructive/modification actions
    if profile_lower == PermissionLevel.SAFE.value:
        if action_lower in DESTRUCTIVE_ACTIONS:
            return False, f"Action '{action}' is blocked under the 'safe' permission profile."

        # File modifications are blocked in safe mode
        if action_lower in (
            "create_file",
            "create_folder",
            "write",
            "move",
            "copy",
            "rename",
            "organize_desktop",
        ):
            return (
                False,
                f"File modification action '{action}' is blocked under the 'safe' permission profile.",
            )

        return True, "Allowed"

    # Normal mode (Default)
    if profile_lower == PermissionLevel.NORMAL.value:
        if action_lower in DESTRUCTIVE_ACTIONS:
            # Check for confirmation
            confirmed = str(parameters.get("confirmed", "")).lower()
            if confirmed not in ("yes", "true", "1", "confirm"):
                return (
                    False,
                    f"Confirmation required: Action '{action}' is classified as a destructive or system-altering operation. Call again with 'confirmed=yes'.",
                )

        return True, "Allowed"

    # Default fallback to Normal mode checks if profile name is invalid
    return check_action(PermissionLevel.NORMAL.value, action, parameters)


def get_tool_metadata(tool_name: str) -> Optional[ToolMetadata]:
    """
    Get metadata for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        ToolMetadata or None if not found
    """
    return TOOL_METADATA.get(tool_name.lower())


def register_tool_metadata(metadata: ToolMetadata):
    """
    Register or update tool metadata.

    Args:
        metadata: ToolMetadata to register
    """
    TOOL_METADATA[metadata.name.lower()] = metadata


def disable_action(action: str):
    """
    Disable an action by name.

    Args:
        action: Action name to disable
    """
    DISABLED_ACTIONS.add(action.lower())


def enable_action(action: str):
    """
    Enable a previously disabled action.

    Args:
        action: Action name to enable
    """
    DISABLED_ACTIONS.discard(action.lower())


def is_action_enabled(action: str) -> bool:
    """
    Check if an action is enabled.

    Args:
        action: Action name to check

    Returns:
        True if enabled, False if disabled
    """
    return action.lower() not in DISABLED_ACTIONS


def get_all_tool_metadata() -> Dict[str, ToolMetadata]:
    """
    Get all registered tool metadata.

    Returns:
        Dictionary of tool metadata
    """
    return TOOL_METADATA.copy()


def get_disabled_actions() -> Set[str]:
    """
    Get all disabled actions.

    Returns:
        Set of disabled action names
    """
    return DISABLED_ACTIONS.copy()
