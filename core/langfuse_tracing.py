"""Optional Langfuse tracing helpers.

This module keeps Langfuse as a soft dependency: Jarvis can run normally when
the SDK is absent or the Langfuse service is offline.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

from core.logger import get_logger

logger = get_logger(__name__)


def _enabled() -> bool:
    return os.getenv("LANGFUSE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def _get_client() -> Any | None:
    if not _enabled():
        return None
    try:
        try:
            from langfuse import get_client

            return get_client()
        except ImportError:
            from langfuse import Langfuse

            return Langfuse()
    except Exception as exc:
        logger.debug(f"Langfuse client unavailable: {exc}")
        return None


class _SpanAdapter:
    def __init__(self, span: Any | None):
        self.span = span

    def update(self, **kwargs: Any) -> None:
        if not self.span:
            return
        for method_name in ("update", "end"):
            method = getattr(self.span, method_name, None)
            if callable(method):
                try:
                    method(**kwargs)
                    return
                except TypeError:
                    continue
                except Exception as exc:
                    logger.debug(f"Langfuse span update skipped: {exc}")
                    return


@contextmanager
def trace_tool_execution(tool_name: str, parameters: dict[str, Any]) -> Iterator[_SpanAdapter]:
    client = _get_client()
    span = None
    if client:
        payload = {"tool": tool_name, "parameters": _redact(parameters)}
        try:
            if hasattr(client, "start_span"):
                span = client.start_span(name=f"tool:{tool_name}", input=payload)
            elif hasattr(client, "trace"):
                span = client.trace(name=f"tool:{tool_name}", input=payload)
        except Exception as exc:
            logger.debug(f"Langfuse span start skipped: {exc}")
    adapter = _SpanAdapter(span)
    try:
        yield adapter
    finally:
        flush = getattr(client, "flush", None) if client else None
        if callable(flush):
            try:
                flush()
            except Exception as exc:
                logger.debug(f"Langfuse flush skipped: {exc}")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key.lower() in {"password", "token", "api_key", "secret", "cookie"}:
                redacted[key] = "***"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
