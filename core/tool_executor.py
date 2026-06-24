"""
Tool executor module for JARVIS AI Assistant.

This module provides:
- Tool execution and routing
- Tool result handling
- Tool performance tracking
- Tool error handling
- Parallel tool execution
"""

import asyncio
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger
from core.action_history import ActionStatus, get_action_history
from core.approval_flow import get_approval_flow
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags
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
        self.max_parallel_tools = 4
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
        self, name: str, args: Dict[str, Any], player=None, speak: Optional[Callable] = None
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

        start_perf = time.perf_counter()
        success = True
        error = None
        result = "Done."
        action = str(args.get("action", name) or name)
        history = get_action_history()

        try:
            allowed, approval_message = get_approval_flow().check_and_request_approval(
                name, action, args
            )
        except Exception as approval_error:
            allowed = False
            approval_message = f"Approval check failed: {approval_error}"

        if not allowed:
            duration_ms = (time.perf_counter() - start_perf) * 1000
            result = approval_message
            error = approval_message
            try:
                history.record_action(
                    tool_name=name,
                    action=action,
                    parameters=args,
                    result=str(result),
                    status=ActionStatus.FAILED,
                )
            except Exception as history_error:
                logger.debug(f"Tool history write skipped: {history_error}")
            return {
                "name": name,
                "result": result,
                "success": False,
                "error": error,
                "duration_ms": duration_ms,
                "approval_required": "confirmation" in approval_message.lower()
                or "approval" in approval_message.lower(),
            }

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
                success = False
                error = result
                logger.warning(f"Attempted to execute unknown tool: {name}")

        except Exception as e:
            success = False
            error = str(e)
            result = f"Tool '{name}' failed: {e}"
            logger.error(f"Tool execution failed: {name} - {e}")
            traceback.print_exc()

        # Track performance
        duration_ms = (time.perf_counter() - start_perf) * 1000
        try:
            history.record_action(
                tool_name=name,
                action=action,
                parameters=args,
                result=str(result),
                status=ActionStatus.SUCCESS if success else ActionStatus.FAILED,
            )
        except Exception as history_error:
            logger.debug(f"Tool history write skipped: {history_error}")

        try:
            self.perf_monitor.track_tool_execution(
                tool_name=name,
                action=action,
                duration_ms=duration_ms,
                success=success,
                error=error,
                parameters=args,
                result_size=len(str(result).encode("utf-8")),
            )
        except Exception as perf_error:
            logger.debug(f"Tool execution metrics skipped: {perf_error}")
        self.perf_monitor.track_api_call(
            endpoint=f"tool_{name}", duration_ms=duration_ms, success=success, error=error
        )

        logger.info(f"Tool result: {name} → {str(result)[:80]}")

        return {
            "name": name,
            "result": result,
            "success": success,
            "error": error,
            "duration_ms": duration_ms,
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

    async def execute_tools_parallel(
        self, tool_calls: List[Dict[str, Any]], player=None, speak: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tools in parallel.

        Args:
            tool_calls: List of tool call dictionaries with 'name' and 'args'
            player: Player instance for UI updates
            speak: Speak callback function

        Returns:
            List of tool execution results
        """
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        if not perf_flags.is_enabled("parallel_tool_execution"):
            # Fallback to sequential execution
            results = []
            for tool_call in tool_calls:
                result = await self.execute_tool(
                    tool_call["name"], tool_call["args"], player, speak
                )
                results.append(result)
            return results

        metrics.start_operation("parallel_tool_execution")

        # Determine which tools can be executed in parallel
        # Tools that depend on each other's results should be executed sequentially
        independent_tools = []
        dependent_tools = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            # Simple heuristic: tools with no dependencies can run in parallel
            # In a real implementation, you'd have a dependency graph
            if tool_name in ["file_processor", "web_search", "computer_control"]:
                independent_tools.append(tool_call)
            else:
                dependent_tools.append(tool_call)

        # Execute independent tools in parallel
        parallel_results = []
        if independent_tools:
            tasks = [
                self.execute_tool(tc["name"], tc["args"], player, speak) for tc in independent_tools
            ]
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Execute dependent tools sequentially
        sequential_results = []
        for tool_call in dependent_tools:
            result = await self.execute_tool(tool_call["name"], tool_call["args"], player, speak)
            sequential_results.append(result)

        # Combine results
        all_results = []
        for result in parallel_results:
            if isinstance(result, Exception):
                all_results.append(
                    {
                        "name": "unknown",
                        "result": str(result),
                        "success": False,
                        "error": str(result),
                        "duration_ms": 0,
                    }
                )
            else:
                all_results.append(result)

        all_results.extend(sequential_results)

        metrics.end_operation(
            "parallel_tool_execution",
            {
                "total_tools": len(tool_calls),
                "parallel_tools": len(independent_tools),
                "sequential_tools": len(dependent_tools),
            },
        )

        logger.info(f"Executed {len(tool_calls)} tools ({len(independent_tools)} parallel)")
        return all_results


# Global instance
_tool_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutor()
    return _tool_executor
