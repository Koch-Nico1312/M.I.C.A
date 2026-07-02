"""Draft and approve structured Obsidian notes."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DRAFT_PATH = BASE_DIR / "data" / "note_drafts.json"


@dataclass
class NoteDraft:
    id: str
    title: str
    markdown: str
    tags: list[str]
    sources: list[str]
    links: list[str]
    target_folder: str = "Knowledge/Inbox"
    status: str = "draft"
    duplicate_warning: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


def safe_note_filename(title: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", str(title or "Untitled Note")).strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean or "Untitled Note"


class SmartNoteComposer:
    def __init__(self, path: Path = DRAFT_PATH):
        self.path = path
        self._drafts: dict[str, NoteDraft] = {}
        self._load()

    def create_draft(
        self,
        title: str,
        summary: str,
        *,
        sources: list[str] | None = None,
        tags: list[str] | None = None,
        links: list[str] | None = None,
        target_folder: str = "Knowledge/Inbox",
    ) -> dict[str, Any]:
        title = safe_note_filename(title)
        draft = NoteDraft(
            id=f"note-{uuid.uuid4().hex[:8]}",
            title=title,
            markdown=self._render_markdown(title, summary, sources or [], tags or [], links or []),
            tags=tags or ["jarvis-note"],
            sources=sources or [],
            links=links or [],
            target_folder=target_folder,
            duplicate_warning=self._duplicate_warning(title, target_folder),
        )
        self._drafts[draft.id] = draft
        self._save()
        return asdict(draft)

    def list_drafts(self) -> list[dict[str, Any]]:
        return [asdict(draft) for draft in self._drafts.values()]

    def update_draft(self, draft_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        draft = self._require(draft_id)
        for field_name in ("title", "markdown", "target_folder", "status"):
            if field_name in updates:
                setattr(draft, field_name, str(updates[field_name]))
        for field_name in ("tags", "sources", "links"):
            if isinstance(updates.get(field_name), list):
                setattr(draft, field_name, [str(item) for item in updates[field_name]])
        self._save()
        return asdict(draft)

    def approve_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self._require(draft_id)
        from memory.obsidian_vault import get_obsidian_bridge

        relative_path = f"{draft.target_folder.strip('/')}/{safe_note_filename(draft.title)}.md"
        get_obsidian_bridge().create_note(relative_path, draft.markdown)
        draft.status = "written"
        self._save()
        return {"status": "written", "path": relative_path, "draft": asdict(draft)}

    def _render_markdown(
        self,
        title: str,
        summary: str,
        sources: list[str],
        tags: list[str],
        links: list[str],
    ) -> str:
        lines = ["---", "type: smart-note", "tags:"]
        lines.extend(f"  - {tag}" for tag in (tags or ["jarvis-note"]))
        lines.extend(["---", "", f"# {title}", "", str(summary or "").strip(), "", "## Sources"])
        lines.extend(f"- {source}" for source in sources)
        lines.extend(["", "## Links"])
        lines.extend(f"- [[{link}]]" for link in links)
        return "\n".join(lines).rstrip() + "\n"

    def _duplicate_warning(self, title: str, target_folder: str) -> str:
        try:
            from memory.obsidian_vault import get_obsidian_bridge

            bridge = get_obsidian_bridge()
            matches = bridge.search_notes(title) or []
            if matches:
                return f"{len(matches)} similar note(s) found."
        except Exception:
            return ""
        return ""

    def _require(self, draft_id: str) -> NoteDraft:
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError("unknown note draft")
        return draft

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("drafts", []):
                draft = NoteDraft(**item)
                self._drafts[draft.id] = draft
        except Exception:
            self._drafts = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"drafts": self.list_drafts()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


_composer: SmartNoteComposer | None = None


def get_smart_note_composer() -> SmartNoteComposer:
    global _composer
    if _composer is None:
        _composer = SmartNoteComposer()
    return _composer
