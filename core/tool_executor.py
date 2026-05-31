"""
Tool executor module for JARVIS AI Assistant.

This module provides:
- Tool execution and routing
- Tool result handling
- Tool performance tracking
- Tool error handling
"""

import asyncio
import traceback
from typing import Any, Optional, Callable, Dict
from datetime import datetime

from core.logger import get_logger
from core.performance_monitor import get_performance_monitor

logger = get_logger(__name__)


class ToolExecutor:
    """
    Manages tool execution for JARVIS.
    """
    
    def __init__(self):
        """Initialize tool executor."""
        self.tool_registry: Dict[str, Callable] = {}
        self.perf_monitor = get_performance_monitor()
        logger.info("Tool executor initialized")
    
    def register_tool(self, name: str, func: Callable) -> None:
        """
        Register a tool function.
        
        Args:
            name: Tool name
            func: Tool function
        """
        self.tool_registry[name] = func
        logger.debug(f"Registered tool: {name}")
    
    def unregister_tool(self, name: str) -> None:
        """
        Unregister a tool function.
        
        Args:
            name: Tool name
        """
        if name in self.tool_registry:
            del self.tool_registry[name]
            logger.debug(f"Unregistered tool: {name}")
    
    async def execute_tool(
        self,
        name: str,
        args: Dict[str, Any],
        player=None,
        speak: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Args:
            name: Tool name
            args: Tool arguments
            player: Player instance for UI updates
            speak: Speak callback function
        
        Returns:
            Tool execution result
        """
        logger.info(f"Executing tool: {name} with args {args}")
        
        start_time = datetime.now()
        success = True
        error = None
        result = "Done."
        
        try:
            if name in self.tool_registry:
                # Execute registered tool
                func = self.tool_registry[name]
                if asyncio.iscoroutinefunction(func):
                    result = await func(args, player, speak)
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, func, args, player, speak)
            else:
                result = f"Unknown tool: {name}"
                logger.warning(f"Attempted to execute unknown tool: {name}")
        
        except Exception as e:
            success = False
            error = str(e)
            result = f"Tool '{name}' failed: {e}"
            logger.error(f"Tool execution failed: {name} - {e}")
            traceback.print_exc()
        
        # Track performance
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.perf_monitor.track_api_call(
            endpoint=f"tool_{name}",
            duration_ms=duration_ms,
            success=success,
            error=error
        )
        
        logger.info(f"Tool result: {name} → {str(result)[:80]}")
        
        return {
            "name": name,
            "result": result,
            "success": success,
            "error": error,
            "duration_ms": duration_ms
        }
    
    def get_registered_tools(self) -> list[str]:
        """
        Get list of registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self.tool_registry.keys())
    
    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is registered.
        
        Args:
            name: Tool name
        
        Returns:
            True if tool is registered
        """
        return name in self.tool_registry


# Global instance
_tool_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutor()
    return _tool_executor
