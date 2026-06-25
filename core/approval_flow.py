"""
Approval Flow System for Mark-XXXIX
====================================
Integrates permission checking with UI confirmation for risky actions.
Extended with risk classification (low/medium/high) and detailed summaries.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

from core.logger import get_logger
from core.permission_profiles import PermissionLevel, check_action, get_tool_metadata

logger = get_logger(__name__)


class RiskLevel(Enum):
    """Risk classification for actions."""

    LOW = "low"  # Read-only, queries, searches
    MEDIUM = "medium"  # App launch, browser open, local file ops without delete
    HIGH = "high"  # Delete, move, send messages, calendar changes, system changes, forms, payments


class ApprovalStatus(Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


@dataclass
class ApprovalContext:
    """Structured context shown with an approval request."""

    risk_level: str
    affected_resources: list[str] = field(default_factory=list)
    expected_effect: str = ""
    undo_available: bool = False
    undo_description: str = "No automatic undo is available."
    rationale: str = ""
    safeguards: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "affected_resources": list(self.affected_resources),
            "expected_effect": self.expected_effect,
            "undo_available": self.undo_available,
            "undo_description": self.undo_description,
            "rationale": self.rationale,
            "safeguards": list(self.safeguards),
        }


@dataclass
class ApprovalDecision:
    """Structured decision data for API/UI approval handling."""

    approved: bool
    decided_by: str = "user"
    reason: str = ""
    decided_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "decided_by": self.decided_by,
            "reason": self.reason,
            "decided_at": self.decided_at.isoformat(),
        }


class ApprovalRequest:
    """Represents a pending approval request with risk classification."""

    def __init__(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        permission_level: str,
        reason: str = "",
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        context: ApprovalContext | Dict[str, Any] | None = None,
    ):
        self.tool_name = tool_name
        self.action = action
        self.parameters = parameters
        self.permission_level = permission_level
        self.reason = reason
        self.risk_level = risk_level
        self.timestamp = datetime.now()
        self.status = ApprovalStatus.PENDING
        self._event = threading.Event()
        self._result: Optional[bool] = None
        self.decision: Optional[ApprovalDecision] = None
        if isinstance(context, ApprovalContext):
            self.context = context
        elif isinstance(context, dict):
            self.context = ApprovalContext(risk_level=risk_level.value, **context)
        else:
            self.context = build_approval_context(tool_name, action, parameters, risk_level, reason)
        self.can_undo = self.context.undo_available
        self.summary = self._generate_summary()

    def _generate_summary(self) -> str:
        """Generate a human-readable summary of the action."""
        parts = [f"Tool: {self.tool_name}", f"Action: {self.action}"]

        # Add key parameters to summary
        if self.parameters:
            safe_params = {}
            for key, value in self.parameters.items():
                # Skip sensitive parameters
                if key.lower() in ["password", "token", "api_key", "secret"]:
                    safe_params[key] = "***"
                elif isinstance(value, str) and len(value) > 50:
                    safe_params[key] = value[:50] + "..."
                else:
                    safe_params[key] = value
            if safe_params:
                parts.append(f"Parameters: {safe_params}")

        parts.append(f"Risk Level: {self.risk_level.value.upper()}")
        if self.context.affected_resources:
            parts.append(f"Affected: {', '.join(self.context.affected_resources)}")
        if self.context.expected_effect:
            parts.append(f"Effect: {self.context.expected_effect}")
        parts.append(f"Undo: {self.context.undo_description}")
        parts.append(f"Why: {self.context.rationale or self.reason}")

        return " | ".join(parts)

    def approve(self, reason: str = "", decided_by: str = "user"):
        """Approve the request."""
        self._result = True
        self.status = ApprovalStatus.APPROVED
        self.decision = ApprovalDecision(True, decided_by=decided_by, reason=reason)
        self._event.set()
        logger.info(f"Approval approved: {self.tool_name}/{self.action}")

    def deny(self, reason: str = "", decided_by: str = "user"):
        """Deny the request."""
        self._result = False
        self.status = ApprovalStatus.DENIED
        self.decision = ApprovalDecision(False, decided_by=decided_by, reason=reason)
        self._event.set()
        logger.info(f"Approval denied: {self.tool_name}/{self.action}")

    def wait_for_decision(self, timeout: float = 30.0) -> Optional[bool]:
        """Wait for user decision with timeout."""
        if self._event.wait(timeout=timeout):
            return self._result
        self.status = ApprovalStatus.TIMEOUT
        logger.warning(f"Approval timeout: {self.tool_name}/{self.action}")
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable API shape without exposing secrets."""
        return {
            "tool_name": self.tool_name,
            "action": self.action,
            "permission_level": self.permission_level,
            "reason": self.reason,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "context": self.context.to_dict(),
            "decision": self.decision.to_dict() if self.decision else None,
        }


def _safe_resource(value: Any) -> str:
    text = str(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text


def _affected_resources(parameters: Dict[str, Any]) -> list[str]:
    resource_keys = (
        "path",
        "source",
        "destination",
        "target",
        "file",
        "folder",
        "recipient",
        "to",
        "channel",
        "workflow",
        "workflow_name",
        "event_id",
        "url",
    )
    resources: list[str] = []
    for key in resource_keys:
        value = parameters.get(key)
        if value:
            resources.append(f"{key}={_safe_resource(value)}")
    return resources


def _expected_effect(tool_name: str, action: str, parameters: Dict[str, Any]) -> str:
    action_lower = action.lower()
    tool_lower = tool_name.lower()
    if "file" in tool_lower:
        if action_lower in {"move", "rename"}:
            return "Move or rename a filesystem resource."
        if action_lower in {"copy"}:
            return "Create another copy of a filesystem resource."
        if action_lower in {"delete", "delete_file"}:
            return "Remove a filesystem resource."
        if action_lower in {"write", "create_file", "create_folder"}:
            return "Create or modify local filesystem content."
    if "send_message" in tool_lower or action_lower in {"send", "reply"}:
        return "Prepare or send communication to an external recipient."
    if "workflow" in tool_lower or "workflow" in parameters:
        return "Start or modify an automated workflow."
    if "calendar" in tool_lower:
        return "Create or change calendar data."
    if "settings" in tool_lower or "computer" in tool_lower:
        return "Change local system or device state."
    return "Perform the requested action with the provided parameters."


def _undo_description(tool_name: str, action: str, parameters: Dict[str, Any]) -> tuple[bool, str]:
    action_lower = action.lower()
    tool_lower = tool_name.lower()
    metadata = get_tool_metadata(tool_name)
    if action_lower in {"move", "rename"}:
        return True, "Can usually be undone by moving the resource back to its original path."
    if action_lower == "copy":
        return True, "Can usually be undone by deleting the copied target."
    if action_lower in {"write", "create_file", "create_folder"}:
        return True, "Can be undone when a prior snapshot or created path is recorded."
    if action_lower in {"prepare", "draft"} or parameters.get("draft_only"):
        return True, "Prepared drafts can be discarded before they are sent."
    if action_lower in {"start", "run"} and ("workflow" in tool_lower or parameters.get("workflow")):
        return True, "Workflow starts can be cancelled only if the workflow exposes a cancel step."
    if action_lower in {"send", "reply", "delete", "delete_file"}:
        return False, "This action may not be recoverable after execution."
    if metadata and metadata.reversible:
        return True, "Tool metadata marks this action as reversible when enough state is captured."
    return False, "No automatic undo is available."


def build_approval_context(
    tool_name: str,
    action: str,
    parameters: Dict[str, Any],
    risk_level: RiskLevel,
    reason: str = "",
) -> ApprovalContext:
    """Build structured approval context for risky action prompts."""
    undo_available, undo_description = _undo_description(tool_name, action, parameters)
    safeguards = ["Secrets are redacted in summaries.", "Safe-mode blocks destructive actions."]
    if risk_level == RiskLevel.HIGH:
        safeguards.append("Explicit approval is required before execution.")
    return ApprovalContext(
        risk_level=risk_level.value,
        affected_resources=_affected_resources(parameters),
        expected_effect=_expected_effect(tool_name, action, parameters),
        undo_available=undo_available,
        undo_description=undo_description,
        rationale=parameters.get("why") or parameters.get("reason") or reason,
        safeguards=safeguards,
    )



class ApprovalFlow:
    """
    Manages approval flow for risky actions.
    Integrates with permission profiles and UI confirmation.
    Extended with risk classification and configurable confirmation requirements.
    """

    # Risk classification for actions
    RISK_CLASSIFICATION = {
        # LOW RISK - Read-only, queries, searches
        "web_search": RiskLevel.LOW,
        "weather_report": RiskLevel.LOW,
        "screen_process": RiskLevel.LOW,
        "youtube_video": RiskLevel.LOW,
        "flight_finder": RiskLevel.LOW,
        "daily_briefing": RiskLevel.LOW,
        "obsidian_manager": RiskLevel.LOW,
        "save_memory": RiskLevel.LOW,
        "memory_brain": RiskLevel.LOW,
        # MEDIUM RISK - App launch, browser open, local file ops without delete
        "open_app": RiskLevel.MEDIUM,
        "browser_control": RiskLevel.MEDIUM,
        "file_controller": RiskLevel.MEDIUM,  # except delete action
        "code_helper": RiskLevel.MEDIUM,
        "dev_agent": RiskLevel.MEDIUM,
        "daily_mode": RiskLevel.MEDIUM,
        "self_dev_agent": RiskLevel.HIGH,
        "spotify_controller": RiskLevel.MEDIUM,
        "desktop_control": RiskLevel.MEDIUM,
        "file_processor": RiskLevel.MEDIUM,
        # HIGH RISK - Delete, move, send messages, calendar changes, system changes
        "send_message": RiskLevel.HIGH,
        "reminder": RiskLevel.HIGH,
        "computer_settings": RiskLevel.HIGH,
        "computer_control": RiskLevel.HIGH,
        "gmail_manager": RiskLevel.HIGH,
        "calendar_manager": RiskLevel.HIGH,
        "contact_manager": RiskLevel.HIGH,
        "game_updater": RiskLevel.HIGH,
        "agent_task": RiskLevel.HIGH,
    }

    # Actions that always require confirmation regardless of risk level
    ALWAYS_REQUIRES_CONFIRMATION = {
        "delete",
        "delete_file",
        "shutdown",
        "restart",
        "send",
        "reply",
        "create",
        "update",
        "move",
        "copy",
    }

    def __init__(self):
        self._current_permission_level = PermissionLevel.NORMAL.value
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._ui_callback: Optional[Callable[[ApprovalRequest], None]] = None
        self._lock = threading.Lock()
        self._request_counter = 0
        self._require_confirmation_for_medium = False  # Disabled to allow medium-risk actions without UI callback
        self._require_confirmation_for_high = True
        logger.info("Approval flow initialized")

    def classify_risk(self, tool_name: str, action: str) -> RiskLevel:
        """
        Classify the risk level of an action.

        Args:
            tool_name: Name of the tool
            action: Specific action being performed

        Returns:
            RiskLevel classification
        """
        # Check if action is in high-risk actions list
        action_lower = action.lower()
        if action_lower in self.ALWAYS_REQUIRES_CONFIRMATION:
            return RiskLevel.HIGH

        # File controller needs action-aware classification.
        tool_lower = tool_name.lower()
        if tool_lower == "file_controller":
            if action_lower in {"list", "read", "info", "largest", "disk_usage", "find"}:
                return RiskLevel.LOW
            if action_lower in {
                "delete",
                "delete_file",
                "move",
                "copy",
                "rename",
                "write",
                "create_file",
                "create_folder",
                "organize_desktop",
            }:
                return RiskLevel.MEDIUM

        # Check tool-level classification
        for tool_pattern, risk_level in self.RISK_CLASSIFICATION.items():
            if tool_pattern in tool_lower:
                # Special case: file_controller delete is high risk
                if tool_pattern == "file_controller" and action_lower == "delete":
                    return RiskLevel.HIGH
                return risk_level

        # Default to medium risk for unknown tools
        return RiskLevel.MEDIUM

    def set_permission_level(self, level: str):
        """
        Set the current permission level.

        Args:
            level: Permission level (safe, normal, admin)
        """
        with self._lock:
            self._current_permission_level = level
            logger.info(f"Permission level set to: {level}")

    def set_require_confirmation_for_medium(self, require: bool):
        """
        Set whether medium-risk actions require confirmation.

        Args:
            require: True to require confirmation for medium-risk actions
        """
        with self._lock:
            self._require_confirmation_for_medium = require
            logger.info(f"Medium-risk confirmation requirement set to: {require}")

    def set_require_confirmation_for_high(self, require: bool):
        """Set whether high-risk actions require confirmation."""
        with self._lock:
            self._require_confirmation_for_high = require
            logger.info(f"High-risk confirmation requirement set to: {require}")

    def get_permission_level(self) -> str:
        """Get the current permission level."""
        return self._current_permission_level

    def set_ui_callback(self, callback: Callable[[ApprovalRequest], None]):
        """
        Set the UI callback for approval requests.

        Args:
            callback: Function to call when approval is needed
        """
        self._ui_callback = callback
        logger.info("UI callback set for approval flow")

    def check_and_request_approval(
        self, tool_name: str, action: str, parameters: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Check if action requires approval and request it if needed.
        Uses risk classification to determine confirmation requirements.

        Args:
            tool_name: Name of the tool being called
            action: Specific action being performed
            parameters: Action parameters

        Returns:
            Tuple of (is_allowed, status_message)
        """
        # Classify risk level
        risk_level = self.classify_risk(tool_name, action)

        # Check permission profile first
        is_allowed, message = check_action(self._current_permission_level, action, parameters)

        if is_allowed:
            # Admin bypasses extra confirmation checks.
            if self._current_permission_level == PermissionLevel.ADMIN.value:
                return True, message

            # If the caller already supplied confirmation, honor it.
            confirmed = str(parameters.get("confirmed", "")).lower()
            if confirmed in ("yes", "true", "1", "confirm"):
                return True, message

            # High-risk actions still get a confirmation prompt when possible.
            if risk_level == RiskLevel.HIGH and self._require_confirmation_for_high:
                return self._request_confirmation(
                    tool_name,
                    action,
                    parameters,
                    risk_level,
                    "High-risk action requires confirmation",
                )
            # Medium-risk actions require confirmation if configured.
            elif risk_level == RiskLevel.MEDIUM and self._require_confirmation_for_medium:
                return self._request_confirmation(
                    tool_name,
                    action,
                    parameters,
                    risk_level,
                    "Medium-risk action requires confirmation",
                )
            return True, message

        # If not allowed and requires confirmation
        if "Confirmation required" in message or "blocked" in message.lower():
            # For blocked actions in safe mode, don't even ask
            if "blocked" in message.lower():
                return False, message

            # For actions requiring confirmation, check if UI callback is available
            if not self._ui_callback:
                # No UI callback - return confirmation message directly
                return False, message

            # Request approval through UI
            return self._request_confirmation(tool_name, action, parameters, risk_level, message)

        return False, message

    def _request_confirmation(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        risk_level: RiskLevel,
        reason: str,
    ) -> tuple[bool, str]:
        """
        Request confirmation through UI callback.

        Args:
            tool_name: Name of the tool
            action: Action being performed
            parameters: Action parameters
            risk_level: Risk classification
            reason: Reason for confirmation

        Returns:
            Tuple of (is_allowed, status_message)
        """
        if not self._ui_callback:
            return False, f"{reason} (no UI callback available)"

        # Request approval through UI
        request = ApprovalRequest(
            tool_name=tool_name,
            action=action,
            parameters=parameters,
            permission_level=self._current_permission_level,
            reason=reason,
            risk_level=risk_level,
        )

        with self._lock:
            self._request_counter += 1
            request_id = f"req_{self._request_counter}"
            self._pending_requests[request_id] = request

        # Trigger UI callback
        try:
            self._ui_callback(request)
        except Exception as e:
            logger.error(f"UI callback failed: {e}")
            # On callback failure, return confirmation message
            with self._lock:
                if request_id in self._pending_requests:
                    del self._pending_requests[request_id]
            return False, reason

        # Wait for decision (with timeout)
        decision = request.wait_for_decision(timeout=30.0)

        # Clean up
        with self._lock:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]

        if decision is True:
            # Add confirmation to parameters and re-check
            parameters["confirmed"] = "yes"
            is_allowed, message = check_action(self._current_permission_level, action, parameters)
            logger.info(f"Action approved by user: {tool_name}/{action} (risk: {risk_level.value})")
            return is_allowed, "Action approved by user"
        elif decision is False:
            logger.info(f"Action denied by user: {tool_name}/{action} (risk: {risk_level.value})")
            return False, "Action denied by user"
        else:
            logger.warning(
                f"Approval request timed out: {tool_name}/{action} (risk: {risk_level.value})"
            )
            return False, "Approval request timed out"

    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get list of pending approval requests."""
        with self._lock:
            return list(self._pending_requests.values())

    def approve_request(self, tool_name: str, action: str):
        """
        Approve a pending request by tool name and action.

        Args:
            tool_name: Name of the tool
            action: Action being performed
        """
        with self._lock:
            for request in self._pending_requests.values():
                if request.tool_name == tool_name and request.action == action:
                    request.approve()
                    return

    def deny_request(self, tool_name: str, action: str):
        """
        Deny a pending request by tool name and action.

        Args:
            tool_name: Name of the tool
            action: Action being performed
        """
        with self._lock:
            for request in self._pending_requests.values():
                if request.tool_name == tool_name and request.action == action:
                    request.deny()
                    return


# Global instance
_approval_flow: Optional[ApprovalFlow] = None


def get_approval_flow() -> ApprovalFlow:
    """Get the global approval flow instance."""
    global _approval_flow
    if _approval_flow is None:
        _approval_flow = ApprovalFlow()
    return _approval_flow
