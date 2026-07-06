"""
Daily Briefing System for M.I.C.A
Provides automated morning and evening briefings combining weather, calendar, emails, and reminders
"""

import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from config.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


PRIORITY_SCORE = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def weather_action(*args, **kwargs):
    return ""


calendar_manager = None


@dataclass
class BriefingItem:
    category: str
    content: str
    priority: str = "medium"
    source: str = "manual"
    time_cost_minutes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DailyBriefing:
    """Manages daily briefing system with scheduled briefings"""

    def __init__(
        self,
        providers: Optional[Dict[str, Callable[[], Any]]] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self.config = get_config()
        self._speak_callback: Optional[Callable] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._items: List[BriefingItem] = []
        self._history: List[Dict[str, Any]] = []
        self.providers = providers or {}
        self.clock = clock or datetime.now

        # Load configuration
        self.enabled = self.config.get("briefing.enabled", False)
        self.morning_time = self.config.get("briefing.morning_time", "08:00")
        self.evening_time = self.config.get("briefing.evening_time", "21:00")
        self.include_weather = self.config.get("briefing.include_weather", True)
        self.include_calendar = self.config.get("briefing.include_calendar", True)
        self.include_email = self.config.get("briefing.include_email", True)
        self.include_reminders = self.config.get("briefing.include_reminders", True)
        self.cross_device_push = self.config.get("briefing.cross_device_push", False)
        self.default_time_budget_minutes = int(
            self.config.get("briefing.time_budget_minutes", 15) or 15
        )
        self.include_tasks = self.config.get("briefing.include_tasks", True)
        self.include_news = self.config.get("briefing.include_news", False)

    def set_speak_callback(self, callback: Callable):
        """Set the speak callback for audio output"""
        with self._lock:
            self._speak_callback = callback

    def _speak(self, text: str):
        """Speak text using the callback if available"""
        if self._speak_callback:
            try:
                self._speak_callback(text)
            except Exception as e:
                logger.error(f"[DailyBriefing] ❌ Speak error: {e}")

    @staticmethod
    def _memory_value(entry: Any, default: str = "") -> str:
        if isinstance(entry, dict):
            return str(entry.get("value") or default)
        return str(entry or default)

    def _get_weather(self, city: str = None) -> str:
        """Get weather information"""
        if not self.include_weather:
            return ""

        try:
            if "weather" in self.providers:
                result = self.providers["weather"]()
                return self._format_provider_text("Weather", result)

            from memory.memory_manager import load_memory

            memory = load_memory()
            city = city or self._memory_value(memory.get("identity", {}).get("city"), "Istanbul")

            if not self.config.get("briefing.live_weather", False):
                return f"☀️ Weather: No live weather configured for {city}."

            # Use web search for weather
            from actions.web_search import web_search as web_search_action

            result = web_search_action(
                parameters={"query": f"weather in {city} today"}, player=None, session_memory=None
            )
            return f"☀️ Weather: {result[:100]}..."
        except Exception as e:
            logger.error(f"[DailyBriefing] ⚠️ Weather error: {e}")
            return ""

    def _get_calendar(self) -> str:
        """Get calendar events for today"""
        if not self.include_calendar:
            return ""

        try:
            if "calendar" in self.providers:
                result = self.providers["calendar"]()
                return self._format_provider_text("Calendar", result)

            from actions.calendar_manager import calendar_manager

            result = calendar_manager(
                parameters={"action": "today"},
                response=None,
                player=None,
                speak=None,
                session_memory=None,
            )
            return f"📅 Calendar: {result[:300]}..."
        except Exception as e:
            logger.error(f"[DailyBriefing] ⚠️ Calendar error: {e}")
            return ""

    def _get_email(self) -> str:
        """Get unread email count and recent emails"""
        if not self.include_email:
            return ""

        try:
            if "email" in self.providers:
                result = self.providers["email"]()
                return self._format_provider_text("Email", result)

            from actions.gmail_manager import get_gmail_manager

            gmail = get_gmail_manager()
            unread_count = gmail.get_unread_count()

            if unread_count > 0:
                emails = gmail.list_emails(max_results=5)
                top_subjects = [e["subject"][:40] for e in emails[:3]]
                subjects_str = ", ".join(f'"{s}"' for s in top_subjects)
                return f"📧 Email: {unread_count} unread emails. Top: {subjects_str}"
            else:
                return "📧 Email: No unread emails."
        except Exception as e:
            logger.error(f"[DailyBriefing] ⚠️ Email error: {e}")
            return ""

    def _get_reminders(self) -> str:
        """Get active reminders"""
        if not self.include_reminders:
            return ""

        try:
            if "reminders" in self.providers:
                result = self.providers["reminders"]()
                return self._format_provider_text("Reminders", result)
            return "⏰ Reminders: No active reminders"
        except Exception as e:
            logger.error(f"[DailyBriefing] ⚠️ Reminders error: {e}")
            return ""

    def _get_memory_context(self) -> dict:
        """Get memory context for personalization"""
        try:
            from memory.memory_manager import load_memory

            return load_memory()
        except Exception as e:
            logger.error(f"[DailyBriefing] ⚠️ Memory error: {e}")
            return {}

    @staticmethod
    def _format_provider_text(label: str, result: Any) -> str:
        if not result:
            return ""
        if isinstance(result, str):
            return result
        if isinstance(result, list):
            if not result:
                return ""
            lines = []
            for item in result[:5]:
                if isinstance(item, dict):
                    title = item.get("title") or item.get("summary") or item.get("subject")
                    when = item.get("time") or item.get("start") or item.get("date")
                    lines.append(f"- {when + ' ' if when else ''}{title or item}")
                else:
                    lines.append(f"- {item}")
            return f"{label}:\n" + "\n".join(lines)
        return f"{label}: {result}"

    def add_briefing_item(
        self,
        category: str,
        content: str,
        priority: str = "medium",
        *,
        source: str = "manual",
        time_cost_minutes: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add an item to the current briefing."""
        if not isinstance(category, str) or not category.strip():
            raise ValueError("category must be a non-empty string")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be a non-empty string")
        if priority not in PRIORITY_SCORE:
            priority = "medium"
        item = BriefingItem(
            category=category.strip(),
            content=content.strip(),
            priority=priority,
            source=source,
            time_cost_minutes=max(0, int(time_cost_minutes or 0)),
            metadata=metadata or {},
        )
        self._items.append(item)
        return item.to_dict()

    def clear_briefing(self) -> None:
        self._items.clear()

    def get_sorted_items(self) -> List[Dict[str, Any]]:
        items = sorted(
            self._items,
            key=lambda item: (PRIORITY_SCORE.get(item.priority, 2), -item.time_cost_minutes),
            reverse=True,
        )
        return [item.to_dict() for item in items]

    def get_items_by_category(self, category: str) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self._items if item.category == category]

    def get_briefing(self) -> Dict[str, Any]:
        now = self.clock()
        return {
            "date": now.date().isoformat(),
            "generated_at": now.isoformat(),
            "items": self.get_sorted_items(),
        }

    def save_briefing(self) -> Dict[str, Any]:
        briefing = self.get_briefing()
        self._history.append(briefing)
        return briefing

    def get_briefing_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def set_delivery_callback(self, callback: Callable[[str], None]) -> None:
        self.set_speak_callback(callback)

    def deliver_briefing(self) -> str:
        text = self.render_briefing_text(self.get_briefing())
        self._speak(text)
        return text

    def generate_briefing(
        self,
        kind: str = "morning",
        *,
        time_budget_minutes: Optional[int] = None,
        include_live_sources: bool = False,
    ) -> Dict[str, Any]:
        """Generate a deterministic structured briefing."""
        self.clear_briefing()
        memory = self._get_memory_context()
        budget = time_budget_minutes or self.default_time_budget_minutes

        self._add_memory_focus_items(memory, budget)
        self._add_habit_items(memory)

        if include_live_sources:
            source_getters = [
                ("weather", self._get_weather, "medium"),
                ("calendar", self._get_calendar, "high"),
                ("email", self._get_email, "medium"),
                ("reminders", self._get_reminders, "high"),
            ]
            for category, getter, priority in source_getters:
                content = getter()
                if content:
                    self.add_briefing_item(category, content, priority, source="provider")
        else:
            self._add_provider_snapshot_items()

        if kind == "evening":
            self.add_briefing_item(
                "wrap_up",
                "Capture decisions, unresolved tasks, and tomorrow's first focus.",
                "high",
                source="routine",
                time_cost_minutes=5,
            )

        briefing = self.get_briefing()
        briefing["kind"] = kind
        briefing["time_budget_minutes"] = budget
        briefing["focus"] = self._choose_focus(briefing["items"], budget)
        return briefing

    def _add_memory_focus_items(self, memory: Dict[str, Any], budget: int) -> None:
        projects = memory.get("projects", {}) if isinstance(memory, dict) else {}
        todos = memory.get("todos", {}) if isinstance(memory, dict) else {}
        for key, entry in list(projects.items())[:3]:
            value = entry.get("value") if isinstance(entry, dict) else entry
            if value:
                self.add_briefing_item("focus", str(value), "high", source=f"memory:{key}", time_cost_minutes=min(45, max(10, budget)))
        for key, entry in list(todos.items())[:5]:
            value = entry.get("value") if isinstance(entry, dict) else entry
            priority = "high" if isinstance(entry, dict) and "urgent" in entry.get("tags", []) else "medium"
            if value:
                self.add_briefing_item("todo", str(value), priority, source=f"memory:{key}", time_cost_minutes=10)

    def _add_habit_items(self, memory: Dict[str, Any]) -> None:
        habits = memory.get("habits", {}) if isinstance(memory, dict) else {}
        preferences = memory.get("preferences", {}) if isinstance(memory, dict) else {}
        for key, entry in list({**preferences, **habits}.items())[:6]:
            tags = entry.get("tags", []) if isinstance(entry, dict) else []
            value = entry.get("value") if isinstance(entry, dict) else entry
            if value and ("habit" in tags or str(key).startswith("habit_")):
                self.add_briefing_item("habit", str(value), "medium", source=f"memory:{key}", time_cost_minutes=5)

    def _add_provider_snapshot_items(self) -> None:
        for category, priority in [
            ("weather", "medium"),
            ("calendar", "high"),
            ("email", "medium"),
            ("reminders", "high"),
        ]:
            provider = self.providers.get(category)
            if not provider:
                continue
            try:
                content = self._format_provider_text(category.title(), provider())
            except Exception as exc:
                logger.debug("[DailyBriefing] provider %s unavailable: %s", category, exc)
                content = ""
            if content:
                self.add_briefing_item(category, content, priority, source="provider")

    def _choose_focus(self, items: List[Dict[str, Any]], budget: int) -> List[Dict[str, Any]]:
        chosen = []
        remaining = max(0, int(budget or 0))
        for item in items:
            cost = int(item.get("time_cost_minutes") or 0)
            if cost == 0 or cost <= remaining or not chosen:
                chosen.append(item)
                remaining = max(0, remaining - cost)
            if len(chosen) >= 3:
                break
        return chosen

    def render_briefing_text(self, briefing: Dict[str, Any]) -> str:
        kind = briefing.get("kind", "briefing").title()
        lines = [f"{kind} briefing for {briefing.get('date', '')}"]
        focus = briefing.get("focus") or []
        if focus:
            lines.append("Top focus:")
            for item in focus:
                lines.append(f"- {item['content']}")
        other_items = [i for i in briefing.get("items", []) if i not in focus]
        if other_items:
            lines.append("Also:")
            for item in other_items[:8]:
                lines.append(f"- {item['category']}: {item['content']}")
        return "\n".join(lines)

    def _send_cross_device(self, text: str):
        """Send briefing to cross-device"""
        if not self.cross_device_push:
            return

        try:
            from core.cross_device import get_cross_device

            cross_device = get_cross_device()
            cross_device.sync_send_summary(text)
        except Exception as e:
            logger.error(f"[DailyBriefing] ⚠️ Cross-device error: {e}")

    def generate_morning_briefing(self) -> str:
        """Generate morning briefing"""
        try:
            memory = self._get_memory_context()
            name = self._memory_value(memory.get("identity", {}).get("name"), "sir")

            now = self.clock()
            day_name = now.strftime("%A")
            date_str = now.strftime("%B %d")

            briefing = f"Good morning, {name}! Here's your briefing for {day_name}, {date_str}:\n\n"

            structured = self.generate_briefing("morning", include_live_sources=not self.providers)
            if structured.get("focus"):
                briefing += "Focus:\n"
                for item in structured["focus"]:
                    briefing += f"- {item['content']}\n"
                briefing += "\n"

            # Add weather
            weather = self._get_weather()
            if weather:
                briefing += weather + "\n\n"

            # Add calendar
            calendar = self._get_calendar()
            if calendar:
                briefing += calendar + "\n\n"

            # Add email
            email = self._get_email()
            if email:
                briefing += email + "\n\n"

            # Add reminders
            reminders = self._get_reminders()
            if reminders:
                briefing += reminders + "\n\n"

            briefing += "Have a productive day, sir!"

            logger.info("[DailyBriefing] ✅ Morning briefing generated")
            return briefing

        except Exception as e:
            logger.error(f"[DailyBriefing] ❌ Morning briefing error: {e}")
            return "Could not generate morning briefing, sir."

    def generate_evening_briefing(self) -> str:
        """Generate evening summary"""
        try:
            memory = self._get_memory_context()
            name = self._memory_value(memory.get("identity", {}).get("name"), "sir")

            now = self.clock()
            day_name = now.strftime("%A")
            date_str = now.strftime("%B %d")

            briefing = f"Good evening, {name}! Here's your summary for {day_name}, {date_str}:\n\n"

            structured = self.generate_briefing("evening", include_live_sources=not self.providers)
            if structured.get("focus"):
                briefing += "Wrap-up priorities:\n"
                for item in structured["focus"]:
                    briefing += f"- {item['content']}\n"
                briefing += "\n"

            # Add calendar (what's left today)
            calendar = self._get_calendar()
            if calendar:
                briefing += calendar + "\n\n"

            # Add email
            email = self._get_email()
            if email:
                briefing += email + "\n\n"

            briefing += "Have a good evening, sir!"

            logger.info("[DailyBriefing] ✅ Evening briefing generated")
            return briefing

        except Exception as e:
            logger.error(f"[DailyBriefing] ❌ Evening briefing error: {e}")
            return "Could not generate evening briefing, sir."

    def start_scheduler(self):
        """Start the briefing scheduler"""
        with self._lock:
            if self._running:
                logger.warning("[DailyBriefing] ⚠️ Scheduler already running")
                return

            if not self.enabled:
                logger.info("[DailyBriefing] ℹ️ Briefing disabled, not starting scheduler")
                return

            self._running = True
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._scheduler_thread.start()
            logger.info("[DailyBriefing] ✅ Scheduler started")

    def stop_scheduler(self):
        """Stop the briefing scheduler"""
        with self._lock:
            self._running = False
            if self._scheduler_thread:
                self._scheduler_thread.join(timeout=5)
            logger.info("[DailyBriefing] ✅ Scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("[DailyBriefing] 🔄 Scheduler loop started")

        while self._running:
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M")

                # Check for morning briefing
                if current_time == self.morning_time:
                    logger.info("[DailyBriefing] 🌅 Triggering morning briefing")
                    briefing = self.generate_morning_briefing()
                    self._speak(briefing)
                    self._send_cross_device(briefing)
                    # Wait 1 minute to avoid multiple triggers
                    threading.Event().wait(60)

                # Check for evening briefing
                elif current_time == self.evening_time:
                    logger.info("[DailyBriefing] 🌙 Triggering evening briefing")
                    briefing = self.generate_evening_briefing()
                    self._speak(briefing)
                    self._send_cross_device(briefing)
                    # Wait 1 minute to avoid multiple triggers
                    threading.Event().wait(60)

                # Sleep for 10 seconds
                threading.Event().wait(10)

            except Exception as e:
                logger.error(f"[DailyBriefing] ❌ Scheduler loop error: {e}")
                threading.Event().wait(30)

    def get_status(self) -> str:
        """Get briefing status"""
        status = "Daily Briefing Status:\n"
        status += f"  Enabled: {self.enabled}\n"
        status += f"  Morning Time: {self.morning_time}\n"
        status += f"  Evening Time: {self.evening_time}\n"
        status += f"  Include Weather: {self.include_weather}\n"
        status += f"  Include Calendar: {self.include_calendar}\n"
        status += f"  Include Email: {self.include_email}\n"
        status += f"  Include Reminders: {self.include_reminders}\n"
        status += f"  Cross-Device Push: {self.cross_device_push}\n"
        status += f"  Scheduler Running: {self._running}"
        return status

    def set_schedule(self, morning_time: str = None, evening_time: str = None):
        """Set briefing schedule"""
        if morning_time:
            self.morning_time = morning_time
            logger.info(f"[DailyBriefing] ✅ Morning time set to {morning_time}")

        if evening_time:
            self.evening_time = evening_time
            logger.info(f"[DailyBriefing] ✅ Evening time set to {evening_time}")

    def enable(self):
        """Enable daily briefing"""
        self.enabled = True
        logger.info("[DailyBriefing] ✅ Enabled")

    def disable(self):
        """Disable daily briefing"""
        self.enabled = False
        self.stop_scheduler()
        logger.info("[DailyBriefing] ✅ Disabled")


# Global instance
_daily_briefing: Optional[DailyBriefing] = None
_briefing_lock = threading.Lock()


def get_daily_briefing() -> DailyBriefing:
    """Get the global daily briefing instance"""
    global _daily_briefing
    if _daily_briefing is None:
        with _briefing_lock:
            if _daily_briefing is None:
                _daily_briefing = DailyBriefing()
    return _daily_briefing


def daily_briefing(
    parameters: dict, response=None, player=None, speak: Callable = None, session_memory=None
) -> str:
    """
    Daily briefing tool for M.I.C.A

    Actions:
    - morning: Generate and speak morning briefing
    - evening: Generate and speak evening summary
    - status: Show briefing configuration
    - schedule: Set briefing times
    - enable: Enable automatic briefings
    - disable: Disable automatic briefings
    """
    action = parameters.get("action", "morning")

    briefing = get_daily_briefing()

    if speak:
        briefing.set_speak_callback(speak)

    if action == "morning":
        result = briefing.generate_morning_briefing()
        if speak:
            speak(result)
        return result

    elif action == "evening":
        result = briefing.generate_evening_briefing()
        if speak:
            speak(result)
        return result

    elif action == "status":
        return briefing.get_status()

    elif action == "schedule":
        morning_time = parameters.get("morning_time")
        evening_time = parameters.get("evening_time")

        if not morning_time and not evening_time:
            return "Please provide at least one time (morning_time or evening_time), sir."

        briefing.set_schedule(morning_time, evening_time)

        msg = "Briefing schedule updated"
        if morning_time:
            msg += f" to {morning_time}"
        if evening_time:
            msg += f" and {evening_time}"
        msg += ", sir."

        if speak:
            speak(msg)
        return msg

    elif action == "enable":
        briefing.enable()
        briefing.start_scheduler()
        msg = "Daily briefing enabled, sir."
        if speak:
            speak(msg)
        return msg

    elif action == "disable":
        briefing.disable()
        msg = "Daily briefing disabled, sir."
        if speak:
            speak(msg)
        return msg

    else:
        return f"Unknown action: {action}. Available: morning, evening, status, schedule, enable, disable"
