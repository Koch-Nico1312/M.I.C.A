"""
Proactive Suggestions System
Uses local context to offer timely help before being asked.
"""

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Suggestion:
    """Represents a proactive suggestion."""

    text: str
    priority: str  # high, medium, low
    category: str  # coding, productivity, system, general, health, file_analysis
    timestamp: datetime
    context: str = ""
    action_required: bool = False
    key: str = ""
    reason: str = ""
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a stable dictionary for UI/runtime callers."""
        return {
            "text": self.text,
            "priority": self.priority,
            "category": self.category,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "action_required": self.action_required,
            "key": self.key,
            "reason": self.reason,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class Suppression:
    """Persisted dismissal, mute, or cooldown with an expiry."""

    key: str
    expires_at: datetime
    reason: str = ""

    def is_active(self, now: datetime) -> bool:
        return now < self.expires_at

    def to_dict(self) -> Dict[str, str]:
        return {
            "key": self.key,
            "expires_at": self.expires_at.isoformat(),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Suppression":
        return cls(
            key=str(data["key"]),
            expires_at=datetime.fromisoformat(str(data["expires_at"])),
            reason=str(data.get("reason", "")),
        )


class ProactiveSuggestions:
    """Manages proactive suggestions based on recent local context."""

    def __init__(
        self,
        state_path: Optional[Path] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.config = get_config()
        self.enabled = self.config.get("proactive.enabled", False)
        self.mode = self.config.get("proactive.mode", "normal")
        self.interval = self.config.get("proactive.interval_seconds", 60)
        self.max_suggestions = self.config.get("proactive.max_suggestions", 3)
        self.cooldown_minutes = self.config.get("proactive.cooldown_minutes", 30)
        self.dismiss_minutes = self.config.get("proactive.dismiss_minutes", 240)
        self.mute_minutes = self.config.get("proactive.mute_minutes", 480)
        self.speak_high_priority = self.config.get("proactive.speak_high_priority", True)

        self._now_provider = now_provider or datetime.now
        self.state_path = Path(state_path) if state_path else self._default_state_path()
        self._lock = threading.RLock()

        self.suggestions: List[Suggestion] = []
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.speak_callback: Optional[Callable[[str], None]] = None

        # Backward-compatible tracking shape expected by older tests/modules.
        self.action_history: Dict[str, Dict[str, Any]] = {}
        self.last_action: Optional[str] = None
        self.action_count: Dict[str, int] = {}
        self.error_patterns: List[str] = []
        self.last_file: Optional[Path] = None
        self.last_image: Optional[Path] = None
        self.last_suggestion_time: Optional[datetime] = None

        self.cooldowns: Dict[str, Suppression] = {}
        self.dismissed: Dict[str, Suppression] = {}
        self.mutes: Dict[str, Suppression] = {}
        # Old attribute name kept as an alias for callers that inspect it.
        self.suggestion_cooldown: Dict[str, datetime] = {}

        self._load_state()
        if self.enabled:
            logger.info(
                "Proactive suggestions initialized "
                f"(mode: {self.mode}, interval: {self.interval}s)"
            )

    @property
    def is_running(self) -> bool:
        """Backward-compatible running flag."""
        return self.running

    @is_running.setter
    def is_running(self, value: bool) -> None:
        self.running = bool(value)

    def set_speak_callback(self, callback: Callable[[str], None]):
        """Set the callback function for speaking suggestions."""
        self.speak_callback = callback

    def track_action(self, action: str, success: bool = True):
        """Track user actions for pattern detection."""
        if not isinstance(action, str) or not action.strip():
            raise ValueError("action must be a non-empty string")

        action = action.strip()
        now = self._now()
        self.last_action = action
        record = self.action_history.setdefault(
            action, {"count": 0, "successes": 0, "failures": 0, "last_seen": None}
        )
        record["count"] += 1
        record["last_seen"] = now.isoformat()

        if success:
            record["successes"] += 1
            self.action_count[action] = self.action_count.get(action, 0) + 1
        else:
            record["failures"] += 1
            self.error_patterns.append(action)
            if len(self.error_patterns) > 10:
                self.error_patterns.pop(0)

    def track_file(self, file_path: Path):
        """Track file interactions."""
        self.last_file = Path(file_path)

    def track_image(self, image_path: Path):
        """Track image interactions."""
        self.last_image = Path(image_path)

    def generate_suggestions(self, context: Optional[Dict[str, Any]] = None) -> List[Suggestion]:
        """
        Generate proactive suggestions based on context and patterns.

        Args:
            context: Optional context dictionary with local status information.

        Returns:
            List of new suggestions.
        """
        if self.mode == "off" or (not self.enabled and context is None):
            return []

        with self._lock:
            now = self._context_now(context)
            self._prune_expired(now)
            detected = self._detect_patterns(context=context, now=now)
            filtered = self._filter_by_mode(detected)
            accepted = [item for item in filtered if self._can_show(item, now)]
            accepted = self._dedupe_suggestions(accepted, now)

            for suggestion in accepted:
                self.suggestions.append(suggestion)
                self._set_cooldown(suggestion.key or suggestion.context, now=now)

            self._trim_suggestions()
            if accepted:
                self.last_suggestion_time = now
                self._save_state()

            return accepted

    def detect_patterns(self) -> List[Suggestion]:
        """Backward-compatible public wrapper around pattern detection."""
        return self._detect_patterns(context=None, now=self._now())

    def get_suggestions(self) -> List[Dict[str, Any]]:
        """Get current suggestions as dictionaries for runtime callers."""
        with self._lock:
            return [suggestion.to_dict() for suggestion in self.suggestions]

    def get_suggestion_objects(self) -> List[Suggestion]:
        """Get current suggestions as dataclass objects."""
        with self._lock:
            return self.suggestions.copy()

    def clear_suggestions(self):
        """Clear all visible suggestions."""
        with self._lock:
            self.suggestions.clear()
        logger.debug("Suggestions cleared")

    def dismiss_suggestion(self, index: int, minutes: Optional[int] = None):
        """Dismiss a suggestion by index and suppress it until expiry."""
        with self._lock:
            if 0 <= index < len(self.suggestions):
                dismissed = self.suggestions.pop(index)
                key = dismissed.key or dismissed.context or dismissed.text
                self.dismiss(key, minutes=minutes, reason="dismissed by user")
                logger.debug(f"Dismissed suggestion: {dismissed.text[:50]}...")

    def dismiss(self, key: str, minutes: Optional[int] = None, reason: str = "") -> None:
        """Persistently dismiss a suggestion key until the expiry time."""
        if not key:
            return
        now = self._now()
        expires_at = now + timedelta(minutes=minutes or self.dismiss_minutes)
        self.dismissed[key] = Suppression(key=key, expires_at=expires_at, reason=reason)
        self._save_state()

    def mute(
        self,
        key_or_category: str = "all",
        minutes: Optional[int] = None,
        reason: str = "",
    ) -> None:
        """Mute all suggestions or one category/key until the expiry time."""
        if not key_or_category:
            key_or_category = "all"
        now = self._now()
        expires_at = now + timedelta(minutes=minutes or self.mute_minutes)
        self.mutes[key_or_category] = Suppression(
            key=key_or_category,
            expires_at=expires_at,
            reason=reason,
        )
        self._save_state()

    def unmute(self, key_or_category: str = "all") -> None:
        """Remove a mute by key/category."""
        self.mutes.pop(key_or_category, None)
        self._save_state()

    def should_suggest(self, key: str = "global") -> bool:
        """Backward-compatible cooldown check."""
        now = self._now()
        if self.last_suggestion_time and now < (
            self.last_suggestion_time + timedelta(minutes=self.cooldown_minutes)
        ):
            return False
        return self._check_cooldown(key, now=now)

    def speak_suggestion(self, text: str) -> None:
        """Speak a suggestion via callback, swallowing callback failures."""
        if not self.speak_callback:
            return
        try:
            self.speak_callback(text)
        except Exception as exc:
            logger.error(f"Failed to speak suggestion: {exc}")

    def start(self):
        """Start proactive suggestion monitoring."""
        if self.running:
            return True

        self.running = True
        self.thread = threading.Thread(target=self._suggestion_loop, daemon=True)
        self.thread.start()
        logger.info("Proactive suggestions started")
        return True

    def stop(self):
        """Stop proactive suggestion monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Proactive suggestions stopped")

    def _suggestion_loop(self):
        """Background loop for generating proactive suggestions."""
        while self.running:
            try:
                suggestions = self.generate_suggestions(context={})
                if suggestions and self.speak_callback:
                    for suggestion in suggestions:
                        if suggestion.priority == "high" and self.speak_high_priority:
                            self.speak_suggestion(suggestion.text)
                time.sleep(self.interval)
            except Exception as exc:
                logger.error(f"Proactive suggestions loop error: {exc}")
                time.sleep(self.interval)

    def _detect_patterns(
        self,
        context: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> List[Suggestion]:
        """Detect local patterns and generate candidate suggestions."""
        now = now or self._now()
        context = context or {}
        suggestions: List[Suggestion] = []

        suggestions.extend(self._activity_suggestions(now))
        suggestions.extend(self._error_suggestions(now))
        suggestions.extend(self._file_suggestions(now))
        suggestions.extend(self._image_suggestions(now))
        suggestions.extend(self._contextual_suggestions(context, now))

        return self._dedupe_candidates(suggestions)

    def _activity_suggestions(self, now: datetime) -> List[Suggestion]:
        suggestions = []
        for action, count in list(self.action_count.items()):
            if count < 3:
                continue
            key = f"repetitive:{action}"
            suggestions.append(
                Suggestion(
                    text=(
                        f"You have used '{action}' {count} times recently. "
                        "I can help turn that into a shortcut or workflow."
                    ),
                    priority="medium",
                    category="productivity",
                    timestamp=now,
                    context=f"repetitive_action:{action}",
                    key=key,
                    reason=(
                        f"The action '{action}' crossed the repeat threshold "
                        f"with {count} successful runs."
                    ),
                )
            )
            self.action_count[action] = 0
        return suggestions

    def _error_suggestions(self, now: datetime) -> List[Suggestion]:
        if len(self.error_patterns) < 2:
            return []
        recent_errors = self.error_patterns[-3:]
        self.error_patterns.clear()
        return [
            Suggestion(
                text=(
                    "I noticed repeated failures in recent actions. "
                    "I can review the last errors and suggest a fix path."
                ),
                priority="high",
                category="system",
                timestamp=now,
                context="error_pattern_detected",
                key="error-pattern",
                action_required=True,
                reason=f"Recent failed actions: {', '.join(recent_errors)}.",
            )
        ]

    def _file_suggestions(self, now: datetime) -> List[Suggestion]:
        if not self.last_file:
            return []

        suffix = self.last_file.suffix.lower()
        name = self.last_file.name
        key = f"file:{suffix or 'unknown'}:{name}"
        file_types = {
            ".py": ("I can scan this Python file for risky paths or missing tests.", "coding"),
            ".js": ("I can review this JavaScript file for edge cases.", "coding"),
            ".ts": ("I can review this TypeScript file for type and runtime risks.", "coding"),
            ".tsx": ("I can review this React component for state and UI issues.", "coding"),
            ".md": ("I can tighten this note or turn it into an implementation checklist.", "productivity"),
            ".json": ("I can validate this JSON and summarize its structure.", "file_analysis"),
            ".yaml": ("I can validate this YAML and point out config risks.", "file_analysis"),
            ".yml": ("I can validate this YAML and point out config risks.", "file_analysis"),
        }
        text, category = file_types.get(
            suffix,
            (f"I can inspect {name} and summarize what matters.", "file_analysis"),
        )
        return [
            Suggestion(
                text=text,
                priority="medium",
                category=category,
                timestamp=now,
                context=f"file:{name}",
                key=key,
                action_required=True,
                reason=f"The most recent file context is {name}.",
            )
        ]

    def _image_suggestions(self, now: datetime) -> List[Suggestion]:
        if not self.last_image:
            return []
        return [
            Suggestion(
                text="I can inspect the latest image and describe actionable details.",
                priority="medium",
                category="file_analysis",
                timestamp=now,
                context=f"image:{self.last_image.name}",
                key=f"image:{self.last_image.name}",
                action_required=True,
                reason=f"The latest image context is {self.last_image.name}.",
            )
        ]

    def _contextual_suggestions(
        self,
        context: Dict[str, Any],
        now: datetime,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        suggestions.extend(self._time_suggestions(context, now))
        suggestions.extend(self._calendar_suggestions(context, now))
        suggestions.extend(self._task_suggestions(context, now))
        suggestions.extend(self._system_suggestions(context, now))
        suggestions.extend(self._recent_activity_suggestions(context, now))
        return suggestions

    def _time_suggestions(self, context: Dict[str, Any], now: datetime) -> List[Suggestion]:
        if not (
            context.get("include_time_suggestions")
            or context.get("time_context")
            or context.get("recent_activities")
            or context.get("activities")
        ):
            return []

        hour = now.hour
        if 7 <= hour <= 10:
            return [
                Suggestion(
                    text="Morning context is active. I can help prioritize today's work.",
                    priority="low",
                    category="productivity",
                    timestamp=now,
                    context="time:morning",
                    key="time:morning-plan",
                    reason=f"It is {now.strftime('%H:%M')}, inside the morning planning window.",
                )
            ]
        if 16 <= hour <= 19 and context.get("recent_activities"):
            return [
                Suggestion(
                    text="You have recent activity this afternoon. I can summarize progress and open loops.",
                    priority="low",
                    category="productivity",
                    timestamp=now,
                    context="time:end_of_day",
                    key="time:end-of-day-summary",
                    reason="Recent activities are present near the end-of-day review window.",
                )
            ]
        return []

    def _calendar_suggestions(
        self,
        context: Dict[str, Any],
        now: datetime,
    ) -> List[Suggestion]:
        calendar = context.get("calendar") or {}
        next_event = calendar.get("next_event") or context.get("next_event")
        if not isinstance(next_event, dict):
            return []

        starts_at = self._parse_datetime(next_event.get("start") or next_event.get("starts_at"))
        title = str(next_event.get("title") or next_event.get("summary") or "your next event")
        if not starts_at:
            return []

        minutes_until = int((starts_at - now).total_seconds() // 60)
        if 0 <= minutes_until <= 30:
            return [
                Suggestion(
                    text=f"'{title}' starts in about {minutes_until} minutes. I can gather prep notes.",
                    priority="high",
                    category="productivity",
                    timestamp=now,
                    context=f"calendar:{title}",
                    key=f"calendar:prep:{title}",
                    action_required=True,
                    reason=f"Calendar context shows '{title}' starting within 30 minutes.",
                )
            ]
        return []

    def _task_suggestions(self, context: Dict[str, Any], now: datetime) -> List[Suggestion]:
        tasks = context.get("tasks") or {}
        overdue = tasks.get("overdue") or context.get("overdue_tasks") or []
        due_soon = tasks.get("due_soon") or context.get("due_soon_tasks") or []
        suggestions: List[Suggestion] = []

        if overdue:
            count = len(overdue) if isinstance(overdue, list) else int(overdue)
            suggestions.append(
                Suggestion(
                    text=f"You have {count} overdue task{'s' if count != 1 else ''}. I can help triage them.",
                    priority="high",
                    category="productivity",
                    timestamp=now,
                    context="tasks:overdue",
                    key="tasks:overdue",
                    action_required=True,
                    reason=f"Task context reports {count} overdue item(s).",
                )
            )
        elif due_soon:
            count = len(due_soon) if isinstance(due_soon, list) else int(due_soon)
            suggestions.append(
                Suggestion(
                    text=f"{count} task{'s are' if count != 1 else ' is'} due soon. I can help sequence them.",
                    priority="medium",
                    category="productivity",
                    timestamp=now,
                    context="tasks:due_soon",
                    key="tasks:due-soon",
                    reason=f"Task context reports {count} upcoming item(s).",
                )
            )

        return suggestions

    def _system_suggestions(self, context: Dict[str, Any], now: datetime) -> List[Suggestion]:
        system = context.get("system") or context.get("system_status") or {}
        if not isinstance(system, dict):
            return []

        metrics = {
            "cpu_percent": ("CPU usage is high", "system:cpu"),
            "memory_percent": ("Memory usage is high", "system:memory"),
            "disk_percent": ("Disk usage is high", "system:disk"),
        }
        suggestions: List[Suggestion] = []
        for field, (message, key) in metrics.items():
            value = self._as_float(system.get(field))
            if value is not None and value >= 90:
                suggestions.append(
                    Suggestion(
                        text=f"{message} at {value:.0f}%. I can help identify pressure points.",
                        priority="high",
                        category="system",
                        timestamp=now,
                        context=key,
                        key=key,
                        action_required=True,
                        reason=f"System status reports {field}={value:.0f}%.",
                    )
                )

        battery = self._as_float(system.get("battery_percent"))
        plugged = bool(system.get("plugged_in", system.get("charging", False)))
        if battery is not None and battery <= 15 and not plugged:
            suggestions.append(
                Suggestion(
                    text=f"Battery is at {battery:.0f}% and not charging. I can reduce background work.",
                    priority="high",
                    category="system",
                    timestamp=now,
                    context="system:battery",
                    key="system:battery-low",
                    action_required=True,
                    reason="System status reports low battery without charging.",
                )
            )
        return suggestions

    def _recent_activity_suggestions(
        self,
        context: Dict[str, Any],
        now: datetime,
    ) -> List[Suggestion]:
        activities = context.get("recent_activities") or context.get("activities") or []
        if not isinstance(activities, list) or len(activities) < 3:
            return []

        labels = [
            str(item.get("action", item)) if isinstance(item, dict) else str(item)
            for item in activities[-3:]
        ]
        if len(set(labels)) == 1:
            action = labels[0]
            return [
                Suggestion(
                    text=f"You have repeated '{action}' in recent activity. I can batch or automate it.",
                    priority="medium",
                    category="productivity",
                    timestamp=now,
                    context=f"recent_activity:{action}",
                    key=f"recent-activity:{action}",
                    reason=f"The last {len(labels)} recent activity entries are all '{action}'.",
                )
            ]
        return []

    def _filter_by_mode(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        if self.mode == "subtle":
            return [item for item in suggestions if item.priority == "high"]
        if self.mode == "active":
            return suggestions
        return [item for item in suggestions if item.priority in {"high", "medium"}]

    def _dedupe_candidates(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        seen = set()
        unique = []
        for suggestion in suggestions:
            key = suggestion.key or suggestion.context or suggestion.text
            if key in seen:
                continue
            seen.add(key)
            unique.append(suggestion)
        return unique

    def _dedupe_suggestions(
        self,
        suggestions: List[Suggestion],
        now: datetime,
    ) -> List[Suggestion]:
        active_keys = {
            item.key or item.context or item.text
            for item in self.suggestions
            if not item.expires_at or item.expires_at > now
        }
        unique = []
        for suggestion in suggestions:
            key = suggestion.key or suggestion.context or suggestion.text
            if key in active_keys:
                continue
            active_keys.add(key)
            unique.append(suggestion)
        return unique

    def _can_show(self, suggestion: Suggestion, now: datetime) -> bool:
        key = suggestion.key or suggestion.context or suggestion.text
        if self._is_suppressed(key, suggestion.category, now):
            return False
        return self._check_cooldown(key, now=now)

    def _is_suppressed(self, key: str, category: str, now: datetime) -> bool:
        if self.dismissed.get(key) and self.dismissed[key].is_active(now):
            return True
        for mute_key in ("all", category, key):
            mute = self.mutes.get(mute_key)
            if mute and mute.is_active(now):
                return True
        return False

    def _check_cooldown(self, suggestion_key: str, now: Optional[datetime] = None) -> bool:
        """Check if suggestion is off cooldown."""
        now = now or self._now()
        cooldown = self.cooldowns.get(suggestion_key)
        if cooldown and cooldown.is_active(now):
            return False

        legacy_end = self.suggestion_cooldown.get(suggestion_key)
        if legacy_end and now < legacy_end:
            return False
        if legacy_end and now >= legacy_end:
            self.suggestion_cooldown.pop(suggestion_key, None)

        return True

    def _set_cooldown(self, suggestion_key: str, now: Optional[datetime] = None):
        """Set cooldown for a suggestion."""
        if not suggestion_key:
            return
        now = now or self._now()
        cooldown_end = now + timedelta(minutes=self.cooldown_minutes)
        suppression = Suppression(
            key=suggestion_key,
            expires_at=cooldown_end,
            reason="suggestion cooldown",
        )
        self.cooldowns[suggestion_key] = suppression
        self.suggestion_cooldown[suggestion_key] = cooldown_end

    def _trim_suggestions(self) -> None:
        if len(self.suggestions) > self.max_suggestions:
            self.suggestions = self.suggestions[-self.max_suggestions :]

    def _prune_expired(self, now: datetime) -> None:
        self.cooldowns = {
            key: item for key, item in self.cooldowns.items() if item.is_active(now)
        }
        self.dismissed = {
            key: item for key, item in self.dismissed.items() if item.is_active(now)
        }
        self.mutes = {key: item for key, item in self.mutes.items() if item.is_active(now)}
        self.suggestion_cooldown = {
            key: expires_at
            for key, expires_at in self.suggestion_cooldown.items()
            if expires_at > now
        }

    def _context_now(self, context: Optional[Dict[str, Any]]) -> datetime:
        if not context:
            return self._now()
        return (
            self._parse_datetime(context.get("now"))
            or self._parse_datetime(context.get("current_time"))
            or self._now()
        )

    def _now(self) -> datetime:
        return self._now_provider()

    def _default_state_path(self) -> Path:
        base_dir = Path(__file__).resolve().parent.parent
        return base_dir / "data" / "proactive_suggestions_state.json"

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.cooldowns = self._load_suppressions(data.get("cooldowns", {}))
            self.dismissed = self._load_suppressions(data.get("dismissed", {}))
            self.mutes = self._load_suppressions(data.get("mutes", {}))
            self.suggestion_cooldown = {
                key: item.expires_at for key, item in self.cooldowns.items()
            }
        except Exception as exc:
            logger.error(f"Failed to load proactive suggestion state: {exc}")

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "cooldowns": self._dump_suppressions(self.cooldowns),
                "dismissed": self._dump_suppressions(self.dismissed),
                "mutes": self._dump_suppressions(self.mutes),
            }
            with open(self.state_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
        except Exception as exc:
            logger.error(f"Failed to save proactive suggestion state: {exc}")

    def _load_suppressions(self, data: Dict[str, Any]) -> Dict[str, Suppression]:
        loaded = {}
        for key, value in data.items():
            try:
                loaded[key] = Suppression.from_dict(value)
            except Exception:
                logger.debug(f"Skipping invalid proactive suppression record: {key}")
        return loaded

    def _dump_suppressions(
        self,
        suppressions: Dict[str, Suppression],
    ) -> Dict[str, Dict[str, str]]:
        return {key: item.to_dict() for key, item in suppressions.items()}

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _as_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


# Global instance
_proactive_suggestions: Optional[ProactiveSuggestions] = None


def get_proactive_suggestions() -> ProactiveSuggestions:
    """Get the global proactive suggestions instance."""
    global _proactive_suggestions
    if _proactive_suggestions is None:
        _proactive_suggestions = ProactiveSuggestions()
    return _proactive_suggestions
