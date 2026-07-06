"""
Safety and approval system initializer for M.I.C.A AI Assistant.

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
from config.startup_config import get_startup_setting
from core.action_history import get_action_history
from core.approval_flow import get_approval_flow
from core.logger import get_logger
from core.permission_profiles import disable_action

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
    permission_profile = config.get(
        "security.permission_profile", get_startup_setting("security.permission_level")
    )
    approval_flow.set_permission_level(permission_profile)

    # Configure confirmation requirements
    confirm_medium = get_startup_setting("security.confirmation_medium_risk")
    confirm_high = get_startup_setting("security.confirmation_high_risk")
    approval_flow.set_require_confirmation_for_medium(confirm_medium)
    approval_flow.set_require_confirmation_for_high(confirm_high)

    # Load disabled actions from config
    disabled_actions = get_startup_setting("security.disabled_actions")
    for action in disabled_actions:
        disable_action(action)

    logger.info(
        f"Safety system initialized: profile={permission_profile}, "
        f"confirm_medium={confirm_medium}, confirm_high={confirm_high}, "
        f"disabled_actions={len(disabled_actions)}"
    )

    # Initialize action history
    action_history = get_action_history()
    if get_startup_setting("security.action_history_enabled"):
        max_size = get_startup_setting("security.action_history_max_size")
        action_history._max_history_size = max_size
        logger.info(f"Action history enabled with max_size={max_size}")
    else:
        logger.info("Action history disabled by configuration")

    return approval_flow, action_history
