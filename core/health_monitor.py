"""
Health monitoring system for JARVIS AI Assistant.

This module provides:
- System health checks
- Service status monitoring
- Dependency verification
- Health report generation
"""

import asyncio
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.cache_manager import get_cache_manager
from core.logger import get_logger
from core.paths import project_path
from core.performance_monitor import get_performance_monitor
from memory.memory_backup import get_backup_manager

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: str  # "healthy", "warning", "critical"
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = ""


class HealthMonitor:
    """
    Monitors system health and provides health reports.
    """

    def __init__(self):
        """Initialize health monitor."""
        self.checks: List[HealthCheckResult] = []
        logger.info("Health monitor initialized")

    def check_python_version(self) -> HealthCheckResult:
        """Check Python version compatibility."""
        import sys

        version = sys.version_info
        is_compatible = version >= (3, 11)

        status = "healthy" if is_compatible else "critical"
        message = f"Python {version.major}.{version.minor}.{version.micro}"

        return HealthCheckResult(
            name="python_version",
            status=status,
            message=message,
            details={
                "version": f"{version.major}.{version.minor}.{version.micro}",
                "compatible": is_compatible,
            },
            timestamp=datetime.now().isoformat(),
        )

    def check_dependencies(self) -> HealthCheckResult:
        """Check if required dependencies are installed."""
        required_packages = [
            "google.genai",
            "sounddevice",
            "chromadb",
            "pillow",
            "requests",
            "pyyaml",
        ]

        missing = []
        for package in required_packages:
            try:
                __import__(package.replace(".", "_"))
            except ImportError:
                missing.append(package)

        status = "healthy" if not missing else "critical"
        message = f"All dependencies installed" if not missing else f"Missing: {', '.join(missing)}"

        return HealthCheckResult(
            name="dependencies",
            status=status,
            message=message,
            details={"missing_packages": missing, "total_required": len(required_packages)},
            timestamp=datetime.now().isoformat(),
        )

    def check_disk_space(self) -> HealthCheckResult:
        """Check available disk space."""
        import shutil

        try:
            total, used, free = shutil.disk_usage("/")
            free_gb = free / (1024**3)

            if free_gb < 1:
                status = "critical"
                message = f"Low disk space: {free_gb:.2f} GB free"
            elif free_gb < 5:
                status = "warning"
                message = f"Disk space getting low: {free_gb:.2f} GB free"
            else:
                status = "healthy"
                message = f"Sufficient disk space: {free_gb:.2f} GB free"

            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "free_gb": free_gb,
                    "used_gb": used / (1024**3),
                    "total_gb": total / (1024**3),
                },
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status="warning",
                message=f"Could not check disk space: {e}",
                timestamp=datetime.now().isoformat(),
            )

    def check_memory_integrity(self) -> HealthCheckResult:
        """Check memory file integrity."""
        try:
            backup_manager = get_backup_manager()
            is_valid, message = backup_manager.verify_memory_integrity()

            status = "healthy" if is_valid else "critical"

            return HealthCheckResult(
                name="memory_integrity",
                status=status,
                message=message,
                details={"valid": is_valid},
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory_integrity",
                status="warning",
                message=f"Could not check memory integrity: {e}",
                timestamp=datetime.now().isoformat(),
            )

    def check_cache_health(self) -> HealthCheckResult:
        """Check cache system health."""
        try:
            cache_manager = get_cache_manager()
            stats = cache_manager.get_stats()

            # Check if cache is too large
            db_size_mb = stats.get("database_size_mb", 0)
            if db_size_mb > 500:
                status = "warning"
                message = f"Cache size large: {db_size_mb:.2f} MB"
            else:
                status = "healthy"
                message = f"Cache healthy: {db_size_mb:.2f} MB"

            return HealthCheckResult(
                name="cache_health",
                status=status,
                message=message,
                details=stats,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="cache_health",
                status="warning",
                message=f"Could not check cache: {e}",
                timestamp=datetime.now().isoformat(),
            )

    def check_audio_backend(self) -> HealthCheckResult:
        """Check audio backend availability."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            status = "healthy"
            message = f"Audio backend available: {len(devices)} devices"

            return HealthCheckResult(
                name="audio_backend",
                status=status,
                message=message,
                details={"device_count": len(devices)},
                timestamp=datetime.now().isoformat(),
            )
        except ImportError:
            return HealthCheckResult(
                name="audio_backend",
                status="critical",
                message="Sounddevice not installed",
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="audio_backend",
                status="warning",
                message=f"Audio backend issue: {e}",
                timestamp=datetime.now().isoformat(),
            )

    def check_api_key(self) -> HealthCheckResult:
        """Check if API key is configured."""
        try:
            from config.config_loader import get_config

            config = get_config()
            api_key = str(config.get_api_key("gemini") or "").strip()

            if api_key and len(api_key) > 10:
                status = "healthy"
                message = "API key configured"
            else:
                status = "critical"
                message = "API key not configured or invalid"

            return HealthCheckResult(
                name="api_key",
                status=status,
                message=message,
                details={"configured": bool(api_key)},
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="api_key",
                status="warning",
                message=f"Could not check API key: {e}",
                timestamp=datetime.now().isoformat(),
            )

    def check_configuration(self) -> HealthCheckResult:
        """Check configuration file."""
        try:
            from config.config_loader import get_config

            config = get_config()

            # Check required config keys
            required_keys = ["models.live", "audio.channels"]
            missing = [key for key in required_keys if not config.get(key)]

            if missing:
                status = "warning"
                message = f"Missing config keys: {', '.join(missing)}"
            else:
                status = "healthy"
                message = "Configuration valid"

            return HealthCheckResult(
                name="configuration",
                status=status,
                message=message,
                details={"missing_keys": missing},
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="configuration",
                status="critical",
                message=f"Configuration error: {e}",
                timestamp=datetime.now().isoformat(),
            )

    def run_all_checks(self) -> List[HealthCheckResult]:
        """
        Run all health checks.

        Returns:
            List of health check results
        """
        self.checks = [
            self.check_python_version(),
            self.check_dependencies(),
            self.check_disk_space(),
            self.check_memory_integrity(),
            self.check_cache_health(),
            self.check_audio_backend(),
            self.check_api_key(),
            self.check_configuration(),
        ]

        return self.checks

    def get_overall_status(self) -> str:
        """
        Get overall system health status.

        Returns:
            Overall status: "healthy", "warning", or "critical"
        """
        if not self.checks:
            self.run_all_checks()

        statuses = [check.status for check in self.checks]

        if "critical" in statuses:
            return "critical"
        elif "warning" in statuses:
            return "warning"
        else:
            return "healthy"

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive health report.

        Returns:
            Dictionary containing health report
        """
        if not self.checks:
            self.run_all_checks()

        # Get performance stats
        try:
            perf_monitor = get_performance_monitor()
            perf_stats = perf_monitor.get_resource_stats(minutes=5)
        except Exception:
            perf_stats = {}

        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": self.get_overall_status(),
            "checks": [asdict(check) for check in self.checks],
            "performance": perf_stats,
            "summary": {
                "total_checks": len(self.checks),
                "healthy": sum(1 for c in self.checks if c.status == "healthy"),
                "warning": sum(1 for c in self.checks if c.status == "warning"),
                "critical": sum(1 for c in self.checks if c.status == "critical"),
            },
        }

        return report

    def save_report(self, path: Optional[Path] = None):
        """
        Save health report to file.

        Args:
            path: Path to save report (defaults to ./logs/health_report.json)
        """
        if path is None:
            path = project_path("logs", "health_report.json")

        path.parent.mkdir(parents=True, exist_ok=True)

        report = self.generate_report()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Health report saved to {path}")


# Global instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor


def run_health_checks() -> Dict[str, Any]:
    """
    Run all health checks and return report.

    Returns:
        Health report dictionary
    """
    monitor = get_health_monitor()
    return monitor.generate_report()
