"""
Performance monitoring system for JARVIS AI Assistant.

This module provides:
- API call tracking with metrics
- Response time monitoring
- Resource usage monitoring (CPU, RAM, Memory)
- Performance statistics and reporting
"""

import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from core.logger import get_logger
from core.paths import project_path

logger = get_logger(__name__)


@dataclass
class APICallMetrics:
    """Metrics for a single API call."""

    endpoint: str
    timestamp: datetime
    duration_ms: float
    success: bool
    error: Optional[str] = None
    tokens_used: Optional[int] = None


@dataclass
class ToolExecutionMetrics:
    """Metrics for a single tool execution."""

    tool_name: str
    action: str
    timestamp: datetime
    duration_ms: float
    success: bool
    error: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    result_size: Optional[int] = None  # Size of result in bytes


@dataclass
class LatencyMetrics:
    """Detailed latency breakdown for an operation."""

    operation_type: str
    timestamp: datetime
    total_duration_ms: float
    queue_time_ms: float = 0.0
    processing_time_ms: float = 0.0
    network_time_ms: float = 0.0
    ui_response_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


@dataclass
class ResourceSnapshot:
    """Snapshot of system resource usage."""

    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_usage_percent: float
    active_threads: int


class PerformanceMonitor:
    """
    Monitors system performance and API calls for JARVIS.
    """

    def __init__(
        self,
        max_api_calls: int = 1000,
        max_tool_executions: int = 1000,
        max_latency_metrics: int = 1000,
        max_resource_snapshots: int = 1440,  # 24 hours at 1-minute intervals
        resource_interval_seconds: float = 60.0,
    ):
        """
        Initialize the performance monitor.

        Args:
            max_api_calls: Maximum number of API call records to keep
            max_tool_executions: Maximum number of tool execution records to keep
            max_latency_metrics: Maximum number of latency metric records to keep
            max_resource_snapshots: Maximum number of resource snapshots to keep
            resource_interval_seconds: Interval between resource snapshots
        """
        self.max_api_calls = max_api_calls
        self.max_tool_executions = max_tool_executions
        self.max_latency_metrics = max_latency_metrics
        self.max_resource_snapshots = max_resource_snapshots
        self.resource_interval_seconds = resource_interval_seconds

        self.api_calls: List[APICallMetrics] = []
        self.tool_executions: List[ToolExecutionMetrics] = []
        self.latency_metrics: List[LatencyMetrics] = []
        self.resource_snapshots: List[ResourceSnapshot] = []
        self.api_call_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_calls": 0,
                "successful": 0,
                "failed": 0,
                "total_duration_ms": 0.0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": float("inf"),
                "max_duration_ms": 0.0,
                "total_tokens": 0,
            }
        )
        self.tool_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_calls": 0,
                "successful": 0,
                "failed": 0,
                "total_duration_ms": 0.0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": float("inf"),
                "max_duration_ms": 0.0,
                "total_result_size": 0,
            }
        )

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        logger.info("Performance monitor initialized")

    def track_api_call(
        self,
        endpoint: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ):
        """
        Record an API call with its metrics.

        Args:
            endpoint: API endpoint or service name
            duration_ms: Call duration in milliseconds
            success: Whether the call was successful
            error: Error message if failed
            tokens_used: Number of tokens used (if applicable)
        """
        with self._lock:
            metrics = APICallMetrics(
                endpoint=endpoint,
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                success=success,
                error=error,
                tokens_used=tokens_used,
            )

            self.api_calls.append(metrics)

            # Trim old records
            if len(self.api_calls) > self.max_api_calls:
                self.api_calls = self.api_calls[-self.max_api_calls :]

            # Update statistics
            stats = self.api_call_stats[endpoint]
            stats["total_calls"] += 1
            stats["total_duration_ms"] += duration_ms
            stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_calls"]
            stats["min_duration_ms"] = min(stats["min_duration_ms"], duration_ms)
            stats["max_duration_ms"] = max(stats["max_duration_ms"], duration_ms)

            if success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1

            if tokens_used:
                stats["total_tokens"] += tokens_used

            logger.debug(
                f"API call tracked: {endpoint} - {duration_ms:.2f}ms - {'SUCCESS' if success else 'FAILED'}"
            )

    def track_tool_execution(
        self,
        tool_name: str,
        action: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        result_size: Optional[int] = None,
    ):
        """
        Record a tool execution with its metrics.

        Args:
            tool_name: Name of the tool
            action: Specific action performed
            duration_ms: Execution duration in milliseconds
            success: Whether the execution was successful
            error: Error message if failed
            parameters: Tool parameters (optional, for analysis)
            result_size: Size of result in bytes (optional)
        """
        with self._lock:
            metrics = ToolExecutionMetrics(
                tool_name=tool_name,
                action=action,
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                success=success,
                error=error,
                parameters=parameters,
                result_size=result_size,
            )

            self.tool_executions.append(metrics)

            # Trim old records
            if len(self.tool_executions) > self.max_tool_executions:
                self.tool_executions = self.tool_executions[-self.max_tool_executions :]

            # Update statistics
            stats_key = f"{tool_name}:{action}"
            stats = self.tool_stats[stats_key]
            stats["total_calls"] += 1
            stats["total_duration_ms"] += duration_ms
            stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_calls"]
            stats["min_duration_ms"] = min(stats["min_duration_ms"], duration_ms)
            stats["max_duration_ms"] = max(stats["max_duration_ms"], duration_ms)

            if success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1

            if result_size:
                stats["total_result_size"] += result_size

            logger.debug(
                f"Tool execution tracked: {tool_name}/{action} - {duration_ms:.2f}ms - {'SUCCESS' if success else 'FAILED'}"
            )

    def track_latency(
        self,
        operation_type: str,
        total_duration_ms: float,
        queue_time_ms: float = 0.0,
        processing_time_ms: float = 0.0,
        network_time_ms: float = 0.0,
        ui_response_time_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """
        Record detailed latency breakdown for an operation.

        Args:
            operation_type: Type of operation (e.g., "model_call", "tool_execution", "file_operation")
            total_duration_ms: Total duration in milliseconds
            queue_time_ms: Time spent in queue
            processing_time_ms: Actual processing time
            network_time_ms: Network latency
            ui_response_time_ms: UI response time
            success: Whether the operation was successful
            error: Error message if failed
        """
        with self._lock:
            metrics = LatencyMetrics(
                operation_type=operation_type,
                timestamp=datetime.now(),
                total_duration_ms=total_duration_ms,
                queue_time_ms=queue_time_ms,
                processing_time_ms=processing_time_ms,
                network_time_ms=network_time_ms,
                ui_response_time_ms=ui_response_time_ms,
                success=success,
                error=error,
            )

            self.latency_metrics.append(metrics)

            # Trim old records
            if len(self.latency_metrics) > self.max_latency_metrics:
                self.latency_metrics = self.latency_metrics[-self.max_latency_metrics :]

            logger.debug(
                f"Latency tracked: {operation_type} - total={total_duration_ms:.2f}ms, "
                f"queue={queue_time_ms:.2f}ms, processing={processing_time_ms:.2f}ms, "
                f"network={network_time_ms:.2f}ms, ui={ui_response_time_ms:.2f}ms"
            )

    def get_api_stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get API call statistics.

        Args:
            endpoint: Specific endpoint to query, or None for all endpoints

        Returns:
            Dictionary containing statistics
        """
        with self._lock:
            if endpoint:
                return dict(self.api_call_stats.get(endpoint, {}))

            # Aggregate all endpoints
            total_stats = {
                "total_calls": 0,
                "successful": 0,
                "failed": 0,
                "total_duration_ms": 0.0,
                "avg_duration_ms": 0.0,
                "total_tokens": 0,
                "endpoints": {},
            }

            for ep, stats in self.api_call_stats.items():
                total_stats["total_calls"] += stats["total_calls"]
                total_stats["successful"] += stats["successful"]
                total_stats["failed"] += stats["failed"]
                total_stats["total_duration_ms"] += stats["total_duration_ms"]
                total_stats["total_tokens"] += stats["total_tokens"]
                total_stats["endpoints"][ep] = dict(stats)

            if total_stats["total_calls"] > 0:
                total_stats["avg_duration_ms"] = (
                    total_stats["total_duration_ms"] / total_stats["total_calls"]
                )

            return total_stats

    def get_tool_stats(
        self, tool_name: Optional[str] = None, action: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get tool execution statistics.

        Args:
            tool_name: Specific tool to query, or None for all tools
            action: Specific action to query, or None for all actions

        Returns:
            Dictionary containing statistics
        """
        with self._lock:
            if tool_name and action:
                stats_key = f"{tool_name}:{action}"
                return dict(self.tool_stats.get(stats_key, {}))

            # Filter by tool name only
            if tool_name:
                filtered_stats = {}
                for key, stats in self.tool_stats.items():
                    if key.startswith(f"{tool_name}:"):
                        filtered_stats[key] = dict(stats)
                return filtered_stats

            # Return all tool stats
            return dict(self.tool_stats)

    def get_latency_stats(self, operation_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get latency statistics.

        Args:
            operation_type: Specific operation type to query, or None for all

        Returns:
            Dictionary containing latency statistics
        """
        with self._lock:
            if operation_type:
                filtered = [m for m in self.latency_metrics if m.operation_type == operation_type]
            else:
                filtered = self.latency_metrics

            if not filtered:
                return {"error": "No latency data available"}

            total_durations = [m.total_duration_ms for m in filtered]
            queue_times = [m.queue_time_ms for m in filtered]
            processing_times = [m.processing_time_ms for m in filtered]
            network_times = [m.network_time_ms for m in filtered]
            ui_times = [m.ui_response_time_ms for m in filtered]

            # Calculate percentiles
            sorted_durations = sorted(total_durations)
            p95_index = int(len(sorted_durations) * 0.95)
            p95 = (
                sorted_durations[p95_index]
                if p95_index < len(sorted_durations)
                else sorted_durations[-1]
            )

            return {
                "total_operations": len(filtered),
                "total_duration": {
                    "avg": sum(total_durations) / len(total_durations),
                    "min": min(total_durations),
                    "max": max(total_durations),
                    "median": sorted_durations[len(sorted_durations) // 2],
                    "p95": p95,
                },
                "queue_time": {
                    "avg": sum(queue_times) / len(queue_times),
                    "min": min(queue_times),
                    "max": max(queue_times),
                },
                "processing_time": {
                    "avg": sum(processing_times) / len(processing_times),
                    "min": min(processing_times),
                    "max": max(processing_times),
                },
                "network_time": {
                    "avg": sum(network_times) / len(network_times),
                    "min": min(network_times),
                    "max": max(network_times),
                },
                "ui_response_time": {
                    "avg": sum(ui_times) / len(ui_times),
                    "min": min(ui_times),
                    "max": max(ui_times),
                },
                "success_rate": sum(1 for m in filtered if m.success) / len(filtered),
            }

    def get_slowest_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the slowest operations.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of slowest operations with details
        """
        with self._lock:
            # Combine API calls and tool executions
            all_ops = []

            for api in self.api_calls:
                all_ops.append(
                    {
                        "type": "api_call",
                        "name": api.endpoint,
                        "duration_ms": api.duration_ms,
                        "timestamp": api.timestamp.isoformat(),
                        "success": api.success,
                        "error": api.error,
                    }
                )

            for tool in self.tool_executions:
                all_ops.append(
                    {
                        "type": "tool_execution",
                        "name": f"{tool.tool_name}/{tool.action}",
                        "duration_ms": tool.duration_ms,
                        "timestamp": tool.timestamp.isoformat(),
                        "success": tool.success,
                        "error": tool.error,
                    }
                )

            # Sort by duration and return slowest
            all_ops.sort(key=lambda x: x["duration_ms"], reverse=True)
            return all_ops[:limit]

    def capture_resource_snapshot(self) -> ResourceSnapshot:
        """
        Capture current system resource usage.

        Returns:
            ResourceSnapshot with current metrics
        """
        try:
            process = psutil.Process()

            snapshot = ResourceSnapshot(
                timestamp=datetime.now(),
                cpu_percent=psutil.cpu_percent(interval=0.1),
                memory_percent=psutil.virtual_memory().percent,
                memory_mb=psutil.virtual_memory().used / (1024 * 1024),
                disk_usage_percent=(
                    psutil.disk_usage("/").percent
                    if Path("/").exists()
                    else psutil.disk_usage("C:\\").percent
                ),
                active_threads=process.num_threads(),
            )

            with self._lock:
                self.resource_snapshots.append(snapshot)

                # Trim old snapshots
                if len(self.resource_snapshots) > self.max_resource_snapshots:
                    self.resource_snapshots = self.resource_snapshots[
                        -self.max_resource_snapshots :
                    ]

            logger.debug(
                f"Resource snapshot captured: CPU={snapshot.cpu_percent:.1f}%, RAM={snapshot.memory_percent:.1f}%"
            )
            return snapshot

        except Exception as e:
            logger.error(f"Failed to capture resource snapshot: {e}")
            raise

    def get_resource_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """
        Get resource usage statistics over a time window.

        Args:
            minutes: Number of minutes to look back

        Returns:
            Dictionary containing resource statistics
        """
        with self._lock:
            cutoff = datetime.now().timestamp() - (minutes * 60)
            recent_snapshots = [
                s for s in self.resource_snapshots if s.timestamp.timestamp() >= cutoff
            ]

            if not recent_snapshots:
                return {"error": "No resource data available"}

            cpu_values = [s.cpu_percent for s in recent_snapshots]
            memory_values = [s.memory_percent for s in recent_snapshots]
            memory_mb_values = [s.memory_mb for s in recent_snapshots]
            thread_values = [s.active_threads for s in recent_snapshots]

            return {
                "period_minutes": minutes,
                "snapshot_count": len(recent_snapshots),
                "cpu": {
                    "avg": sum(cpu_values) / len(cpu_values),
                    "min": min(cpu_values),
                    "max": max(cpu_values),
                    "current": cpu_values[-1],
                },
                "memory": {
                    "avg_percent": sum(memory_values) / len(memory_values),
                    "min_percent": min(memory_values),
                    "max_percent": max(memory_values),
                    "current_percent": memory_values[-1],
                    "avg_mb": sum(memory_mb_values) / len(memory_mb_values),
                    "current_mb": memory_mb_values[-1],
                },
                "threads": {
                    "avg": sum(thread_values) / len(thread_values),
                    "min": min(thread_values),
                    "max": max(thread_values),
                    "current": thread_values[-1],
                },
            }

    def start_monitoring(self):
        """Start background resource monitoring."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Resource monitoring thread already running")
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="PerformanceMonitorThread"
        )
        self._monitor_thread.start()
        logger.info(f"Performance monitoring started (interval: {self.resource_interval_seconds}s)")

    def _monitor_loop(self):
        """Background thread loop for resource monitoring."""
        while not self._stop_event.is_set():
            try:
                self.capture_resource_snapshot()
            except Exception as e:
                logger.error(f"Resource monitoring failed: {e}")

            self._stop_event.wait(timeout=self.resource_interval_seconds)

    def stop_monitoring(self):
        """Stop background resource monitoring."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_event.set()
            self._monitor_thread.join(timeout=5)
            logger.info("Performance monitoring stopped")

    def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.

        Returns:
            Dictionary containing all performance metrics
        """
        with self._lock:
            report = {
                "generated_at": datetime.now().isoformat(),
                "api_calls": self.get_api_stats(),
                "tool_executions": self.get_tool_stats(),
                "latency": self.get_latency_stats(),
                "resources": self.get_resource_stats(minutes=60),
                "slowest_operations": self.get_slowest_operations(limit=10),
                "recent_api_calls": [
                    {
                        "endpoint": m.endpoint,
                        "timestamp": m.timestamp.isoformat(),
                        "duration_ms": m.duration_ms,
                        "success": m.success,
                        "error": m.error,
                    }
                    for m in self.api_calls[-10:]
                ],
                "recent_tool_executions": [
                    {
                        "tool_name": m.tool_name,
                        "action": m.action,
                        "timestamp": m.timestamp.isoformat(),
                        "duration_ms": m.duration_ms,
                        "success": m.success,
                        "error": m.error,
                    }
                    for m in self.tool_executions[-10:]
                ],
            }
            return report

    def save_report(self, path: Optional[Path] = None):
        """
        Save performance report to a JSON file.

        Args:
            path: Path to save the report (defaults to ./logs/performance_report.json)
        """
        if path is None:
            path = project_path("logs", "performance_report.json")

        path.parent.mkdir(parents=True, exist_ok=True)

        report = self.get_performance_report()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Performance report saved to {path}")


# Global instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def track_api_call_decorator(endpoint: str):
    """
    Decorator to automatically track API calls.

    Args:
        endpoint: API endpoint or service name
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.perf_counter()
            success = True
            error = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                monitor.track_api_call(
                    endpoint=endpoint, duration_ms=duration_ms, success=success, error=error
                )

        return wrapper

    return decorator
