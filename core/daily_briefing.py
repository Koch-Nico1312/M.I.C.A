"""
Daily Briefing System for JARVIS.
Combines weather, calendar, unread emails, reminders, and memory into one summary.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from config.config_loader import get_config
from core.cross_device import get_cross_device
from core.logger import get_logger
from memory.memory_manager import load_memory

logger = get_logger(__name__)


class DailyBriefing:
    """Schedules and builds daily JARVIS briefings."""

    def __init__(self) -> None:
        self.config = get_config()
        self._speak: Optional[Callable[[str], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_morning_date = ""
        self._last_evening_date = ""

    def set_speak_callback(self, speak: Callable[[str], None]) -> None:
        """Set callback for audio output."""
        self._speak = speak

    def start_scheduler(self) -> bool:
        """Start the background scheduler thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                print("[Briefing] ⚠️ Scheduler already running")
                return True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self._thread.start()
            print("[Briefing] ✅ Scheduler started")
            return True

    def stop_scheduler(self) -> None:
        """Stop the background scheduler thread."""
        self._stop_event.set()
        print("[Briefing] ✅ Scheduler stopped")

    def _run_scheduler(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.config.get("briefing.enabled", False):
                    now = datetime.now()
                    today = now.strftime("%Y-%m-%d")
                    current_time = now.strftime("%H:%M")
                    morning_time = self.config.get("briefing.morning_time", "08:00")
                    evening_time = self.config.get("briefing.evening_time", "21:00")

                    if current_time == morning_time and self._last_morning_date != today:
                        self._last_morning_date = today
                        self.run_morning_briefing()
                    if current_time == evening_time and self._last_evening_date != today:
                        self._last_evening_date = today
                        self.run_evening_briefing()
            except Exception as e:
                print(f"[Briefing] ❌ Scheduler error: {e}")
                logger.exception("Daily briefing scheduler error")
            self._stop_event.wait(30)

    def _extract_memory_value(self, key: str, default: str = "") -> str:
        memory = load_memory()
        identity = memory.get("identity", {})
        value = identity.get(key)
        if isinstance(value, dict):
            return str(value.get("value", default) or default)
        if isinstance(value, str):
            return value
        if key == "city":
            location = identity.get("location", {})
            if isinstance(location, dict):
                city = location.get("city", default)
                return str(city.get("value", default) if isinstance(city, dict) else city)
        return default

    def _get_weather_summary(self) -> str:
        if not self.config.get("briefing.include_weather", True):
            return "Weather: skipped"
        city = self._extract_memory_value("city", "your city")
        return f"Weather: Currently showing results for {city}"

    def _get_calendar_summary(self) -> str:
        if not self.config.get("briefing.include_calendar", True):
            return "Calendar: skipped"
        try:
            from actions.calendar_manager import get_calendar_manager

            calendar = get_calendar_manager()
            events = calendar.list_day_events(datetime.now().astimezone())
            if not events:
                return "Calendar: No events today"
            lines = [f"Calendar: You have {len(events)} events today:"]
            lines.extend(f"   {calendar._format_event(event)}" for event in events)
            return "\n".join(lines)
        except Exception as e:
            print(f"[Briefing] ⚠️ Calendar skipped: {e}")
            return "Calendar: unavailable"

    def _get_email_summary(self) -> str:
        if not self.config.get("briefing.include_email", True):
            return "Email: skipped"
        try:
            from actions.gmail_manager import get_gmail_manager

            gmail = get_gmail_manager()
            unread_count = gmail.get_unread_count()
            emails = gmail.list_emails(max_results=5, query="is:unread")
            subjects = [email.get("subject", "(No subject)") for email in emails[:3]]
            if subjects:
                return f"Email: {unread_count} unread emails. Top: " + ", ".join(
                    f'"{subject}"' for subject in subjects
                )
            return f"Email: {unread_count} unread emails"
        except Exception as e:
            print(f"[Briefing] ⚠️ Email skipped: {e}")
            return "Email: unavailable"

    def _get_reminder_summary(self) -> str:
        if not self.config.get("briefing.include_reminders", True):
            return "Reminders: skipped"
        try:
            reminder_dir = Path.home() / ".jarvis" / "reminders"
            if not reminder_dir.exists():
                return "Reminders: No active reminders"
            reminders = sorted(reminder_dir.glob("JARVISReminder_*.py"))[:5]
            if not reminders:
                return "Reminders: No active reminders"
            return "Reminders: " + ", ".join(path.stem.replace("JARVISReminder_", "") for path in reminders)
        except Exception as e:
            print(f"[Briefing] ⚠️ Reminders skipped: {e}")
            return "Reminders: unavailable"

    def _send_cross_device(self, briefing_text: str) -> None:
        if not self.config.get("briefing.cross_device_push", False):
            return
        try:
            get_cross_device().sync_send_summary(briefing_text)
            print("[Briefing] ✅ Cross-device summary sent")
        except Exception as e:
            print(f"[Briefing] ⚠️ Cross-device push failed: {e}")

    def _speak_briefing(self, briefing_text: str) -> None:
        if self._speak:
            try:
                self._speak(briefing_text)
            except Exception as e:
                print(f"[Briefing] ⚠️ Speak callback failed: {e}")

    def run_morning_briefing(self) -> str:
        """Build and deliver a morning briefing."""
        user_name = self._extract_memory_value("name", "sir")
        today = datetime.now().strftime("%A, %B %d")
        sections = [
            f"Good morning, {user_name}! Here's your briefing for {today}:",
            self._get_weather_summary(),
            self._get_calendar_summary(),
            self._get_email_summary(),
            self._get_reminder_summary(),
            "Have a productive day, sir!",
        ]
        briefing_text = "\n".join(sections)
        self._send_cross_device(briefing_text)
        self._speak_briefing(briefing_text)
        print("[Briefing] ✅ Morning briefing generated")
        return briefing_text

    def run_evening_briefing(self) -> str:
        """Build and deliver an evening summary."""
        user_name = self._extract_memory_value("name", "sir")
        sections = [
            f"Good evening, {user_name}. Here's your evening summary:",
            self._get_calendar_summary(),
            self._get_email_summary(),
            self._get_reminder_summary(),
            "Your active context is saved in memory. Rest well, sir.",
        ]
        briefing_text = "\n".join(sections)
        self._send_cross_device(briefing_text)
        self._speak_briefing(briefing_text)
        print("[Briefing] ✅ Evening briefing generated")
        return briefing_text

    def status(self) -> str:
        """Return current briefing configuration."""
        return (
            "Daily briefing configuration, sir:\n"
            f"- Enabled: {self.config.get('briefing.enabled', False)}\n"
            f"- Morning time: {self.config.get('briefing.morning_time', '08:00')}\n"
            f"- Evening time: {self.config.get('briefing.evening_time', '21:00')}\n"
            f"- Weather: {self.config.get('briefing.include_weather', True)}\n"
            f"- Calendar: {self.config.get('briefing.include_calendar', True)}\n"
            f"- Email: {self.config.get('briefing.include_email', True)}\n"
            f"- Reminders: {self.config.get('briefing.include_reminders', True)}"
        )

    def _write_config_update(self, updates: dict) -> None:
        """Persist simple briefing updates to config.yaml."""
        config_path = Path(self.config.get("paths.base_dir", ".")) / "config.yaml"
        if not config_path.exists():
            return
        try:
            import yaml

            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            briefing = data.setdefault("briefing", {})
            briefing.update(updates)
            config_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
            self.config.reload()
            print("[Briefing] ✅ Configuration updated")
        except Exception as e:
            print(f"[Briefing] ❌ Could not update config: {e}")

    def schedule(self, morning_time: str = "", evening_time: str = "") -> str:
        updates = {}
        if morning_time:
            updates["morning_time"] = morning_time
        if evening_time:
            updates["evening_time"] = evening_time
        if updates:
            self._write_config_update(updates)
        return (
            "Briefing schedule updated, sir.\n"
            f"Morning: {morning_time or self.config.get('briefing.morning_time', '08:00')}\n"
            f"Evening: {evening_time or self.config.get('briefing.evening_time', '21:00')}"
        )

    def enable(self) -> str:
        self._write_config_update({"enabled": True})
        self.start_scheduler()
        return "Daily briefing enabled, sir."

    def disable(self) -> str:
        self._write_config_update({"enabled": False})
        self.stop_scheduler()
        return "Daily briefing disabled, sir."


_daily_briefing: Optional[DailyBriefing] = None
_briefing_lock = threading.Lock()


def get_daily_briefing() -> DailyBriefing:
    """Get the global DailyBriefing instance."""
    global _daily_briefing
    if _daily_briefing is None:
        with _briefing_lock:
            if _daily_briefing is None:
                _daily_briefing = DailyBriefing()
    return _daily_briefing


def daily_briefing(
    parameters: dict,
    response=None,
    player=None,
    speak: Callable[[str], None] = None,
    session_memory=None,
) -> str:
    """Daily briefing tool called by Gemini."""
    action = parameters.get("action", "morning")
    briefing = get_daily_briefing()
    if speak:
        briefing.set_speak_callback(speak)

    try:
        if action == "morning":
            result = briefing.run_morning_briefing()
        elif action == "evening":
            result = briefing.run_evening_briefing()
        elif action == "status":
            result = briefing.status()
        elif action == "schedule":
            result = briefing.schedule(
                morning_time=parameters.get("morning_time", ""),
                evening_time=parameters.get("evening_time", ""),
            )
        elif action == "enable":
            result = briefing.enable()
        elif action == "disable":
            result = briefing.disable()
        else:
            result = f"Unknown briefing action: {action}"

        if player:
            try:
                player.write_log(f"JARVIS: {result}")
            except Exception:
                pass
        return result or "Done."
    except Exception as e:
        print(f"[Briefing] ❌ Tool error: {e}")
        return f"Daily briefing error, sir: {e}"
