import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from core.external_agent_integrations import get_mem0_bridge


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_PATH = BASE_DIR / "memory" / "long_term.json"
_lock = Lock()
MAX_VALUE_LENGTH = 380
MEMORY_MAX_CHARS = 2200
DEFAULT_MEMORY_CATEGORIES = (
    "identity",
    "preferences",
    "projects",
    "relationships",
    "wishes",
    "knowledge",
    "notes",
    "decisions",
    "todos",
    "daily_summaries",
)


def _resolve_memory_path(memory_path: Path | None = None) -> Path:
    return memory_path or MEMORY_PATH


def _empty_memory() -> dict:
    return {
        "identity": {},
        "preferences": {},
        "projects": {},
        "relationships": {},
        "wishes": {},
        "knowledge": {},
        "notes": {},
        "decisions": {},
        "todos": {},
        "daily_summaries": {},
    }


def load_memory(memory_path: Path | None = None) -> dict:
    path = _resolve_memory_path(memory_path)
    if not path.exists():
        return _empty_memory()
    with _lock:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for key in base:
                    if key not in data:
                        data[key] = {}
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()


def _all_entries(memory: dict) -> list[tuple]:
    entries = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    return entries


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            return None


def cleanup_expired_memories(
    memory_path: Path | None = None, now: datetime | None = None
) -> int:
    """Remove memory entries whose expires_at date has passed."""
    now = now or datetime.now()
    memory = load_memory(memory_path=memory_path)
    removed = 0

    for category, items in list(memory.items()):
        if not isinstance(items, dict):
            continue
        for key, entry in list(items.items()):
            if not isinstance(entry, dict):
                continue
            expires_at = _parse_date(entry.get("expires_at"))
            if expires_at and expires_at < now:
                del items[key]
                removed += 1

    if removed:
        save_memory(memory, memory_path=memory_path)
    return removed


def _trim_to_limit(memory: dict, memory_path: Path | None = None) -> dict:
    if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
        return memory
    entries = _all_entries(memory)
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
        print(f"[Memory] Trimmed {cat}/{key}")
    return memory


def save_memory(memory: dict, memory_path: Path | None = None) -> None:
    if not isinstance(memory, dict):
        return
    path = _resolve_memory_path(memory_path)
    memory = _trim_to_limit(memory, memory_path=path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        path.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            raw_value = value["value"] if isinstance(value, dict) else value
            new_val = _truncate_value(str(raw_value))
            existing = target.get(key, {})
            metadata = {}
            if isinstance(value, dict):
                metadata = {
                    meta_key: meta_value
                    for meta_key, meta_value in value.items()
                    if meta_key != "value" and meta_value is not None
                }

            if not isinstance(existing, dict):
                existing = {}

            entry = dict(existing)
            entry_changed = entry.get("value") != new_val
            entry["value"] = new_val
            entry["updated"] = datetime.now().strftime("%Y-%m-%d")
            if "created" not in entry:
                entry["created"] = entry["updated"]

            for meta_key, meta_value in metadata.items():
                if entry.get(meta_key) != meta_value:
                    entry[meta_key] = meta_value
                    entry_changed = True

            if "tags" not in entry:
                entry["tags"] = []

            if entry_changed or existing != entry:
                target[key] = entry
                changed = True
    return changed


def update_memory(memory_update: dict, memory_path: Path | None = None) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory(memory_path=memory_path)
    memory = load_memory(memory_path=memory_path)
    if _recursive_update(memory, memory_update):
        save_memory(memory, memory_path=memory_path)
        _sync_update_to_mem0(memory_update)
        print(f"[Memory] Saved: {list(memory_update.keys())}")
    return memory


def _sync_update_to_mem0(memory_update: dict) -> None:
    try:
        bridge = get_mem0_bridge()
        lines: list[str] = []
        for category, items in memory_update.items():
            if not isinstance(items, dict):
                continue
            for key, entry in items.items():
                value = entry.get("value") if isinstance(entry, dict) else entry
                if value:
                    lines.append(f"{category}/{key}: {value}")
        if lines:
            bridge.add("\n".join(lines), metadata={"source": "jarvis_long_term_json"})
    except Exception as exc:
        print(f"[Memory] Mem0 sync skipped: {exc}")


def search_mem0_memory(query: str, limit: int = 5) -> dict[str, Any]:
    """Search optional Mem0 retrieval layer without touching local JSON fallback."""
    result = get_mem0_bridge().search(query, limit=limit)
    return result.to_dict()


def format_memory_for_prompt(memory: dict | None) -> str:
    if not memory:
        return ""

    lines = []

    identity = memory.get("identity", {})
    id_fields = ["name", "age", "birthday", "city", "job", "language", "school", "nationality"]
    for field in id_fields:
        entry = identity.get(field)
        if entry:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in id_fields:
            continue
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    prefs = memory.get("preferences", {})
    if prefs:
        lines.append("")
        lines.append("Preferences:")
        for key, entry in list(prefs.items())[:15]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    projects = memory.get("projects", {})
    if projects:
        lines.append("")
        lines.append("Active Projects / Goals:")
        for key, entry in list(projects.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    knowledge = memory.get("knowledge", {})
    if knowledge:
        lines.append("")
        lines.append("Recently learned facts:")
        for key, entry in list(knowledge.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    rels = memory.get("relationships", {})
    if rels:
        lines.append("")
        lines.append("People in their life:")
        for key, entry in list(rels.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    wishes = memory.get("wishes", {})
    if wishes:
        lines.append("")
        lines.append("Wishes / Plans / Wants:")
        for key, entry in list(wishes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    notes = memory.get("notes", {})
    if notes:
        lines.append("")
        lines.append("Other notes:")
        for key, entry in list(notes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key}: {val}")

    if not lines:
        return ""

    header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
    result = header + "\n".join(lines)
    if len(result) > 2000:
        result = result[:1997] + "…"

    return result + "\n"


def remember(
    key: str, value: str, category: str = "notes", memory_path: Path | None = None
) -> str:
    valid = set(DEFAULT_MEMORY_CATEGORIES)
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}}, memory_path=memory_path)
    return f"Remembered: {category}/{key} = {value}"


def remember_structured(
    kind: str,
    key: str,
    value: str,
    *,
    tags: list[str] | None = None,
    expires_in_days: int | None = None,
    metadata: dict[str, Any] | None = None,
    memory_path: Path | None = None,
) -> dict:
    """Persist a typed memory record with tags and optional expiry."""
    category_map = {
        "decision": "decisions",
        "preference": "preferences",
        "todo": "todos",
        "daily_summary": "daily_summaries",
    }
    category = category_map.get(kind, kind if kind in DEFAULT_MEMORY_CATEGORIES else "notes")
    record: dict[str, Any] = {
        "value": value,
        "kind": kind,
        "tags": sorted(set(tags or [])),
    }
    if expires_in_days is not None:
        record["expires_at"] = (datetime.now() + timedelta(days=expires_in_days)).date().isoformat()
    if metadata:
        record.update({k: v for k, v in metadata.items() if v is not None})

    memory = update_memory({category: {key: record}}, memory_path=memory_path)
    _persist_to_obsidian(kind, key, record)
    return memory.get(category, {}).get(key, record)


def remember_decision(
    key: str,
    value: str,
    *,
    tags: list[str] | None = None,
    expires_in_days: int | None = None,
    memory_path: Path | None = None,
) -> dict:
    return remember_structured(
        "decision",
        key,
        value,
        tags=tags or ["decision"],
        expires_in_days=expires_in_days,
        memory_path=memory_path,
    )


def remember_preference(
    key: str,
    value: str,
    *,
    tags: list[str] | None = None,
    memory_path: Path | None = None,
) -> dict:
    return remember_structured(
        "preference", key, value, tags=tags or ["preference"], memory_path=memory_path
    )


def remember_todo(
    key: str,
    value: str,
    *,
    tags: list[str] | None = None,
    expires_in_days: int | None = 30,
    memory_path: Path | None = None,
) -> dict:
    return remember_structured(
        "todo",
        key,
        value,
        tags=tags or ["todo"],
        expires_in_days=expires_in_days,
        memory_path=memory_path,
    )


def remember_daily_summary(
    date_key: str,
    value: str,
    *,
    tags: list[str] | None = None,
    memory_path: Path | None = None,
) -> dict:
    return remember_structured(
        "daily_summary",
        date_key,
        value,
        tags=tags or ["daily-summary"],
        memory_path=memory_path,
    )


def _persist_to_obsidian(kind: str, key: str, record: dict[str, Any]) -> None:
    try:
        from memory.obsidian_vault import get_obsidian_bridge

        bridge = get_obsidian_bridge()
        if hasattr(bridge, "persist_memory_record"):
            bridge.persist_memory_record(kind, key, record)
    except Exception:
        return


def forget(key: str, category: str = "notes", memory_path: Path | None = None) -> str:
    memory = load_memory(memory_path=memory_path)
    cat = memory.get(category, {})
    if key in cat:
        del cat[key]
        memory[category] = cat
        save_memory(memory, memory_path=memory_path)
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"


forget_memory = forget


class MemoryManager:
    """Object-oriented facade around the module-level memory helpers."""

    def __init__(self, memory_path: Path | None = None):
        self.memory_path = memory_path
        self._cache: dict[str, dict] = {}

    def load_memory(self, memory_path: Path | None = None) -> dict:
        path = _resolve_memory_path(memory_path or self.memory_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        self._cache[str(path)] = data
        return data

    def save_memory(self, memory_path: Path | None, data: dict) -> None:
        path = _resolve_memory_path(memory_path or self.memory_path)
        if not path.parent.exists():
            raise FileNotFoundError(str(path.parent))
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._cache[str(path)] = data

    def update_memory(self, memory_path: Path | None, updates: dict) -> dict:
        path = _resolve_memory_path(memory_path or self.memory_path)
        existing = self.load_memory(path)
        existing.update(updates)
        self.save_memory(path, existing)
        return existing

    def check_size_limit(self, data: dict, max_chars: int = MEMORY_MAX_CHARS) -> bool:
        return len(json.dumps(data, ensure_ascii=False)) > max_chars

    def compress_memory(self, data: dict, max_items: int = 100) -> dict:
        if isinstance(data, dict):
            compressed = {}
            for key, value in data.items():
                if isinstance(value, list):
                    compressed[key] = value[:max_items]
                elif isinstance(value, dict):
                    compressed[key] = dict(list(value.items())[:max_items])
                else:
                    compressed[key] = _truncate_value(str(value))
            return compressed
        return {"value": _truncate_value(str(data))}
