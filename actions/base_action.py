"""
Base action interface for M.I.C.A AI Assistant.

This module provides a standardized interface that all actions should implement.
This ensures consistency across actions and makes testing and maintenance easier.

Example:
    >>> from actions.base_action import BaseAction, ActionMetadata, ActionPermission
    >>> 
    >>> class MyAction(BaseAction):
    ...     @property
    ...     def metadata(self):
    ...         return ActionMetadata(
    ...             name="my_action",
    ...             description="My custom action",
    ...             permission=ActionPermission.MEDIUM
    ...         )
    ...     
    ...     def execute(self, parameters):
    ...         return "Executed successfully"
    ...     
    ...     def validate_parameters(self, parameters):
    ...         return True
    >>> 
    >>> # Register the action
    >>> from actions.base_action import get_action_registry
    >>> registry = get_action_registry()
    >>> registry.register(MyAction())
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionPermission(Enum):
    """Permission levels for actions."""
    SAFE = "safe"  # No confirmation needed
    MEDIUM = "medium"  # Requires confirmation for medium-risk actions
    HIGH = "high"  # Requires confirmation for high-risk actions
    ADMIN = "admin"  # Requires admin privileges


@dataclass
class ActionMetadata:
    """Metadata for an action."""
    name: str
    description: str
    version: str = "1.0.0"
    permission: ActionPermission = ActionPermission.MEDIUM
    dependencies: List[str] = field(default_factory=list)
    category: str = "general"
    enabled: bool = True


class BaseAction(ABC):
    """
    Base class for all M.I.C.A actions.
    
    All actions should inherit from this class and implement the required methods.
    This provides a consistent interface for action execution, validation, and lifecycle management.
    """
    
    def __init__(self):
        self._metadata: Optional[ActionMetadata] = None
        self._initialized = False
    
    @property
    @abstractmethod
    def metadata(self) -> ActionMetadata:
        """
        Get the action metadata.
        
        Returns:
            ActionMetadata: The action's metadata
        """
        pass
    
    @abstractmethod
    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        Execute the action with the given parameters.
        
        Args:
            parameters: Dictionary of parameters for the action
            
        Returns:
            str: Result message from the action execution
            
        Raises:
            ActionExecutionError: If the action fails to execute
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate the parameters for the action.
        
        Args:
            parameters: Dictionary of parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        pass
    
    def initialize(self) -> None:
        """
        Initialize the action.
        
        Called once when the action is first loaded.
        Override this method to perform any setup needed.
        """
        self._initialized = True
    
    def cleanup(self) -> None:
        """
        Clean up resources used by the action.
        
        Called when the action is being unloaded or the application is shutting down.
        Override this method to release any resources.
        """
        self._initialized = False
    
    def get_required_parameters(self) -> List[str]:
        """
        Get the list of required parameter names.
        
        Returns:
            List[str]: List of required parameter names
        """
        return []
    
    def get_optional_parameters(self) -> Dict[str, Any]:
        """
        Get the optional parameters with their default values.
        
        Returns:
            Dict[str, Any]: Dictionary of optional parameters and their defaults
        """
        return {}
    
    def is_enabled(self) -> bool:
        """
        Check if the action is enabled.
        
        Returns:
            bool: True if the action is enabled
        """
        return self.metadata.enabled
    
    def get_tool_declaration(self) -> Dict[str, Any]:
        """
        Get the tool declaration for this action in the format expected by the AI.
        
        Returns:
            Dict[str, Any]: Tool declaration dictionary
        """
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "parameters": {
                "type": "OBJECT",
                "properties": self._get_parameter_schema(),
                "required": self.get_required_parameters(),
            },
        }
    
    def _get_parameter_schema(self) -> Dict[str, Any]:
        """
        Get the parameter schema for this action.
        
        Returns:
            Dict[str, Any]: Parameter schema dictionary
        """
        schema = {}
        
        # Add required parameters
        for param in self.get_required_parameters():
            schema[param] = {"type": "STRING", "description": f"Parameter: {param}"}
        
        # Add optional parameters
        for param, default in self.get_optional_parameters().items():
            schema[param] = {
                "type": "STRING",
                "description": f"Optional parameter: {param}",
                "default": default,
            }
        
        return schema


class ActionRegistry:
    """
    Registry for managing actions.
    
    Provides a central place to register, retrieve, and manage actions.
    """
    
    def __init__(self):
        self._actions: Dict[str, BaseAction] = {}
    
    def register(self, action: BaseAction) -> None:
        """
        Register an action.
        
        Args:
            action: The action to register
        """
        self._actions[action.metadata.name] = action
        action.initialize()
    
    def unregister(self, action_name: str) -> None:
        """
        Unregister an action.
        
        Args:
            action_name: Name of the action to unregister
        """
        if action_name in self._actions:
            self._actions[action_name].cleanup()
            del self._actions[action_name]
    
    def get(self, action_name: str) -> Optional[BaseAction]:
        """
        Get an action by name.
        
        Args:
            action_name: Name of the action to retrieve
            
        Returns:
            BaseAction or None if not found
        """
        return self._actions.get(action_name)
    
    def get_all(self) -> List[BaseAction]:
        """
        Get all registered actions.
        
        Returns:
            List[BaseAction]: All registered actions
        """
        return list(self._actions.values())
    
    def get_enabled(self) -> List[BaseAction]:
        """
        Get all enabled actions.
        
        Returns:
            List[BaseAction]: All enabled actions
        """
        return [action for action in self._actions.values() if action.is_enabled()]
    
    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        """
        Get tool declarations for all enabled actions.
        
        Returns:
            List[Dict[str, Any]]: Tool declarations for enabled actions
        """
        return [action.get_tool_declaration() for action in self.get_enabled()]


# Global action registry instance
_action_registry: Optional[ActionRegistry] = None


def get_action_registry() -> ActionRegistry:
    """
    Get the global action registry instance.
    
    Returns:
        ActionRegistry: The global action registry
    """
    global _action_registry
    if _action_registry is None:
        _action_registry = ActionRegistry()
    return _action_registry
