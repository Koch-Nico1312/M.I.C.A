"""
Application initializer for M.I.C.A AI Assistant.

This module handles the application startup logic, including UI initialization
and mode selection (GUI vs CLI).

Example:
    >>> from startup import initialize_application
    >>>
    >>> # Initialize application (defaults to GUI unless --cli is passed)
    >>> use_gui, ui = initialize_application()
    >>>
    >>> if use_gui:
    ...     print("Running in GUI mode")
    ... else:
    ...     print("Running in CLI mode")
"""

import sys
from typing import Any, Optional

from config.startup_config import BASE_DIR


def should_use_gui(argv: list[str] | None = None) -> bool:
    """Return True unless the caller explicitly requested CLI mode."""
    args = sys.argv if argv is None else argv
    return "--cli" not in args


def create_ui_bridge(use_gui: bool = False) -> Any:
    """
    Create and initialize the UI bridge based on the selected mode.
    
    Args:
        use_gui: If True, use GUI mode with Qt. If False, use CLI mode.
        
    Returns:
        UI bridge instance (MicaUI or CLIUIBridge)
    """
    if use_gui:
        print("=" * 60)
        print("M.I.C.A AI Assistant - GUI Mode")
        print("=" * 60)
        print("Starting M.I.C.A with Qt window...")
        print()
        
        # Import the heavy Qt/WebEngine bridge only when GUI mode is actually used.
        from ui_bridge import MicaUI

        ui = MicaUI(str(BASE_DIR / "face.png"))
    else:
        print("=" * 60)
        print("M.I.C.A AI Assistant - CLI Mode")
        print("=" * 60)
        print("Starting M.I.C.A in text-only mode...")
        print()
        
        # Create minimal CLI UI bridge
        ui = CLIUIBridge()

    return ui


def initialize_application(use_gui: bool | None = None) -> tuple[bool, Any]:
    """
    Initialize the M.I.C.A application.

    Args:
        use_gui: If provided, forces GUI or CLI mode. If None, defaults to GUI unless --cli is present.

    Returns:
        tuple: (use_gui, ui_bridge_instance)
    """
    if use_gui is None:
        use_gui = should_use_gui()

    # Create UI bridge
    ui = create_ui_bridge(use_gui)

    return use_gui, ui


class CLIUIBridge:
    """
    Minimal UI bridge for CLI mode without Qt/GUI components.
    Provides a simple text-based interface for M.I.C.A in CLI mode.
    """
    
    def __init__(self):
        self._muted = False
        self._current_file: Optional[str] = None
        self._state = "LISTENING"
        self._on_text_command: Optional[callable] = None
    
    @property
    def muted(self) -> bool:
        return self._muted
    
    @muted.setter
    def muted(self, value: bool):
        self._muted = value
        print(f"[CLI] Microphone {'muted' if value else 'active'}")
    
    @property
    def current_file(self) -> Optional[str]:
        return self._current_file
    
    @current_file.setter
    def current_file(self, value: Optional[str]):
        self._current_file = value
        if value:
            print(f"[CLI] Current file: {value}")
    
    @property
    def on_text_command(self) -> Optional[callable]:
        return self._on_text_command
    
    @on_text_command.setter
    def on_text_command(self, cb: Optional[callable]):
        self._on_text_command = cb
    
    def set_state(self, state: str):
        """Set the current state of M.I.C.A."""
        self._state = state
        print(f"[CLI] State: {state}")
    
    def write_log(self, message: str):
        """Write a log message to the console."""
        print(f"[LOG] {message}")
    
    def wait_for_api_key(self):
        """Wait for API key - CLI mode assumes key is already configured."""
        print("[CLI] Assuming API key is configured in .env file")
    
    def root(self):
        """No root.mainloop in CLI mode."""
        pass
