"""
Performance Metrics Collector for M.I.C.A AI Assistant
======================================================
Collects and tracks performance metrics before/after optimizations.
"""

import threading
import time
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
psutil = None


def _get_psutil():
    """Import psutil only when process/system metrics are actually captured."""
    global psutil
    if psutil is None:
        try:
            import psutil as psutil_module
        except ImportError:
            psutil_module = False
        psutil = psutil_module
    return psutil if psutil is not False else None


@dataclass
class MetricSnapshot:
    """A snapshot of performance metrics at a point in time."""

    timestamp: datetime
    operation_name: str
    duration_ms: float
    memory_mb: float
    cpu_percent: float
    thread_count: int
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and tracks performance metrics for optimization analysis.
    """

    def __init__(self, max_snapshots: int = 1000):
        """
        Initialize the metrics collector.

        Args:
            max_snapshots: Maximum number of snapshots to keep in memory
        """
        self.max_snapshots = max_snapshots
        self.snapshots: deque = deque(maxlen=max_snapshots)
        self._lock = threading.Lock()
        psutil_module = _get_psutil()
        self._process = psutil_module.Process() if psutil_module is not None else None

        # Baseline metrics for comparison
        self._baseline: Optional[MetricSnapshot] = None
        self._operation_timers: Dict[str, float] = {}

        logger.info("Metrics collector initialized")

    def start_operation(self, operation_name: str) -> None:
        """
        Start timing an operation.

        Args:
            operation_name: Name of the operation to time
        """
        self._operation_timers[operation_name] = time.time()

    def end_operation(
        self, operation_name: str, custom_metrics: Dict[str, Any] = None
    ) -> Optional[MetricSnapshot]:
        """
        End timing an operation and record metrics.

        Args:
            operation_name: Name of the operation
            custom_metrics: Additional custom metrics to record

        Returns:
            MetricSnapshot if operation was tracked, None otherwise
        """
        if operation_name not in self._operation_timers:
            logger.warning(f"Operation '{operation_name}' was not started")
            return None

        start_time = self._operation_timers.pop(operation_name)
        duration_ms = (time.time() - start_time) * 1000

        snapshot = self._capture_snapshot(
            operation_name=operation_name,
            duration_ms=duration_ms,
            custom_metrics=custom_metrics or {},
        )

        with self._lock:
            self.snapshots.append(snapshot)

        logger.debug(f"Recorded metrics for '{operation_name}': {duration_ms:.2f}ms")
        return snapshot

    def _capture_snapshot(
        self, operation_name: str, duration_ms: float, custom_metrics: Dict[str, Any]
    ) -> MetricSnapshot:
        """
        Capture a snapshot of current system metrics.

        Args:
            operation_name: Name of the operation
            duration_ms: Duration of the operation in milliseconds
            custom_metrics: Additional custom metrics

        Returns:
            MetricSnapshot
        """
        try:
            if self._process is None:
                raise ImportError("psutil is not available")
            memory_info = self._process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            cpu_percent = self._process.cpu_percent()
            thread_count = self._process.num_threads()
        except Exception as e:
            if not isinstance(e, ImportError):
                logger.warning(f"Failed to capture system metrics: {e}")
            memory_mb = 0.0
            cpu_percent = 0.0
            thread_count = 0

        return MetricSnapshot(
            timestamp=datetime.now(),
            operation_name=operation_name,
            duration_ms=duration_ms,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            thread_count=thread_count,
            custom_metrics=custom_metrics,
        )

    def set_baseline(self, operation_name: str) -> None:
        """
        Set baseline metrics for an operation.

        Args:
            operation_name: Name of the operation to baseline
        """
        snapshot = self._capture_snapshot(
            operation_name=operation_name, duration_ms=0.0, custom_metrics={}
        )
        self._baseline = snapshot
        logger.info(f"Baseline set for '{operation_name}'")

    def get_baseline(self) -> Optional[MetricSnapshot]:
        """Get the baseline metrics."""
        return self._baseline

    def get_snapshots(
        self, operation_name: str = None, since: datetime = None, limit: int = 100
    ) -> List[MetricSnapshot]:
        """
        Get snapshots matching criteria.

        Args:
            operation_name: Filter by operation name (optional)
            since: Filter by timestamp (optional)
            limit: Maximum number of snapshots to return

        Returns:
            List of MetricSnapshot
        """
        with self._lock:
            snapshots = list(self.snapshots)

        # Filter by operation name
        if operation_name:
            snapshots = [s for s in snapshots if s.operation_name == operation_name]

        # Filter by timestamp
        if since:
            snapshots = [s for s in snapshots if s.timestamp >= since]

        # Limit results
        snapshots = snapshots[-limit:]

        return snapshots

    def get_statistics(self, operation_name: str = None) -> Dict[str, Any]:
        """
        Get statistics for operations.

        Args:
            operation_name: Filter by operation name (optional)

        Returns:
            Dictionary with statistics
        """
        snapshots = self.get_snapshots(operation_name=operation_name)

        if not snapshots:
            return {
                "count": 0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "avg_memory_mb": 0.0,
                "avg_cpu_percent": 0.0,
            }

        durations = [s.duration_ms for s in snapshots]
        memories = [s.memory_mb for s in snapshots]
        cpus = [s.cpu_percent for s in snapshots]

        return {
            "count": len(snapshots),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "avg_memory_mb": sum(memories) / len(memories),
            "avg_cpu_percent": sum(cpus) / len(cpus),
            "total_duration_ms": sum(durations),
        }

    def compare_with_baseline(self, operation_name: str) -> Dict[str, Any]:
        """
        Compare current metrics with baseline.

        Args:
            operation_name: Name of the operation to compare

        Returns:
            Dictionary with comparison results
        """
        if self._baseline is None:
            return {"error": "No baseline set"}

        current_stats = self.get_statistics(operation_name=operation_name)

        if current_stats["count"] == 0:
            return {"error": "No snapshots for comparison"}

        baseline_memory = self._baseline.memory_mb
        baseline_cpu = self._baseline.cpu_percent

        return {
            "operation": operation_name,
            "baseline": {"memory_mb": baseline_memory, "cpu_percent": baseline_cpu},
            "current": {
                "avg_memory_mb": current_stats["avg_memory_mb"],
                "avg_cpu_percent": current_stats["avg_cpu_percent"],
                "avg_duration_ms": current_stats["avg_duration_ms"],
            },
            "improvement": {
                "memory_reduction_percent": (
                    (baseline_memory - current_stats["avg_memory_mb"]) / baseline_memory * 100
                    if baseline_memory > 0
                    else 0
                ),
                "cpu_reduction_percent": (
                    (baseline_cpu - current_stats["avg_cpu_percent"]) / baseline_cpu * 100
                    if baseline_cpu > 0
                    else 0
                ),
            },
        }

    def clear_snapshots(self, operation_name: str = None) -> None:
        """
        Clear snapshots.

        Args:
            operation_name: Clear only snapshots for this operation (optional)
        """
        with self._lock:
            if operation_name:
                self.snapshots = deque(
                    [s for s in self.snapshots if s.operation_name != operation_name],
                    maxlen=self.max_snapshots,
                )
            else:
                self.snapshots.clear()

        logger.info(f"Cleared snapshots for '{operation_name if operation_name else 'all'}'")

    def export_metrics(self, filepath: Path = None) -> Dict[str, Any]:
        """
        Export metrics to a file or return as dict.

        Args:
            filepath: Path to export to (optional)

        Returns:
            Dictionary with all metrics
        """
        with self._lock:
            snapshots_data = []
            for snapshot in self.snapshots:
                snapshots_data.append(
                    {
                        "timestamp": snapshot.timestamp.isoformat(),
                        "operation_name": snapshot.operation_name,
                        "duration_ms": snapshot.duration_ms,
                        "memory_mb": snapshot.memory_mb,
                        "cpu_percent": snapshot.cpu_percent,
                        "thread_count": snapshot.thread_count,
                        "custom_metrics": snapshot.custom_metrics,
                    }
                )

        export_data = {
            "baseline": (
                {
                    "timestamp": self._baseline.timestamp.isoformat() if self._baseline else None,
                    "operation_name": self._baseline.operation_name if self._baseline else None,
                    "memory_mb": self._baseline.memory_mb if self._baseline else 0,
                    "cpu_percent": self._baseline.cpu_percent if self._baseline else 0,
                }
                if self._baseline
                else None
            ),
            "snapshots": snapshots_data,
            "exported_at": datetime.now().isoformat(),
        }

        if filepath:
            import json

            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            logger.info(f"Exported metrics to {filepath}")

        return export_data


# Global instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.

    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
