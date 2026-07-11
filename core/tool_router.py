"""Intent-aware tool catalog selection for smaller model tool contexts."""

from __future__ import annotations

import re
from typing import Any, Iterable


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_äöüÄÖÜß-]+")
_CATEGORY_HINTS = {
    "file": {"file", "folder", "document", "pdf", "datei", "ordner", "dokument"},
    "web": {"web", "search", "browser", "url", "internet", "suche"},
    "message": {"message", "email", "gmail", "send", "reply", "nachricht", "mail"},
    "calendar": {"calendar", "meeting", "appointment", "termin", "kalender"},
    "media": {"spotify", "youtube", "music", "video", "musik"},
    "system": {"computer", "desktop", "app", "settings", "screen", "system"},
    "memory": {"memory", "remember", "note", "wissen", "merke", "notiz"},
    "code": {"code", "test", "debug", "git", "python", "typescript"},
}


class AdaptiveToolRouter:
    def __init__(self, minimum_tools: int = 6, maximum_tools: int = 10):
        self.minimum_tools = max(1, int(minimum_tools))
        self.maximum_tools = max(self.minimum_tools, int(maximum_tools))

    def select(
        self,
        prompt: str,
        declarations: Iterable[dict[str, Any]],
        *,
        always_include: Iterable[str] = (),
    ) -> list[dict[str, Any]]:
        catalog = list(declarations)
        if len(catalog) <= self.maximum_tools:
            return catalog

        query_tokens = self._tokens(prompt)
        expanded = set(query_tokens)
        for hints in _CATEGORY_HINTS.values():
            if query_tokens & hints:
                expanded.update(hints)

        required = {str(name).strip() for name in always_include if str(name).strip()}
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for index, declaration in enumerate(catalog):
            name = str(declaration.get("name") or "")
            searchable = f"{name} {declaration.get('description', '')}"
            tokens = self._tokens(searchable)
            score = len(expanded & tokens) * 5
            if name in required:
                score += 10_000
            if any(token and token in name.lower() for token in query_tokens):
                score += 3
            scored.append((score, -index, declaration))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        positive = [item[2] for item in scored if item[0] > 0]
        target = min(self.maximum_tools, max(self.minimum_tools, len(positive)))
        selected = [item[2] for item in scored[:target]]
        for declaration in catalog:
            if str(declaration.get("name") or "") in required and declaration not in selected:
                if len(selected) >= self.maximum_tools:
                    selected.pop()
                selected.append(declaration)
        return sorted(selected, key=catalog.index)

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {token.lower() for token in _TOKEN_RE.findall(str(value or "")) if len(token) > 1}


_tool_router: AdaptiveToolRouter | None = None


def get_tool_router() -> AdaptiveToolRouter:
    global _tool_router
    if _tool_router is None:
        from config.config_loader import get_config

        config = get_config()
        _tool_router = AdaptiveToolRouter(
            minimum_tools=int(config.get("performance.contextual_tool_minimum", 6) or 6),
            maximum_tools=int(config.get("performance.contextual_tool_maximum", 10) or 10),
        )
    return _tool_router
