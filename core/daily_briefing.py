"""
Daily Briefing System for JARVIS
Provides automated morning and evening briefings combining weather, calendar, emails, and reminders
"""

import threading
from datetime import datetime, time
from typing import Callable, Optional

from config.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


class DailyBriefing:
    """Manages daily briefing system with scheduled briefings"""

    def __init__(self):
        self.config = get_config()
        self._speak_callback: Optional[Callable] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Load configuration
        self.enabled = self.config.get("briefing.enabled", False)
        self.morning_time = self.config.get("briefing.morning_time", "08:00")
        self.evening_time = self.config.get("briefing.evening_time", "21:00")
        self.include_weather = self.config.get("briefing.include_weather", True)
        self.include_calendar = self.config.get("briefing.include_calendar", True)
        self.include_email = self.config.get("briefing.include_email", True)
        self.include_reminders = self.config.get("briefing.include_reminders", True)
        self.cross_device_push = self.config.get("briefing.cross_device_push", False)

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

    def _get_weather(self, city: str = None) -> str:
        """Get weather information"""
        if not self.include_weather:
            return ""

        try:
            from memory.memory_manager import load_memory

            memory = load_memory()
            city = city or memory.get("identity", {}).get("city", "Istanbul")

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
            # Check if reminder module has a list method
            # For now, return a placeholder
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
            name = memory.get("identity", {}).get("name", "sir")

            now = datetime.now()
            day_name = now.strftime("%A")
            date_str = now.strftime("%B %d")

            briefing = f"Good morning, {name}! Here's your briefing for {day_name}, {date_str}:\n\n"

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
            name = memory.get("identity", {}).get("name", "sir")

            now = datetime.now()
            day_name = now.strftime("%A")
            date_str = now.strftime("%B %d")

            briefing = f"Good evening, {name}! Here's your summary for {day_name}, {date_str}:\n\n"

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
        status = f"Daily Briefing Status:\n"
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
    Daily briefing tool for JARVIS

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
