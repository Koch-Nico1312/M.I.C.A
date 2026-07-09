"""
Tool executor module for M.I.C.A AI Assistant.

This module provides:
- Tool execution and routing
- Tool result handling
- Tool performance tracking
- Tool error handling
- Parallel tool execution
"""

import asyncio
import concurrent.futures
import inspect
import math
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from config.config_loader import get_config
from core.logger import get_logger
from core.action_history import ActionStatus, get_action_history
from core.approval_flow import get_approval_flow
from core.metrics_collector import get_metrics_collector
from core.langfuse_tracing import trace_tool_execution
from core.performance_flags import get_performance_flags
from core.performance_monitor import get_performance_monitor

logger = get_logger(__name__)


def check_action(*_args: Any, **_kwargs: Any) -> tuple[bool, str]:
    """Compatibility hook for older tests and integrations."""
    return True, "Allowed"


class _AwaitableToolResult:
    def __init__(
        self,
        *,
        raw: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        coro: Optional[Any] = None,
    ) -> None:
        self.raw = raw
        self.metadata = metadata
        self._coro = coro

    def __await__(self):
        async def _wait():
            if self._coro is not None:
                return await self._coro
            return self.metadata

        return _wait().__await__()

    def __eq__(self, other: object) -> bool:
        return self.raw == other

    def __str__(self) -> str:
        return str(self.raw)

    def __repr__(self) -> str:
        return repr(self.raw)


class ToolExecutor:
    """
    Manages tool execution for M.I.C.A.
    """

    def __init__(self):
        """Initialize tool executor."""
        self.tool_registry: Dict[str, Callable] = {}
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}
        self.default_timeout = 30
        self.perf_monitor = get_performance_monitor()
        self.max_parallel_tools = 4
        sample_rate = float(get_config().get("performance.tool_metrics_sample_rate", 1.0) or 1.0)
        self._metrics_sample_interval = max(1, math.ceil(1.0 / max(0.01, min(1.0, sample_rate))))
        self._metrics_counter = 0
        logger.info("Tool executor initialized")

    @property
    def tools(self) -> Dict[str, Callable]:
        return self.tool_registry

    def register_tool(
        self,
        name: str,
        func: Callable,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        **metadata: Any,
    ) -> None:
        """
        Register a tool function.

        Args:
            name: Tool name
            func: Tool function
        """
        self.tool_registry[name] = func
        self.tool_metadata[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {},
            **metadata,
        }
        logger.debug(f"Registered tool: {name}")

    def register_tool_from_declaration(self, declaration: Dict[str, Any]) -> None:
        """Register a declaration placeholder so tool catalogs can be inspected."""
        name = str(declaration.get("name") or "").strip()
        if not name:
            return

        def _placeholder(*_args: Any, **_kwargs: Any) -> str:
            return f"Tool declaration registered: {name}"

        self.register_tool(
            name,
            _placeholder,
            description=str(declaration.get("description") or ""),
            parameters=declaration.get("parameters") or {},
        )

    def unregister_tool(self, name: str) -> None:
        """
        Unregister a tool function.

        Args:
            name: Tool name
        """
        if name in self.tool_registry:
            del self.tool_registry[name]
            self.tool_metadata.pop(name, None)
            logger.debug(f"Unregistered tool: {name}")

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        metadata = self.tool_metadata.get(name)
        if not metadata:
            return None
        return dict(metadata)

    def list_tools(self) -> List[str]:
        return list(self.tool_registry.keys())

    def execute_tool(
        self, name: str, args: Dict[str, Any], player=None, speak: Optional[Callable] = None
    ) -> Any:
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
        try:
            asyncio.get_running_loop()
            in_running_loop = True
        except RuntimeError:
            in_running_loop = False

        if in_running_loop:
            return _AwaitableToolResult(
                coro=self._execute_tool_async(
                    name, args, player=player, speak=speak, raise_errors=False
                )
            )

        metadata = asyncio.run(
            self._execute_tool_async(name, args, player=player, speak=speak, raise_errors=True)
        )
        return _AwaitableToolResult(raw=metadata["result"], metadata=metadata)

    async def execute_tool_async(
        self, name: str, args: Dict[str, Any], player=None, speak: Optional[Callable] = None
    ) -> Any:
        metadata = await self._execute_tool_async(
            name, args, player=player, speak=speak, raise_errors=True
        )
        return metadata["result"]

    async def _execute_tool_async(
        self,
        name: str,
        args: Dict[str, Any],
        player=None,
        speak: Optional[Callable] = None,
        *,
        raise_errors: bool,
    ) -> Dict[str, Any]:
        logger.info(f"Executing tool: {name} with args {args}")

        if name not in self.tool_registry:
            if raise_errors:
                raise KeyError(name)
            duration_ms = 0.0
            return {
                "name": name,
                "result": f"Unknown tool: {name}",
                "success": False,
                "error": f"Unknown tool: {name}",
                "duration_ms": duration_ms,
            }

        self._validate_parameters(name, args)
        start_perf = time.perf_counter()
        success = True
        error = None
        result = "Done."
        action = str(args.get("action", name) or name)
        history = get_action_history()

        try:
            check_allowed, check_message = check_action(name, action, args)
            if not check_allowed:
                raise PermissionError(check_message)
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
            with trace_tool_execution(name, args) as langfuse_span:
                func = self.tool_registry[name]
                result = await self._invoke_tool(func, args, player, speak)
                result_text = str(result)
                langfuse_span.update(
                    output=result_text[:8000],
                    metadata={"success": success, "error": error},
                )

        except Exception as e:
            success = False
            error = str(e)
            result = f"Tool '{name}' failed: {e}"
            result_text = str(result)
            logger.error(f"Tool execution failed: {name} - {e}")
            traceback.print_exc()
            if raise_errors:
                raise

        # Track performance
        duration_ms = (time.perf_counter() - start_perf) * 1000
        result_size = len(result_text.encode("utf-8"))
        try:
            history.record_action(
                tool_name=name,
                action=action,
                parameters=args,
                result=result_text,
                status=ActionStatus.SUCCESS if success else ActionStatus.FAILED,
            )
        except Exception as history_error:
            logger.debug(f"Tool history write skipped: {history_error}")

        if self._should_track_metrics(duration_ms, success):
            try:
                self.perf_monitor.track_tool_execution(
                    tool_name=name,
                    action=action,
                    duration_ms=duration_ms,
                    success=success,
                    error=error,
                    parameters=args,
                    result_size=result_size,
                )
            except Exception as perf_error:
                logger.debug(f"Tool execution metrics skipped: {perf_error}")
            self.perf_monitor.track_api_call(
                endpoint=f"tool_{name}", duration_ms=duration_ms, success=success, error=error
            )

        logger.info(f"Tool result: {name} → {result_text[:80]}")

        return {
            "name": name,
            "result": result,
            "success": success,
            "error": error,
            "duration_ms": duration_ms,
        }

    def _should_track_metrics(self, duration_ms: float, success: bool) -> bool:
        if not success or duration_ms >= self.default_timeout * 1000:
            return True
        if self._metrics_sample_interval <= 1:
            return True
        self._metrics_counter = (self._metrics_counter + 1) % self._metrics_sample_interval
        return self._metrics_counter == 0

    def _validate_parameters(self, name: str, args: Dict[str, Any]) -> None:
        schema = self.tool_metadata.get(name, {}).get("parameters") or {}
        required = schema.get("required") or []
        for field in required:
            if field not in args:
                raise ValueError(f"Missing required parameter: {field}")

        properties = schema.get("properties") or {}
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        for field, spec in properties.items():
            if field not in args:
                continue
            expected = type_map.get(str(spec.get("type", "")).lower())
            if expected and not isinstance(args[field], expected):
                raise TypeError(f"Invalid type for {field}: expected {spec.get('type')}")

    async def _invoke_tool(
        self, func: Callable, args: Dict[str, Any], player=None, speak: Optional[Callable] = None
    ) -> Any:
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(
                self._call_async_func(func, args, player, speak),
                timeout=self.default_timeout,
            )

        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, self._call_sync_func, func, args, player, speak),
            timeout=self.default_timeout,
        )

    async def _call_async_func(
        self, func: Callable, args: Dict[str, Any], player=None, speak: Optional[Callable] = None
    ) -> Any:
        call_args, call_kwargs = self._prepare_call(func, args, player, speak)
        return await func(*call_args, **call_kwargs)

    def _call_sync_func(
        self, func: Callable, args: Dict[str, Any], player=None, speak: Optional[Callable] = None
    ) -> Any:
        call_args, call_kwargs = self._prepare_call(func, args, player, speak)
        return func(*call_args, **call_kwargs)

    def _prepare_call(
        self, func: Callable, args: Dict[str, Any], player=None, speak: Optional[Callable] = None
    ) -> tuple[list[Any], Dict[str, Any]]:
        try:
            signature = inspect.signature(func)
            params = list(signature.parameters.values())
        except (TypeError, ValueError):
            return [args, player, speak], {}

        if params and params[0].name in {"args", "parameters"}:
            call_args: list[Any] = [args]
            if len(params) > 1:
                call_args.append(player)
            if len(params) > 2:
                call_args.append(speak)
            return call_args, {}

        return [], dict(args)

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
                result = await self._execute_tool_async(
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
                self._execute_tool_async(tc["name"], tc["args"], player, speak, raise_errors=False)
                for tc in independent_tools
            ]
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Execute dependent tools sequentially
        sequential_results = []
        for tool_call in dependent_tools:
            result = await self._execute_tool_async(
                tool_call["name"], tool_call["args"], player, speak, raise_errors=False
            )
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
