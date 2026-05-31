"""
Google Calendar API Integration for JARVIS.
Allows listing, creating, updating, deleting, and searching calendar events.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    """Manages Google Calendar API operations."""

    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar",
    ]

    def __init__(self) -> None:
        self.config = get_config()
        self.service: Optional[Any] = None

        base_dir = Path(self.config.get("paths.base_dir", "."))
        credentials_path = self.config.get(
            "calendar.credentials_path", "./config/gmail_credentials.json"
        )
        token_path = self.config.get("calendar.token_path", "./config/calendar_token.json")

        self.credentials_path = self._resolve_path(base_dir, credentials_path)
        self.token_path = self._resolve_path(base_dir, token_path)

        if self.config.get("calendar.enabled", True):
            self._authenticate()

    def _resolve_path(self, base_dir: Path, raw_path: str) -> Path:
        path = Path(raw_path)
        return path if path.is_absolute() else base_dir / path

    def _authenticate(self) -> bool:
        """Authenticate with Google Calendar API."""
        if not CALENDAR_AVAILABLE:
            print("[Calendar] ⚠️ Google API libraries not available")
            return False

        creds = None

        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
            except Exception as e:
                print(f"[Calendar] ⚠️ Could not load token: {e}")

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
                    self.token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.token_path, "w", encoding="utf-8") as token:
                        token.write(creds.to_json())
                    print("[Calendar] ✅ Authentication successful")
                except Exception as e:
                    print(f"[Calendar] ❌ Authentication failed: {e}")
                    return False
            else:
                print("[Calendar] ⚠️ No credentials file found. See Gmail setup credentials.")
                return False

        try:
            self.service = build("calendar", "v3", credentials=creds)
            print("[Calendar] ✅ Service initialized")
            return True
        except Exception as e:
            print(f"[Calendar] ❌ Service initialization failed: {e}")
            return False

    def _day_bounds(self, day: datetime) -> Tuple[datetime, datetime]:
        start = datetime.combine(day.date(), time.min).astimezone()
        end = datetime.combine(day.date(), time.max).astimezone()
        return start, end

    def _parse_date(self, date_str: str) -> datetime:
        if not date_str:
            return datetime.now().astimezone()
        return datetime.strptime(date_str, "%Y-%m-%d").astimezone()

    def _parse_datetime(self, date_str: str, time_str: str) -> datetime:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").astimezone()

    def _format_event_time(self, event: Dict[str, Any]) -> str:
        start = event.get("start", {})
        raw_start = start.get("dateTime") or start.get("date", "")
        if "T" not in raw_start:
            return "All day"
        try:
            return datetime.fromisoformat(raw_start.replace("Z", "+00:00")).strftime("%H:%M")
        except ValueError:
            return raw_start

    def _format_event(self, event: Dict[str, Any]) -> str:
        event_time = self._format_event_time(event)
        title = event.get("summary", "Untitled event")
        location = event.get("location", "")
        event_id = event.get("id", "")
        location_text = f" ({location})" if location else ""
        return f"- {event_time} {title}{location_text} [ID: {event_id}]"

    def list_events(self, start_dt: datetime, end_dt: datetime, max_results: int = 20) -> List[Dict[str, Any]]:
        """List events between two datetimes."""
        if not self.service:
            return []

        try:
            results = self.service.events().list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return results.get("items", [])
        except HttpError as e:
            print(f"[Calendar] ❌ List error: {e}")
            return []
        except Exception as e:
            print(f"[Calendar] ❌ List exception: {e}")
            return []

    def list_day_events(self, day: datetime) -> List[Dict[str, Any]]:
        start_dt, end_dt = self._day_bounds(day)
        return self.list_events(start_dt, end_dt)

    def create_event(
        self,
        title: str,
        date: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Create a calendar event."""
        if not self.service:
            return None

        try:
            start_dt = self._parse_datetime(date, start_time)
            end_dt = self._parse_datetime(date, end_time)
            event_body = {
                "summary": title,
                "location": location,
                "description": description,
                "start": {"dateTime": start_dt.isoformat()},
                "end": {"dateTime": end_dt.isoformat()},
            }
            event = self.service.events().insert(calendarId="primary", body=event_body).execute()
            print(f"[Calendar] ✅ Event created: {event.get('id')}")
            return event
        except HttpError as e:
            print(f"[Calendar] ❌ Create error: {e}")
            return None
        except Exception as e:
            print(f"[Calendar] ❌ Create exception: {e}")
            return None

    def update_event(
        self,
        event_id: str,
        title: str = "",
        date: str = "",
        start_time: str = "",
        end_time: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Update a calendar event."""
        if not self.service:
            return None

        try:
            event = self.service.events().get(calendarId="primary", eventId=event_id).execute()
            if title:
                event["summary"] = title
            if date and start_time:
                event["start"] = {"dateTime": self._parse_datetime(date, start_time).isoformat()}
            if date and end_time:
                event["end"] = {"dateTime": self._parse_datetime(date, end_time).isoformat()}

            updated = self.service.events().update(
                calendarId="primary", eventId=event_id, body=event
            ).execute()
            print(f"[Calendar] ✅ Event updated: {event_id}")
            return updated
        except HttpError as e:
            print(f"[Calendar] ❌ Update error: {e}")
            return None
        except Exception as e:
            print(f"[Calendar] ❌ Update exception: {e}")
            return None

    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        if not self.service:
            return False

        try:
            self.service.events().delete(calendarId="primary", eventId=event_id).execute()
            print(f"[Calendar] ✅ Event deleted: {event_id}")
            return True
        except HttpError as e:
            print(f"[Calendar] ❌ Delete error: {e}")
            return False
        except Exception as e:
            print(f"[Calendar] ❌ Delete exception: {e}")
            return False

    def search_events(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search upcoming calendar events."""
        if not self.service:
            return []

        try:
            now = datetime.now().astimezone()
            future = now + timedelta(days=365)
            results = self.service.events().list(
                calendarId="primary",
                q=query,
                timeMin=now.isoformat(),
                timeMax=future.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return results.get("items", [])
        except HttpError as e:
            print(f"[Calendar] ❌ Search error: {e}")
            return []
        except Exception as e:
            print(f"[Calendar] ❌ Search exception: {e}")
            return []

    def next_event(self) -> Optional[Dict[str, Any]]:
        """Get the next upcoming event."""
        now = datetime.now().astimezone()
        events = self.list_events(now, now + timedelta(days=365), max_results=1)
        return events[0] if events else None

    def free_slots(self, day: datetime, work_start: str = "09:00", work_end: str = "18:00") -> List[str]:
        """Find free slots between calendar events for a given day."""
        start_dt, end_dt = self._day_bounds(day)
        events = self.list_events(start_dt, end_dt, max_results=50)
        slot_start = self._parse_datetime(day.strftime("%Y-%m-%d"), work_start)
        slot_end = self._parse_datetime(day.strftime("%Y-%m-%d"), work_end)
        busy: List[Tuple[datetime, datetime]] = []

        for event in events:
            raw_start = event.get("start", {}).get("dateTime")
            raw_end = event.get("end", {}).get("dateTime")
            if not raw_start or not raw_end:
                continue
            try:
                busy_start = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
                busy_end = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
                busy.append((busy_start, busy_end))
            except ValueError:
                continue

        busy.sort(key=lambda item: item[0])
        free: List[str] = []
        cursor = slot_start
        for busy_start, busy_end in busy:
            if busy_start > cursor:
                free.append(f"{cursor.strftime('%H:%M')}-{busy_start.strftime('%H:%M')}")
            if busy_end > cursor:
                cursor = busy_end
        if cursor < slot_end:
            free.append(f"{cursor.strftime('%H:%M')}-{slot_end.strftime('%H:%M')}")
        return free

    def format_events(self, events: List[Dict[str, Any]], label: str) -> str:
        if not events:
            return f"No calendar events found for {label}, sir."
        lines = [f"Calendar events for {label}, sir:"]
        lines.extend(self._format_event(event) for event in events)
        return "\n".join(lines)


_calendar_manager: Optional[CalendarManager] = None


def get_calendar_manager() -> CalendarManager:
    """Get the global Calendar manager instance."""
    global _calendar_manager
    if _calendar_manager is None:
        _calendar_manager = CalendarManager()
    return _calendar_manager


def calendar_manager(
    parameters: dict,
    response=None,
    player=None,
    speak: Callable[[str], None] = None,
    session_memory=None,
) -> str:
    """Calendar management tool for JARVIS."""
    action = parameters.get("action", "today")
    calendar = get_calendar_manager()

    try:
        if action == "today":
            events = calendar.list_day_events(datetime.now().astimezone())
            result = calendar.format_events(events, "today")
        elif action == "tomorrow":
            events = calendar.list_day_events(datetime.now().astimezone() + timedelta(days=1))
            result = calendar.format_events(events, "tomorrow")
        elif action == "this_week":
            now = datetime.now().astimezone()
            events = calendar.list_events(now, now + timedelta(days=7), max_results=50)
            result = calendar.format_events(events, "the next 7 days")
        elif action == "list":
            start_date = parameters.get("start_date", "")
            end_date = parameters.get("end_date", "")
            if not start_date or not end_date:
                return "Please provide start_date and end_date in YYYY-MM-DD format, sir."
            start_dt = calendar._parse_date(start_date)
            end_dt = calendar._parse_date(end_date) + timedelta(days=1)
            events = calendar.list_events(start_dt, end_dt, max_results=50)
            result = calendar.format_events(events, f"{start_date} to {end_date}")
        elif action == "create":
            title = parameters.get("title", "")
            date = parameters.get("date", "")
            start_time = parameters.get("start_time", "")
            end_time = parameters.get("end_time", "")
            if not all([title, date, start_time, end_time]):
                return "Please provide title, date, start_time, and end_time, sir."
            event = calendar.create_event(
                title=title,
                date=date,
                start_time=start_time,
                end_time=end_time,
                description=parameters.get("description", ""),
                location=parameters.get("location", ""),
            )
            result = (
                f"Created calendar event '{title}', sir. ID: {event.get('id')}"
                if event else "Could not create calendar event, sir."
            )
        elif action == "delete":
            event_id = parameters.get("event_id", "")
            if not event_id:
                return "Please provide an event_id, sir."
            result = "Deleted calendar event, sir." if calendar.delete_event(event_id) else "Could not delete calendar event, sir."
        elif action == "update":
            event_id = parameters.get("event_id", "")
            if not event_id:
                return "Please provide an event_id, sir."
            event = calendar.update_event(
                event_id=event_id,
                title=parameters.get("title", ""),
                date=parameters.get("date", ""),
                start_time=parameters.get("start_time", ""),
                end_time=parameters.get("end_time", ""),
            )
            result = (
                f"Updated calendar event, sir. ID: {event.get('id')}"
                if event else "Could not update calendar event, sir."
            )
        elif action == "next":
            event = calendar.next_event()
            result = (
                "Next calendar event, sir:\n" + calendar._format_event(event)
                if event else "No upcoming calendar events found, sir."
            )
        elif action == "search":
            query = parameters.get("query", "")
            if not query:
                return "Please provide a search query, sir."
            events = calendar.search_events(query)
            result = calendar.format_events(events, f"search '{query}'")
        elif action == "free_slots":
            day_value = parameters.get("date", "today")
            day = datetime.now().astimezone()
            if day_value == "tomorrow":
                day += timedelta(days=1)
            elif day_value and day_value != "today":
                day = calendar._parse_date(day_value)
            slots = calendar.free_slots(day)
            result = (
                f"Free slots for {day.strftime('%Y-%m-%d')}, sir:\n- " + "\n- ".join(slots)
                if slots else f"No free slots found for {day.strftime('%Y-%m-%d')}, sir."
            )
        else:
            result = f"Unknown calendar action: {action}"

        if speak and action in {"today", "tomorrow", "next", "free_slots"}:
            speak(result)
        if player:
            try:
                player.write_log(f"JARVIS: {result}")
            except Exception:
                pass
        return result or "Done."
    except Exception as e:
        print(f"[Calendar] ❌ Tool error: {e}")
        return f"Calendar error, sir: {e}"
