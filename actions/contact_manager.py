from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.paths import project_path


CONTACTS_PATH = project_path("data", "contacts.json")

TOOL_DECLARATION = {
    "name": "contact_manager",
    "description": "Manages the local Jarvis contact book: list, search, create, update, and delete contacts.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list | search | upsert | delete",
            },
            "id": {"type": "STRING", "description": "Existing contact id for update/delete"},
            "query": {"type": "STRING", "description": "Search query"},
            "name": {"type": "STRING", "description": "Contact display name"},
            "email": {"type": "STRING", "description": "Email address"},
            "phone": {"type": "STRING", "description": "Phone number"},
            "notes": {"type": "STRING", "description": "Private notes"},
            "tags": {"type": "STRING", "description": "Comma-separated tags"},
        },
        "required": ["action"],
    },
}


def _load_contacts(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or CONTACTS_PATH
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    contacts = data.get("contacts", data) if isinstance(data, dict) else data
    return contacts if isinstance(contacts, list) else []


def _save_contacts(contacts: list[dict[str, Any]], path: Path | None = None) -> None:
    path = path or CONTACTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"contacts": contacts, "updated_at": datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )


def _parse_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _public_contact(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": contact.get("id"),
        "name": contact.get("name", ""),
        "email": contact.get("email", ""),
        "phone": contact.get("phone", ""),
        "notes": contact.get("notes", ""),
        "tags": contact.get("tags", []),
        "updated_at": contact.get("updated_at"),
    }


def contact_manager(parameters: dict[str, Any], player=None, speak=None) -> str:
    action = str(parameters.get("action", "list")).lower().strip()
    contacts = _load_contacts()

    if action == "list":
        visible = [_public_contact(contact) for contact in contacts[:50]]
        return json.dumps({"contacts": visible}, ensure_ascii=False)

    if action == "search":
        query = str(parameters.get("query", "")).lower().strip()
        if not query:
            return json.dumps({"contacts": []}, ensure_ascii=False)
        matches = []
        for contact in contacts:
            haystack = " ".join(
                str(contact.get(field, "")) for field in ("name", "email", "phone", "notes")
            ).lower()
            haystack += " " + " ".join(str(tag).lower() for tag in contact.get("tags", []))
            if query in haystack:
                matches.append(_public_contact(contact))
        return json.dumps({"contacts": matches[:20]}, ensure_ascii=False)

    if action == "upsert":
        contact_id = str(parameters.get("id", "")).strip() or uuid4().hex
        existing = next((contact for contact in contacts if contact.get("id") == contact_id), None)
        if existing is None:
            existing = {"id": contact_id, "created_at": datetime.now().isoformat()}
            contacts.insert(0, existing)
        for field in ("name", "email", "phone", "notes"):
            if parameters.get(field) is not None:
                existing[field] = str(parameters.get(field, "")).strip()
        if parameters.get("tags") is not None:
            existing["tags"] = _parse_tags(parameters.get("tags"))
        existing["updated_at"] = datetime.now().isoformat()
        _save_contacts(contacts)
        return json.dumps({"status": "saved", "contact": _public_contact(existing)}, ensure_ascii=False)

    if action == "delete":
        contact_id = str(parameters.get("id", "")).strip()
        if not contact_id:
            return "Missing contact id."
        remaining = [contact for contact in contacts if contact.get("id") != contact_id]
        if len(remaining) == len(contacts):
            return "Contact not found."
        _save_contacts(remaining)
        return "Contact deleted."

    return f"Unknown contact action: {action}"
