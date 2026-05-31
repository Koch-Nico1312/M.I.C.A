"""
Permission Profiles System for Mark-XXXIX
==========================================
Defines permission levels (safe, normal, admin) and checks if actions are allowed.
"""

from enum import Enum

class PermissionLevel(Enum):
    SAFE = "safe"      # Read-only, no modifications
    NORMAL = "normal"  # Modification allowed, dangerous actions require confirmation
    ADMIN = "admin"    # No restrictions

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

def check_action(profile: str, action: str, parameters: dict = None) -> tuple[bool, str]:
    """
    Checks if an action is allowed under the current permission profile.
    
    Returns:
        (is_allowed, status_message)
    """
    if parameters is None:
        parameters = {}
        
    profile_lower = str(profile).lower().strip()
    action_lower = str(action).lower().strip()
    
    # Admin has absolute access
    if profile_lower == PermissionLevel.ADMIN.value:
        return True, "Allowed"
        
    # Safe blocks all destructive/modification actions
    if profile_lower == PermissionLevel.SAFE.value:
        if action_lower in DESTRUCTIVE_ACTIONS:
            return False, f"Action '{action}' is blocked under the 'safe' permission profile."
            
        # File modifications are blocked in safe mode
        if action_lower in ("create_file", "create_folder", "write", "move", "copy", "rename", "organize_desktop"):
            return False, f"File modification action '{action}' is blocked under the 'safe' permission profile."
            
        return True, "Allowed"
        
    # Normal mode (Default)
    if profile_lower == PermissionLevel.NORMAL.value:
        if action_lower in DESTRUCTIVE_ACTIONS:
            # Check for confirmation
            confirmed = str(parameters.get("confirmed", "")).lower()
            if confirmed not in ("yes", "true", "1", "confirm"):
                return False, f"Confirmation required: Action '{action}' is classified as a destructive or system-altering operation. Call again with 'confirmed=yes'."
                
        return True, "Allowed"
        
    # Default fallback to Normal mode checks if profile name is invalid
    return check_action(PermissionLevel.NORMAL.value, action, parameters)
