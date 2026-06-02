"""
Startup module for JARVIS AI Assistant.

This module handles application initialization and startup logic.
"""

from .app_initializer import initialize_application, create_ui_bridge
from .performance_initializer import initialize_performance_system
from .safety_initializer import initialize_safety_system

__all__ = [
    "initialize_application",
    "create_ui_bridge",
    "initialize_performance_system",
    "initialize_safety_system",
]
