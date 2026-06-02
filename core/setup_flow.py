"""
Setup Flow System for Mark-XXXIX
=================================
Provides first-time setup wizard and configuration validation.
Checks API keys, dependencies, and optional integrations.
"""

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


class SetupStatus(Enum):
    """Status of a setup check."""

    PENDING = "pending"
    CHECKING = "checking"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class SetupCheck:
    """Represents a single setup check."""

    name: str
    description: str
    status: SetupStatus = SetupStatus.PENDING
    message: str = ""
    is_required: bool = True
    fix_instructions: str = ""
    category: str = "general"


@dataclass
class SetupReport:
    """Complete setup report."""

    checks: List[SetupCheck] = field(default_factory=list)
    overall_status: SetupStatus = SetupStatus.PENDING
    timestamp: str = ""

    def add_check(self, check: SetupCheck):
        """Add a check to the report."""
        self.checks.append(check)
        self._update_overall_status()

    def _update_overall_status(self):
        """Update overall status based on checks."""
        required_failed = any(c.status == SetupStatus.FAILED and c.is_required for c in self.checks)
        optional_failed = any(
            c.status == SetupStatus.FAILED and not c.is_required for c in self.checks
        )

        if required_failed:
            self.overall_status = SetupStatus.FAILED
        elif optional_failed:
            self.overall_status = SetupStatus.WARNING
        elif all(c.status in [SetupStatus.PASSED, SetupStatus.SKIPPED] for c in self.checks):
            self.overall_status = SetupStatus.PASSED
        else:
            self.overall_status = SetupStatus.PENDING

    def get_required_checks(self) -> List[SetupCheck]:
        """Get all required checks."""
        return [c for c in self.checks if c.is_required]

    def get_optional_checks(self) -> List[SetupCheck]:
        """Get all optional checks."""
        return [c for c in self.checks if not c.is_required]

    def get_failed_checks(self) -> List[SetupCheck]:
        """Get all failed checks."""
        return [c for c in self.checks if c.status == SetupStatus.FAILED]

    def get_passed_checks(self) -> List[SetupCheck]:
        """Get all passed checks."""
        return [c for c in self.checks if c.status == SetupStatus.PASSED]


class SetupFlow:
    """
    Manages the setup flow for first-time configuration.
    Checks API keys, dependencies, and optional integrations.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize setup flow.

        Args:
            base_dir: Base directory of the project
        """
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent

        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "config"
        self.report = SetupReport()
        logger.info("Setup flow initialized")

    def run_all_checks(self) -> SetupReport:
        """
        Run all setup checks.

        Returns:
            Complete setup report
        """
        from datetime import datetime

        self.report.timestamp = datetime.now().isoformat()

        # Required checks
        self._check_api_key()
        self._check_python_version()
        self._check_required_modules()
        self._check_config_files()

        # Optional checks
        self._check_audio_dependencies()
        self._check_browser_automation()
        self._check_optional_integrations()
        self._check_memory_system()

        logger.info(f"Setup check complete: {self.report.overall_status.value}")
        return self.report

    def _check_api_key(self):
        """Check if Gemini API key is configured."""
        check = SetupCheck(
            name="API Key",
            description="Gemini API key is configured",
            is_required=True,
            category="required",
        )

        try:
            # Check .env file
            env_file = self.base_dir / ".env"
            if env_file.exists():
                content = env_file.read_text(encoding="utf-8")
                if "GEMINI_API_KEY" in content and "your_gemini_api_key_here" not in content:
                    check.status = SetupStatus.PASSED
                    check.message = "API key found in .env file"
                else:
                    check.status = SetupStatus.FAILED
                    check.message = "API key not configured in .env file"
                    check.fix_instructions = (
                        "1. Open .env file in the project root\n"
                        "2. Replace 'your_gemini_api_key_here' with your actual Gemini API key\n"
                        "3. Get your API key from: https://aistudio.google.com/app/apikey"
                    )
            else:
                # Check legacy api_keys.json
                api_file = self.config_dir / "api_keys.json"
                if api_file.exists():
                    data = json.loads(api_file.read_text(encoding="utf-8"))
                    if data.get("gemini_api_key"):
                        check.status = SetupStatus.PASSED
                        check.message = "API key found in api_keys.json"
                    else:
                        check.status = SetupStatus.FAILED
                        check.message = "API key not configured"
                        check.fix_instructions = "Add gemini_api_key to config/api_keys.json"
                else:
                    check.status = SetupStatus.FAILED
                    check.message = "No API key configuration found"
                    check.fix_instructions = (
                        "Create .env file from .env.example and add your Gemini API key"
                    )
        except Exception as e:
            check.status = SetupStatus.FAILED
            check.message = f"Error checking API key: {e}"
            check.fix_instructions = "Check file permissions and format"

        self.report.add_check(check)

    def _check_python_version(self):
        """Check Python version compatibility."""
        check = SetupCheck(
            name="Python Version",
            description="Python 3.10+ is installed",
            is_required=True,
            category="required",
        )

        version = sys.version_info
        if version.major == 3 and version.minor >= 10:
            check.status = SetupStatus.PASSED
            check.message = f"Python {version.major}.{version.minor}.{version.micro}"
        else:
            check.status = SetupStatus.FAILED
            check.message = f"Python {version.major}.{version.minor} is not supported"
            check.fix_instructions = "Install Python 3.10 or higher from python.org"

        self.report.add_check(check)

    def _check_required_modules(self):
        """Check if required Python modules are installed."""
        check = SetupCheck(
            name="Required Modules",
            description="Core dependencies are installed",
            is_required=True,
            category="required",
        )

        required = ["google.genai", "PyQt6", "sounddevice"]
        missing = []

        for module in required:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)

        if not missing:
            check.status = SetupStatus.PASSED
            check.message = "All required modules installed"
        else:
            check.status = SetupStatus.FAILED
            check.message = f"Missing modules: {', '.join(missing)}"
            check.fix_instructions = (
                f"Run: pip install {' '.join(missing)}\n" "Or run: pip install -r requirements.txt"
            )

        self.report.add_check(check)

    def _check_config_files(self):
        """Check if required config files exist."""
        check = SetupCheck(
            name="Config Files",
            description="Required configuration files exist",
            is_required=True,
            category="required",
        )

        required_files = [
            self.base_dir / "config.yaml",
            self.base_dir / "core" / "prompt.txt",
        ]

        missing = [f for f in required_files if not f.exists()]

        if not missing:
            check.status = SetupStatus.PASSED
            check.message = "All config files present"
        else:
            check.status = SetupStatus.FAILED
            check.message = f"Missing files: {', '.join(str(f) for f in missing)}"
            check.fix_instructions = "Ensure all required config files exist in the project"

        self.report.add_check(check)

    def _check_audio_dependencies(self):
        """Check audio/microphone dependencies."""
        check = SetupCheck(
            name="Audio Dependencies",
            description="Audio input/output is available",
            is_required=False,
            category="optional",
        )

        try:
            import sounddevice as sd

            devices = sd.query_devices()
            input_devices = sum(1 for d in devices if d["max_input_channels"] > 0)
            output_devices = sum(1 for d in devices if d["max_output_channels"] > 0)

            if input_devices > 0 and output_devices > 0:
                check.status = SetupStatus.PASSED
                check.message = f"Audio available ({input_devices} input, {output_devices} output)"
            else:
                check.status = SetupStatus.WARNING
                check.message = (
                    f"Limited audio devices (input: {input_devices}, output: {output_devices})"
                )
                check.fix_instructions = "Check audio device connections and drivers"
        except ImportError:
            check.status = SetupStatus.WARNING
            check.message = "sounddevice not installed"
            check.fix_instructions = "Install with: pip install sounddevice"
        except Exception as e:
            check.status = SetupStatus.WARNING
            check.message = f"Audio check failed: {e}"
            check.fix_instructions = "Check audio drivers and permissions"

        self.report.add_check(check)

    def _check_browser_automation(self):
        """Check browser automation dependencies."""
        check = SetupCheck(
            name="Browser Automation",
            description="Playwright for browser control",
            is_required=False,
            category="optional",
        )

        try:
            import playwright

            check.status = SetupStatus.PASSED
            check.message = "Playwright installed"
        except ImportError:
            check.status = SetupStatus.WARNING
            check.message = "Playwright not installed"
            check.fix_instructions = (
                "Install with: pip install playwright\n" "Then run: playwright install"
            )

        self.report.add_check(check)

    def _check_optional_integrations(self):
        """Check optional integration dependencies."""
        integrations = {
            "Gmail": ["googleapiclient"],
            "Calendar": ["googleapiclient"],
            "Obsidian": [],  # No special deps
            "Spotify": [],  # No special deps
            "VS Code": ["websockets"],
        }

        for name, deps in integrations.items():
            check = SetupCheck(
                name=f"{name} Integration",
                description=f"{name} integration dependencies",
                is_required=False,
                category="integration",
            )

            missing = []
            for dep in deps:
                try:
                    __import__(dep)
                except ImportError:
                    missing.append(dep)

            if not missing:
                check.status = SetupStatus.PASSED
                check.message = f"{name} integration ready"
            else:
                check.status = SetupStatus.SKIPPED
                check.message = f"{name} integration not available (missing: {', '.join(missing)})"
                check.fix_instructions = f"Install with: pip install {' '.join(missing)}"

            self.report.add_check(check)

    def _check_memory_system(self):
        """Check memory system setup."""
        check = SetupCheck(
            name="Memory System",
            description="Long-term memory is configured",
            is_required=False,
            category="optional",
        )

        memory_file = self.base_dir / "memory" / "long_term.json"

        if memory_file.exists():
            check.status = SetupStatus.PASSED
            check.message = "Memory file exists"
        else:
            check.status = SetupStatus.WARNING
            check.message = "Memory file not found (will be created on first use)"
            check.fix_instructions = "Memory will be created automatically"

        self.report.add_check(check)

    def format_report(self, verbose: bool = False) -> str:
        """
        Format the setup report as a readable string.

        Args:
            verbose: Include detailed information

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("MARK-XXXIX SETUP REPORT")
        lines.append("=" * 60)
        lines.append(f"Overall Status: {self.report.overall_status.value.upper()}")
        lines.append(f"Timestamp: {self.report.timestamp}")
        lines.append("")

        # Required checks
        lines.append("REQUIRED CHECKS:")
        lines.append("-" * 40)
        for check in self.report.get_required_checks():
            status_symbol = {
                SetupStatus.PASSED: "✓",
                SetupStatus.FAILED: "✗",
                SetupStatus.WARNING: "⚠",
                SetupStatus.SKIPPED: "○",
            }.get(check.status, "?")

            lines.append(f"{status_symbol} {check.name}: {check.message}")

            if verbose and check.status == SetupStatus.FAILED:
                lines.append(f"  Fix: {check.fix_instructions}")

        lines.append("")

        # Optional checks
        lines.append("OPTIONAL CHECKS:")
        lines.append("-" * 40)
        for check in self.report.get_optional_checks():
            status_symbol = {
                SetupStatus.PASSED: "✓",
                SetupStatus.FAILED: "✗",
                SetupStatus.WARNING: "⚠",
                SetupStatus.SKIPPED: "○",
            }.get(check.status, "?")

            lines.append(f"{status_symbol} {check.name}: {check.message}")

            if verbose and check.status in [SetupStatus.FAILED, SetupStatus.WARNING]:
                lines.append(f"  Fix: {check.fix_instructions}")

        lines.append("")

        # Summary
        passed = len(self.report.get_passed_checks())
        failed = len(self.report.get_failed_checks())
        total = len(self.report.checks)

        lines.append("SUMMARY:")
        lines.append("-" * 40)
        lines.append(f"Total checks: {total}")
        lines.append(f"Passed: {passed}")
        lines.append(f"Failed: {failed}")

        if self.report.overall_status == SetupStatus.PASSED:
            lines.append("")
            lines.append("✓ Setup complete! You can start using JARVIS.")
        elif self.report.overall_status == SetupStatus.WARNING:
            lines.append("")
            lines.append("⚠ Setup complete with warnings. Some features may be limited.")
        else:
            lines.append("")
            lines.append("✗ Setup incomplete. Please fix the required checks above.")

        lines.append("=" * 60)

        return "\n".join(lines)


# Global instance
_setup_flow: Optional[SetupFlow] = None


def get_setup_flow(base_dir: Optional[Path] = None) -> SetupFlow:
    """Get the global setup flow instance."""
    global _setup_flow
    if _setup_flow is None:
        _setup_flow = SetupFlow(base_dir)
    return _setup_flow


def run_setup_check(base_dir: Optional[Path] = None, verbose: bool = False) -> str:
    """
    Run setup check and return formatted report.

    Args:
        base_dir: Base directory of the project
        verbose: Include detailed information

    Returns:
        Formatted setup report
    """
    setup = get_setup_flow(base_dir)
    report = setup.run_all_checks()
    return setup.format_report(verbose=verbose)


if __name__ == "__main__":
    # Run setup check when executed directly
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print(run_setup_check(verbose=True))
