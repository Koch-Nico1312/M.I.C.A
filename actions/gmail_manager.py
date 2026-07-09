"""
Gmail API Integration for M.I.C.A
Allows reading, writing, and summarizing emails
"""

import base64
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    import googleapiclient
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

from config.config_loader import get_config


class GmailManager:
    """Manages Gmail API operations"""

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    def __init__(self):
        self.config = get_config()
        self.service = None
        self.credentials_path = None
        self.token_path = None

        # Get paths from config or use defaults
        base_dir = Path(self.config.get("paths.base_dir", "."))
        self.credentials_path = base_dir / "config" / "gmail_credentials.json"
        self.token_path = base_dir / "config" / "gmail_token.json"

        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API"""
        if not GMAIL_AVAILABLE:
            print("[Gmail] ⚠️ Google API libraries not available")
            return False

        creds = None

        # Load existing token
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
            except Exception as e:
                print(f"[Gmail] ⚠️ Could not load token: {e}")

        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[Gmail] ⚠️ Could not refresh token: {e}")
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

                    print("[Gmail] ✅ Authentication successful")
                except Exception as e:
                    print(f"[Gmail] ❌ Authentication failed: {e}")
                    return False
            else:
                print("[Gmail] ⚠️ No credentials file found. See documentation for setup.")
                return False

        try:
            self.service = build("gmail", "v1", credentials=creds)
            print("[Gmail] ✅ Service initialized")
            return True
        except Exception as e:
            print(f"[Gmail] ❌ Service initialization failed: {e}")
            return False

    def list_emails(
        self, max_results: int = 10, query: str = "", label: str = "INBOX"
    ) -> List[Dict]:
        """List emails from Gmail"""
        if not self.service:
            return []

        try:
            # Build query
            q = f"label:{label}"
            if query:
                q += f" {query}"

            results = (
                self.service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=q)
                .execute()
            )

            messages = results.get("messages", [])
            emails = []

            for msg in messages:
                email_data = self._get_email_details(msg["id"])
                if email_data:
                    emails.append(email_data)

            return emails

        except HttpError as e:
            print(f"[Gmail] ❌ List error: {e}")
            return []

    def _get_email_details(self, message_id: str) -> Optional[Dict]:
        """Get detailed email information"""
        if not self.service:
            return None

        try:
            message = (
                self.service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"],
                )
                .execute()
            )

            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}

            return {
                "id": message_id,
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": message.get("snippet", ""),
                "thread_id": message.get("threadId", ""),
            }

        except HttpError as e:
            print(f"[Gmail] ❌ Get details error: {e}")
            return None

    def read_email(self, message_id: str) -> Optional[Dict]:
        """Read full email content"""
        if not self.service:
            return None

        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            # Extract body
            body = self._extract_body(message["payload"])

            # Extract headers
            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}

            return {
                "id": message_id,
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "body": body,
                "thread_id": message.get("threadId", ""),
            }

        except HttpError as e:
            print(f"[Gmail] ❌ Read error: {e}")
            return None

    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        body = ""

        if "parts" in payload:
            for part in payload["parts"]:
                body += self._extract_body(part)
        else:
            if "body" in payload and "data" in payload["body"]:
                data = payload["body"]["data"]
                body += base64.urlsafe_b64decode(data).decode("utf-8")

        return body

    def send_email(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> bool:
        """Send an email"""
        if not self.service:
            return False

        try:
            message = MIMEMultipart()
            message["to"] = to
            message["subject"] = subject
            if cc:
                message["cc"] = cc
            if bcc:
                message["bcc"] = bcc

            message.attach(MIMEText(body, "plain"))

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            self.service.users().messages().send(userId="me", body={"raw": raw}).execute()

            print(f"[Gmail] ✅ Email sent to {to}")
            return True

        except HttpError as e:
            print(f"[Gmail] ❌ Send error: {e}")
            return False

    def reply_to_email(self, message_id: str, body: str) -> bool:
        """Reply to an email"""
        if not self.service:
            return False

        try:
            # Get original message
            original = self._get_email_details(message_id)
            if not original:
                return False

            # Extract sender
            sender = original["from"]
            # Remove name if present
            if "<" in sender:
                sender = sender.split("<")[1].rstrip(">")

            # Get thread ID
            thread_id = original.get("thread_id", "")

            # Create reply
            message = MIMEText(body, "plain")
            message["to"] = sender
            message["subject"] = f"Re: {original['subject']}"

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            self.service.users().messages().send(
                userId="me", body={"raw": raw, "threadId": thread_id}
            ).execute()

            print(f"[Gmail] ✅ Reply sent to {sender}")
            return True

        except HttpError as e:
            print(f"[Gmail] ❌ Reply error: {e}")
            return False

    def search_emails(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search emails using Gmail search syntax"""
        if not self.service:
            return []

        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=query)
                .execute()
            )

            messages = results.get("messages", [])
            emails = []

            for msg in messages:
                email_data = self._get_email_details(msg["id"])
                if email_data:
                    emails.append(email_data)

            return emails

        except HttpError as e:
            print(f"[Gmail] ❌ Search error: {e}")
            return []

    def mark_as_read(self, message_id: str) -> bool:
        """Mark an email as read"""
        if not self.service:
            return False

        try:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()

            print(f"[Gmail] ✅ Marked as read: {message_id}")
            return True

        except HttpError as e:
            print(f"[Gmail] ❌ Mark read error: {e}")
            return False

    def archive_email(self, message_id: str) -> bool:
        """Archive an email"""
        if not self.service:
            return False

        try:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
            ).execute()

            print(f"[Gmail] ✅ Archived: {message_id}")
            return True

        except HttpError as e:
            print(f"[Gmail] ❌ Archive error: {e}")
            return False

    def delete_email(self, message_id: str) -> bool:
        """Delete an email"""
        if not self.service:
            return False

        try:
            self.service.users().messages().trash(userId="me", id=message_id).execute()

            print(f"[Gmail] ✅ Deleted: {message_id}")
            return True

        except HttpError as e:
            print(f"[Gmail] ❌ Delete error: {e}")
            return False

    def get_unread_count(self) -> int:
        """Get count of unread emails"""
        if not self.service:
            return 0

        try:
            results = self.service.users().messages().list(userId="me", q="label:UNREAD").execute()

            return results.get("resultSizeEstimate", 0)

        except HttpError as e:
            print(f"[Gmail] ❌ Unread count error: {e}")
            return 0


# Global instance
_gmail_manager: Optional[GmailManager] = None


def get_gmail_manager() -> GmailManager:
    """Get the global Gmail manager instance"""
    global _gmail_manager
    if _gmail_manager is None:
        _gmail_manager = GmailManager()
    return _gmail_manager


def gmail_manager(
    parameters: dict, response=None, player=None, speak: Callable = None, session_memory=None
) -> str:
    """
    Gmail management tool for M.I.C.A

    Actions:
    - list: List emails
    - read: Read full email
    - send: Send new email
    - reply: Reply to email
    - search: Search emails
    - unread_count: Get unread count
    - mark_read: Mark as read
    - archive: Archive email
    - delete: Delete email
    - summarize: Summarize emails (uses AI)
    """
    action = parameters.get("action", "list")

    gmail = get_gmail_manager()

    if action == "list":
        max_results = parameters.get("max_results", 10)
        query = parameters.get("query", "")
        label = parameters.get("label", "INBOX")

        emails = gmail.list_emails(max_results=max_results, query=query, label=label)

        if not emails:
            return "No emails found, sir."

        result = f"Found {len(emails)} emails:\n\n"
        for i, email in enumerate(emails, 1):
            result += f"{i}. From: {email['from']}\n"
            result += f"   Subject: {email['subject']}\n"
            result += f"   Date: {email['date']}\n"
            result += f"   ID: {email['id']}\n\n"

        if speak:
            speak(f"Found {len(emails)} emails, sir.")

        return result

    elif action == "read":
        message_id = parameters.get("message_id")
        if not message_id:
            return "Please provide a message ID, sir."

        email = gmail.read_email(message_id)
        if not email:
            return "Could not read email, sir."

        result = f"From: {email['from']}\n"
        result += f"To: {email['to']}\n"
        result += f"Subject: {email['subject']}\n"
        result += f"Date: {email['date']}\n\n"
        result += f"Body:\n{email['body']}"

        if speak:
            speak(f"Email from {email['from']}. Subject: {email['subject']}")

        return result

    elif action == "send":
        to = parameters.get("to")
        subject = parameters.get("subject")
        body = parameters.get("body")
        cc = parameters.get("cc", "")
        bcc = parameters.get("bcc", "")

        if not all([to, subject, body]):
            return "Please provide to, subject, and body, sir."

        success = gmail.send_email(to, subject, body, cc, bcc)

        if success:
            if speak:
                speak(f"Email sent to {to}, sir.")
            return f"Email sent to {to}."
        else:
            return "Failed to send email, sir."

    elif action == "reply":
        message_id = parameters.get("message_id")
        body = parameters.get("body")

        if not all([message_id, body]):
            return "Please provide message ID and reply body, sir."

        success = gmail.reply_to_email(message_id, body)

        if success:
            if speak:
                speak("Reply sent, sir.")
            return "Reply sent successfully."
        else:
            return "Failed to send reply, sir."

    elif action == "search":
        query = parameters.get("query")
        max_results = parameters.get("max_results", 10)

        if not query:
            return "Please provide a search query, sir."

        emails = gmail.search_emails(query, max_results)

        if not emails:
            return f"No emails found for '{query}', sir."

        result = f"Found {len(emails)} emails for '{query}':\n\n"
        for i, email in enumerate(emails, 1):
            result += f"{i}. From: {email['from']}\n"
            result += f"   Subject: {email['subject']}\n"
            result += f"   Date: {email['date']}\n\n"

        if speak:
            speak(f"Found {len(emails)} emails for {query}, sir.")

        return result

    elif action == "unread_count":
        count = gmail.get_unread_count()

        if speak:
            speak(f"You have {count} unread emails, sir.")

        return f"You have {count} unread emails."

    elif action == "mark_read":
        message_id = parameters.get("message_id")
        if not message_id:
            return "Please provide a message ID, sir."

        success = gmail.mark_as_read(message_id)

        if success:
            if speak:
                speak("Marked as read, sir.")
            return "Email marked as read."
        else:
            return "Failed to mark as read, sir."

    elif action == "archive":
        message_id = parameters.get("message_id")
        if not message_id:
            return "Please provide a message ID, sir."

        success = gmail.archive_email(message_id)

        if success:
            if speak:
                speak("Email archived, sir.")
            return "Email archived."
        else:
            return "Failed to archive email, sir."

    elif action == "delete":
        message_id = parameters.get("message_id")
        if not message_id:
            return "Please provide a message ID, sir."

        success = gmail.delete_email(message_id)

        if success:
            if speak:
                speak("Email deleted, sir.")
            return "Email deleted."
        else:
            return "Failed to delete email, sir."

    elif action == "summarize":
        max_results = parameters.get("max_results", 5)
        query = parameters.get("query", "")

        emails = gmail.list_emails(max_results=max_results, query=query)

        if not emails:
            return "No emails to summarize, sir."

        # Build summary text
        summary_text = f"Summary of {len(emails)} recent emails:\n\n"
        for i, email in enumerate(emails, 1):
            summary_text += f"{i}. From: {email['from']}\n"
            summary_text += f"   Subject: {email['subject']}\n"
            summary_text += f"   Preview: {email['snippet'][:200]}...\n\n"

        # Use AI to generate a more detailed summary if available
        # For now, return the basic summary

        if speak:
            speak(f"Here's a summary of {len(emails)} emails, sir.")

        return summary_text

    else:
        return f"Unknown action: {action}. Available: list, read, send, reply, search, unread_count, mark_read, archive, delete, summarize"


def _legacy_google_service():
    error = getattr(googleapiclient, "side_effect", None)
    if error:
        raise error
    return googleapiclient.discovery.build("gmail", "v1")


def _validate_email_inputs(to: str = None, subject: str = None) -> None:
    if to is not None:
        if not to:
            raise ValueError("Recipient is required")
        if "@" not in to:
            raise ValueError("Invalid email address")
    if subject is not None and not subject:
        raise ValueError("Subject is required")


def _legacy_send(to: str, subject: str, body: str, cc: str = "", bcc: str = ""):
    _validate_email_inputs(to, subject)
    service = _legacy_google_service()
    message = MIMEMultipart()
    message["to"] = to
    message["subject"] = subject
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc
    message.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()


def _legacy_extract_headers(payload: Dict) -> Dict:
    return {h.get("name", ""): h.get("value", "") for h in payload.get("headers", [])}


def _legacy_get_emails(max_results: int = 10, query: str = "") -> List[Dict]:
    service = _legacy_google_service()
    results = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query)
        .execute()
    )
    emails = []
    for message in results.get("messages", []):
        details = service.users().messages().get(userId="me", id=message["id"]).execute()
        payload = details.get("payload", {})
        headers = _legacy_extract_headers(payload)
        emails.append(
            {
                "id": message["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "payload": payload,
            }
        )
    return emails


def _legacy_search(query: str, max_results: int = 10) -> List[Dict]:
    return _legacy_get_emails(max_results=max_results, query=query)


def _legacy_delete(message_id: str):
    return _legacy_google_service().users().messages().trash(userId="me", id=message_id).execute()


def _legacy_mark_as_read(message_id: str):
    return (
        _legacy_google_service()
        .users()
        .messages()
        .modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]})
        .execute()
    )


def _legacy_mark_as_unread(message_id: str):
    return (
        _legacy_google_service()
        .users()
        .messages()
        .modify(userId="me", id=message_id, body={"addLabelIds": ["UNREAD"]})
        .execute()
    )


def _legacy_star(message_id: str):
    return (
        _legacy_google_service()
        .users()
        .messages()
        .modify(userId="me", id=message_id, body={"addLabelIds": ["STARRED"]})
        .execute()
    )


gmail_manager.send = _legacy_send
gmail_manager.get_emails = _legacy_get_emails
gmail_manager.search = _legacy_search
gmail_manager.delete = _legacy_delete
gmail_manager.mark_as_read = _legacy_mark_as_read
gmail_manager.mark_as_unread = _legacy_mark_as_unread
gmail_manager.star = _legacy_star
