"""
Safety and approval system initializer for JARVIS AI Assistant.

This module handles initialization of safety, approval flow, and action history.

Example:
    >>> from startup.safety_initializer import initialize_safety_system
    >>> 
    >>> # Initialize safety system
    >>> approval_flow, action_history = initialize_safety_system()
    >>> 
    >>> # Use the initialized components
    >>> approval_flow.set_permission_level("normal")
    >>> action_history.add_action("test_action", {"param": "value"})
"""

from config.config_loader import get_config
from core.action_history import get_action_history
from core.approval_flow import get_approval_flow
from core.logger import get_logger
from core.permission_profiles import disable_action
from core.paths import project_path

logger = get_logger(__name__)


def initialize_safety_system():
    """
    Initialize the safety and approval system.
    
    Returns:
        tuple: (approval_flow, action_history)
    """
    config = get_config()

    # Initialize safety and approval system
    approval_flow = get_approval_flow()
    permission_profile = config.get("security.permission_profile", "normal")
    approval_flow.set_permission_level(permission_profile)

    # Configure confirmation requirements
    confirm_medium = config.get("security.confirmation_medium_risk", True)
    confirm_high = config.get("security.confirmation_high_risk", True)
    approval_flow.set_require_confirmation_for_medium(confirm_medium)

    # Load disabled actions from config
    disabled_actions = config.get("security.disabled_actions", [])
    for action in disabled_actions:
        disable_action(action)

    logger.info(
        f"Safety system initialized: profile={permission_profile}, "
        f"confirm_medium={confirm_medium}, confirm_high={confirm_high}, "
        f"disabled_actions={len(disabled_actions)}"
    )

    # Initialize action history
    action_history = get_action_history()
    if config.get("security.action_history_enabled", True):
        max_size = config.get("security.action_history_max_size", 1000)
        action_history._max_history_size = max_size
        logger.info(f"Action history enabled with max_size={max_size}")
    else:
        logger.info("Action history disabled by configuration")

    return approval_flow, action_history
