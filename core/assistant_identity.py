"""Persistent user-configurable identity for M.I.C.A display and voice aliases."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.paths import project_path


ASSISTANT_IDENTITY_PATH = project_path("data", "assistant_identity.json")
NAME_PATTERN = re.compile(r"^[\w .'-]{2,32}$", re.UNICODE)


@dataclass
class AssistantIdentity:
    display_name: str = "M.I.C.A"
    wake_word: str = "mica"
    aliases: list[str] = field(default_factory=lambda: ["mica", "mika"])


class AssistantIdentityManager:
    def __init__(self, path: Path = ASSISTANT_IDENTITY_PATH):
        self.path = path
        self._lock = threading.RLock()
        self.identity = AssistantIdentity()
        self._load()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self.identity)

    def configure(
        self,
        *,
        display_name: str | None = None,
        wake_word: str | None = None,
        aliases: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if display_name is not None:
                value = str(display_name).strip()
                if not NAME_PATTERN.fullmatch(value):
                    raise ValueError("assistant name has an invalid format")
                self.identity.display_name = value
            if wake_word is not None:
                value = str(wake_word).strip().lower()
                if not NAME_PATTERN.fullmatch(value):
                    raise ValueError("wake word has an invalid format")
                self.identity.wake_word = value
            if aliases is not None:
                normalized = [str(item).strip().lower() for item in aliases if str(item).strip()]
                self.identity.aliases = list(dict.fromkeys([self.identity.wake_word, *normalized]))[:10]
            elif self.identity.wake_word not in self.identity.aliases:
                self.identity.aliases.insert(0, self.identity.wake_word)
            self._save()
            return self.snapshot()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.identity = AssistantIdentity(
                display_name=str(raw.get("display_name") or "M.I.C.A"),
                wake_word=str(raw.get("wake_word") or "mica").lower(),
                aliases=[str(item).lower() for item in raw.get("aliases", ["mica", "mika"]) if item],
            )
        except Exception:
            self.identity = AssistantIdentity()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self.identity), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


_manager: AssistantIdentityManager | None = None


def get_assistant_identity_manager() -> AssistantIdentityManager:
    global _manager
    if _manager is None:
        _manager = AssistantIdentityManager()
    return _manager
