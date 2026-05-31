"""
Performance monitoring system for JARVIS AI Assistant.

This module provides:
- API call tracking with metrics
- Response time monitoring
- Resource usage monitoring (CPU, RAM, Memory)
- Performance statistics and reporting
"""

import time
import threading
import psutil
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from collections import defaultdict
import json
from pathlib import Path

from core.logger import get_logger

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
        max_resource_snapshots: int = 1440,  # 24 hours at 1-minute intervals
        resource_interval_seconds: float = 60.0
    ):
        """
        Initialize the performance monitor.
        
        Args:
            max_api_calls: Maximum number of API call records to keep
            max_resource_snapshots: Maximum number of resource snapshots to keep
            resource_interval_seconds: Interval between resource snapshots
        """
        self.max_api_calls = max_api_calls
        self.max_resource_snapshots = max_resource_snapshots
        self.resource_interval_seconds = resource_interval_seconds
        
        self.api_calls: List[APICallMetrics] = []
        self.resource_snapshots: List[ResourceSnapshot] = []
        self.api_call_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_calls": 0,
            "successful": 0,
            "failed": 0,
            "total_duration_ms": 0.0,
            "avg_duration_ms": 0.0,
            "min_duration_ms": float('inf'),
            "max_duration_ms": 0.0,
            "total_tokens": 0
        })
        
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        logger.info("Performance monitor initialized")
    
    def track_api_call(
        self,
        endpoint: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None,
        tokens_used: Optional[int] = None
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
                tokens_used=tokens_used
            )
            
            self.api_calls.append(metrics)
            
            # Trim old records
            if len(self.api_calls) > self.max_api_calls:
                self.api_calls = self.api_calls[-self.max_api_calls:]
            
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
            
            logger.debug(f"API call tracked: {endpoint} - {duration_ms:.2f}ms - {'SUCCESS' if success else 'FAILED'}")
    
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
                "endpoints": {}
            }
            
            for ep, stats in self.api_call_stats.items():
                total_stats["total_calls"] += stats["total_calls"]
                total_stats["successful"] += stats["successful"]
                total_stats["failed"] += stats["failed"]
                total_stats["total_duration_ms"] += stats["total_duration_ms"]
                total_stats["total_tokens"] += stats["total_tokens"]
                total_stats["endpoints"][ep] = dict(stats)
            
            if total_stats["total_calls"] > 0:
                total_stats["avg_duration_ms"] = total_stats["total_duration_ms"] / total_stats["total_calls"]
            
            return total_stats
    
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
                disk_usage_percent=psutil.disk_usage('/').percent if Path('/').exists() else psutil.disk_usage('C:\\').percent,
                active_threads=process.num_threads()
            )
            
            with self._lock:
                self.resource_snapshots.append(snapshot)
                
                # Trim old snapshots
                if len(self.resource_snapshots) > self.max_resource_snapshots:
                    self.resource_snapshots = self.resource_snapshots[-self.max_resource_snapshots:]
            
            logger.debug(f"Resource snapshot captured: CPU={snapshot.cpu_percent:.1f}%, RAM={snapshot.memory_percent:.1f}%")
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
                s for s in self.resource_snapshots
                if s.timestamp.timestamp() >= cutoff
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
                    "current": cpu_values[-1]
                },
                "memory": {
                    "avg_percent": sum(memory_values) / len(memory_values),
                    "min_percent": min(memory_values),
                    "max_percent": max(memory_values),
                    "current_percent": memory_values[-1],
                    "avg_mb": sum(memory_mb_values) / len(memory_mb_values),
                    "current_mb": memory_mb_values[-1]
                },
                "threads": {
                    "avg": sum(thread_values) / len(thread_values),
                    "min": min(thread_values),
                    "max": max(thread_values),
                    "current": thread_values[-1]
                }
            }
    
    def start_monitoring(self):
        """Start background resource monitoring."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Resource monitoring thread already running")
            return
        
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="PerformanceMonitorThread"
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
                "resources": self.get_resource_stats(minutes=60),
                "recent_api_calls": [
                    {
                        "endpoint": m.endpoint,
                        "timestamp": m.timestamp.isoformat(),
                        "duration_ms": m.duration_ms,
                        "success": m.success,
                        "error": m.error
                    }
                    for m in self.api_calls[-10:]
                ]
            }
            return report
    
    def save_report(self, path: Optional[Path] = None):
        """
        Save performance report to a JSON file.
        
        Args:
            path: Path to save the report (defaults to ./logs/performance_report.json)
        """
        if path is None:
            path = Path("./logs/performance_report.json")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        report = self.get_performance_report()
        with open(path, 'w', encoding='utf-8') as f:
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
            start_time = time.time()
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
                duration_ms = (time.time() - start_time) * 1000
                monitor.track_api_call(
                    endpoint=endpoint,
                    duration_ms=duration_ms,
                    success=success,
                    error=error
                )
        return wrapper
    return decorator
