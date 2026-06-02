"""
Google Calendar Integration for JARVIS
Allows managing calendar events, appointments, and schedules
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.paths import project_path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

from config.config_loader import get_config


class CalendarManager:
    """Manages Google Calendar API operations"""

    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar",
    ]

    def __init__(self):
        self.config = get_config()
        self.service = None
        self.credentials_path = None
        self.token_path = None
        self.enabled = bool(self.config.get("calendar.enabled", True))

        # Get paths from config or use defaults
        base_dir = Path(self.config.get("paths.base_dir", "."))
        credentials_path = self.config.get(
            "calendar.credentials_path",
            str(project_path("config", "gmail_credentials.json")),
        )
        token_path = self.config.get(
            "calendar.token_path",
            str(project_path("config", "calendar_token.json")),
        )
        self.credentials_path = Path(credentials_path)
        if not self.credentials_path.is_absolute():
            self.credentials_path = base_dir / self.credentials_path
        self.token_path = Path(token_path)
        if not self.token_path.is_absolute():
            self.token_path = base_dir / self.token_path

        self._authenticate()

    def _authenticate(self):
        """Authenticate with Calendar API"""
        if not self.enabled:
            print("[Calendar] ℹ️ Calendar integration disabled in config")
            return False
        if not CALENDAR_AVAILABLE:
            print("[Calendar] ⚠️ Google API libraries not available")
            return False

        creds = None

        # Load existing token
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
            except Exception as e:
                print(f"[Calendar] ⚠️ Could not load token: {e}")

        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[Calendar] ⚠️ Could not refresh token: {e}")
                    creds = None

            if not creds and self.credentials_path.exists():
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                    # Save credentials
                    with open(self.token_path, "w") as token:
                        token.write(creds.to_json())

                    print("[Calendar] ✅ Authentication successful")
                except Exception as e:
                    print(f"[Calendar] ❌ Authentication failed: {e}")
                    return False
            else:
                print("[Calendar] ⚠️ No credentials file found. See documentation for setup.")
                return False

        try:
            self.service = build("calendar", "v3", credentials=creds)
            print("[Calendar] ✅ Service initialized")
            return True
        except Exception as e:
            print(f"[Calendar] ❌ Service initialization failed: {e}")
            return False

    def _parse_datetime(self, date_str: str, time_str: str = None) -> datetime:
        """Parse date and time strings into datetime object"""
        if time_str:
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return datetime.strptime(date_str, "%Y-%m-%d")

    def _format_event_time(self, event: Dict) -> str:
        """Format event time for display"""
        start = event.get("start", {})
        end = event.get("end", {})

        if "dateTime" in start:
            start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
            return f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"
        else:
            # All-day event
            return "All day"

    def _format_event(self, event: Dict) -> str:
        """Format event for display"""
        summary = event.get("summary", "No title")
        location = event.get("location", "")
        time_str = self._format_event_time(event)

        result = f"- {time_str} {summary}"
        if location:
            result += f" ({location})"
        return result

    def list_events(self, start_date: datetime, end_date: datetime = None) -> List[Dict]:
        """List events in a date range"""
        if not self.service:
            return []

        try:
            # Format dates for API
            start_iso = start_date.isoformat() + "Z"
            if end_date:
                end_iso = end_date.isoformat() + "Z"
            else:
                end_iso = (start_date + timedelta(days=1)).isoformat() + "Z"

            results = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=start_iso,
                    timeMax=end_iso,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = results.get("items", [])
            return events

        except HttpError as e:
            print(f"[Calendar] ❌ List error: {e}")
            return []

    def get_today_events(self) -> List[Dict]:
        """Get events for today"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.list_events(today)

    def get_tomorrow_events(self) -> List[Dict]:
        """Get events for tomorrow"""
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        return self.list_events(tomorrow)

    def get_week_events(self) -> List[Dict]:
        """Get events for the next 7 days"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today + timedelta(days=7)
        return self.list_events(today, end_date)

    def create_event(
        self,
        title: str,
        date: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
    ) -> bool:
        """Create a new calendar event"""
        if not self.service:
            return False

        try:
            start_dt = self._parse_datetime(date, start_time)
            end_dt = self._parse_datetime(date, end_time)

            event = {
                "summary": title,
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": "UTC",
                },
            }

            if description:
                event["description"] = description
            if location:
                event["location"] = location

            self.service.events().insert(calendarId="primary", body=event).execute()

            print(f"[Calendar] ✅ Event created: {title}")
            return True

        except HttpError as e:
            print(f"[Calendar] ❌ Create error: {e}")
            return False

    def delete_event(self, event_id: str) -> bool:
        """Delete an event"""
        if not self.service:
            return False

        try:
            self.service.events().delete(calendarId="primary", eventId=event_id).execute()

            print(f"[Calendar] ✅ Event deleted: {event_id}")
            return True

        except HttpError as e:
            print(f"[Calendar] ❌ Delete error: {e}")
            return False

    def update_event(
        self,
        event_id: str,
        title: str = None,
        date: str = None,
        start_time: str = None,
        end_time: str = None,
    ) -> bool:
        """Update an existing event"""
        if not self.service:
            return False

        try:
            # Get existing event
            event = self.service.events().get(calendarId="primary", eventId=event_id).execute()

            # Update fields
            if title:
                event["summary"] = title

            if date and start_time and end_time:
                start_dt = self._parse_datetime(date, start_time)
                end_dt = self._parse_datetime(date, end_time)
                event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": "UTC"}
                event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": "UTC"}

            self.service.events().update(
                calendarId="primary", eventId=event_id, body=event
            ).execute()

            print(f"[Calendar] ✅ Event updated: {event_id}")
            return True

        except HttpError as e:
            print(f"[Calendar] ❌ Update error: {e}")
            return False

    def get_next_event(self) -> Optional[Dict]:
        """Get the next upcoming event"""
        if not self.service:
            return None

        try:
            now = datetime.now().isoformat() + "Z"
            results = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=1,
                )
                .execute()
            )

            events = results.get("items", [])
            if events:
                return events[0]
            return None

        except HttpError as e:
            print(f"[Calendar] ❌ Next event error: {e}")
            return None

    def search_events(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search events by query"""
        if not self.service:
            return []

        try:
            now = datetime.now().isoformat() + "Z"
            results = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    q=query,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                )
                .execute()
            )

            events = results.get("items", [])
            return events

        except HttpError as e:
            print(f"[Calendar] ❌ Search error: {e}")
            return []

    def find_free_slots(self, date: str = None, duration_minutes: int = 60) -> List[Dict]:
        """Find free time slots on a given date"""
        if not self.service:
            return []

        try:
            if date:
                target_date = datetime.strptime(date, "%Y-%m-%d")
            else:
                target_date = datetime.now()

            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

            events = self.list_events(start_of_day, end_of_day)

            # Build busy slots
            busy_slots = []
            for event in events:
                start = event.get("start", {})
                end = event.get("end", {})
                if "dateTime" in start:
                    start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
                    busy_slots.append((start_dt, end_dt))

            # Find free slots
            free_slots = []
            current_time = start_of_day.replace(hour=8, minute=0)  # Start at 8 AM

            for busy_start, busy_end in sorted(busy_slots):
                if current_time + timedelta(minutes=duration_minutes) <= busy_start:
                    free_slots.append(
                        {
                            "start": current_time.strftime("%H:%M"),
                            "end": busy_start.strftime("%H:%M"),
                            "duration_minutes": (busy_start - current_time).seconds // 60,
                        }
                    )
                current_time = max(current_time, busy_end)

            # Check after last event
            end_of_workday = start_of_day.replace(hour=18, minute=0)  # End at 6 PM
            if current_time + timedelta(minutes=duration_minutes) <= end_of_workday:
                free_slots.append(
                    {
                        "start": current_time.strftime("%H:%M"),
                        "end": end_of_workday.strftime("%H:%M"),
                        "duration_minutes": (end_of_workday - current_time).seconds // 60,
                    }
                )

            return free_slots

        except HttpError as e:
            print(f"[Calendar] ❌ Free slots error: {e}")
            return []


# Global instance
_calendar_manager: Optional[CalendarManager] = None


def get_calendar_manager() -> CalendarManager:
    """Get the global calendar manager instance"""
    global _calendar_manager
    if _calendar_manager is None:
        _calendar_manager = CalendarManager()
    return _calendar_manager


def reset_calendar_manager() -> None:
    """Reset the cached CalendarManager so settings changes take effect."""
    global _calendar_manager
    _calendar_manager = None


def calendar_manager(
    parameters: dict, response=None, player=None, speak: Callable = None, session_memory=None
) -> str:
    """
    Calendar management tool for JARVIS

    Actions:
    - today: List today's events
    - tomorrow: List tomorrow's events
    - this_week: List events for the next 7 days
    - list: List events for a date range
    - create: Create a new event
    - delete: Delete an event
    - update: Update an existing event
    - next: Show the next upcoming event
    - search: Search events
    - free_slots: Find free time slots
    """
    action = parameters.get("action", "today")

    calendar = get_calendar_manager()

    if action == "today":
        events = calendar.get_today_events()

        if not events:
            msg = "No events scheduled for today, sir."
            if speak:
                speak(msg)
            return msg

        result = f"You have {len(events)} events today:\n\n"
        for event in events:
            result += calendar._format_event(event) + "\n"

        if speak:
            speak(f"You have {len(events)} events today, sir.")

        return result

    elif action == "tomorrow":
        events = calendar.get_tomorrow_events()

        if not events:
            msg = "No events scheduled for tomorrow, sir."
            if speak:
                speak(msg)
            return msg

        result = f"You have {len(events)} events tomorrow:\n\n"
        for event in events:
            result += calendar._format_event(event) + "\n"

        if speak:
            speak(f"You have {len(events)} events tomorrow, sir.")

        return result

    elif action == "this_week":
        events = calendar.get_week_events()

        if not events:
            msg = "No events scheduled for the next 7 days, sir."
            if speak:
                speak(msg)
            return msg

        result = f"You have {len(events)} events in the next 7 days:\n\n"
        for event in events:
            result += calendar._format_event(event) + "\n"

        if speak:
            speak(f"You have {len(events)} events this week, sir.")

        return result

    elif action == "list":
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")

        if not start_date:
            return "Please provide a start date (YYYY-MM-DD), sir."

        try:
            start_dt = calendar._parse_datetime(start_date)
            if end_date:
                end_dt = calendar._parse_datetime(end_date)
            else:
                end_dt = start_dt + timedelta(days=1)

            events = calendar.list_events(start_dt, end_dt)

            if not events:
                msg = f"No events found between {start_date} and {end_date or start_date}, sir."
                if speak:
                    speak(msg)
                return msg

            result = f"Found {len(events)} events:\n\n"
            for event in events:
                result += calendar._format_event(event) + "\n"

            if speak:
                speak(f"Found {len(events)} events, sir.")

            return result

        except ValueError:
            return "Invalid date format. Please use YYYY-MM-DD, sir."

    elif action == "create":
        title = parameters.get("title")
        date = parameters.get("date")
        start_time = parameters.get("start_time")
        end_time = parameters.get("end_time")
        description = parameters.get("description", "")
        location = parameters.get("location", "")

        if not all([title, date, start_time, end_time]):
            return "Please provide title, date, start time, and end time, sir."

        success = calendar.create_event(title, date, start_time, end_time, description, location)

        if success:
            msg = f"Event '{title}' created for {date} at {start_time}, sir."
            if speak:
                speak(msg)
            return msg
        else:
            return "Failed to create event, sir."

    elif action == "delete":
        event_id = parameters.get("event_id")
        if not event_id:
            return "Please provide an event ID, sir."

        success = calendar.delete_event(event_id)

        if success:
            msg = "Event deleted, sir."
            if speak:
                speak(msg)
            return msg
        else:
            return "Failed to delete event, sir."

    elif action == "update":
        event_id = parameters.get("event_id")
        title = parameters.get("title")
        date = parameters.get("date")
        start_time = parameters.get("start_time")
        end_time = parameters.get("end_time")

        if not event_id:
            return "Please provide an event ID, sir."

        success = calendar.update_event(event_id, title, date, start_time, end_time)

        if success:
            msg = "Event updated, sir."
            if speak:
                speak(msg)
            return msg
        else:
            return "Failed to update event, sir."

    elif action == "next":
        event = calendar.get_next_event()

        if not event:
            msg = "No upcoming events, sir."
            if speak:
                speak(msg)
            return msg

        summary = event.get("summary", "No title")
        time_str = calendar._format_event_time(event)
        location = event.get("location", "")

        result = f"Next event: {time_str} {summary}"
        if location:
            result += f" at {location}"

        if speak:
            speak(f"Your next event is {summary} at {time_str}")

        return result

    elif action == "search":
        query = parameters.get("query")
        if not query:
            return "Please provide a search query, sir."

        events = calendar.search_events(query)

        if not events:
            msg = f"No events found for '{query}', sir."
            if speak:
                speak(msg)
            return msg

        result = f"Found {len(events)} events for '{query}':\n\n"
        for event in events:
            result += calendar._format_event(event) + "\n"

        if speak:
            speak(f"Found {len(events)} events for {query}, sir.")

        return result

    elif action == "free_slots":
        date = parameters.get("date")
        duration_minutes = 60  # Default 1 hour slots

        free_slots = calendar.find_free_slots(date, duration_minutes)

        if not free_slots:
            msg = "No free time slots found, sir."
            if speak:
                speak(msg)
            return msg

        result = f"Free time slots:\n\n"
        for slot in free_slots:
            result += f"- {slot['start']} - {slot['end']} ({slot['duration_minutes']} minutes)\n"

        if speak:
            speak(f"Found {len(free_slots)} free time slots, sir.")

        return result

    else:
        return f"Unknown action: {action}. Available: today, tomorrow, this_week, list, create, delete, update, next, search, free_slots"
