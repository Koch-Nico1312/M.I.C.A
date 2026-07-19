"""
Voice conversation mode state for M.I.C.A.

This module keeps the voice-mode decisions separate from the low-level audio
streaming code: push-to-talk gating, optional wakeword metadata, transcripts,
and interruption requests.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


VoiceInputMode = Literal["open_mic", "push_to_talk", "wakeword"]


@dataclass
class VoiceTurn:
    role: Literal["user", "assistant", "system"]
    text: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "voice"


class VoiceConversationMode:
    """Runtime state for the dedicated voice conversation mode."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._enabled = True
        self._input_mode: VoiceInputMode = "push_to_talk"
        self._push_to_talk_active = False
        self._wakeword_enabled = False
        self._wakeword = "mica"
        self._wakeword_detected_at: str | None = None
        self._wakeword_active_until = 0.0
        self._wakeword_window_seconds = 8.0
        self._last_transcript = ""
        self._last_response = ""
        self._last_interrupt_at: str | None = None
        self._turns: list[VoiceTurn] = []

    def configure(
        self,
        *,
        input_mode: str | None = None,
        push_to_talk_active: bool | None = None,
        wakeword_enabled: bool | None = None,
        wakeword: str | None = None,
    ) -> dict[str, Any]:
        """Update voice mode settings and return the new snapshot."""
        with self._lock:
            if input_mode in {"open_mic", "push_to_talk", "wakeword"}:
                self._input_mode = input_mode  # type: ignore[assignment]
            if push_to_talk_active is not None:
                self._push_to_talk_active = bool(push_to_talk_active)
            if wakeword_enabled is not None:
                self._wakeword_enabled = bool(wakeword_enabled)
                if self._wakeword_enabled and self._input_mode != "open_mic":
                    self._input_mode = "wakeword"
            if wakeword:
                self._wakeword = str(wakeword).strip().lower() or self._wakeword
            return self.snapshot()

    def should_capture_audio(
        self,
        muted: bool,
        mica_speaking: bool | None = None,
        **legacy_kwargs: Any,
    ) -> bool:
        """Return whether microphone frames should be sent to the live session."""
        if mica_speaking is None:
            mica_speaking = bool(legacy_kwargs.get("jarvis_speaking", False))
        with self._lock:
            if not self._enabled or muted or mica_speaking:
                return False
            if self._input_mode == "push_to_talk":
                return self._push_to_talk_active
            if self._input_mode == "wakeword":
                return self._wakeword_enabled and time.monotonic() < self._wakeword_active_until
            return True

    def activate_wakeword(self) -> dict[str, Any]:
        """Open a short audio window after a real detector reports the wake word."""
        with self._lock:
            self._wakeword_detected_at = datetime.now().isoformat()
            self._wakeword_active_until = time.monotonic() + self._wakeword_window_seconds
            self.record_system(f"Wake word '{self._wakeword}' detected.")
            return self.snapshot()

    def waiting_for_wakeword(self) -> bool:
        with self._lock:
            return (
                self._enabled
                and self._input_mode == "wakeword"
                and self._wakeword_enabled
                and time.monotonic() >= self._wakeword_active_until
            )

    def record_transcript(self, role: Literal["user", "assistant"], text: str) -> None:
        """Remember a spoken transcript turn for the UI."""
        cleaned = str(text or "").strip()
        if not cleaned:
            return
        with self._lock:
            if role == "user":
                self._last_transcript = cleaned
            else:
                self._last_response = cleaned
            self._turns.append(VoiceTurn(role=role, text=cleaned))
            self._turns = self._turns[-80:]

    def record_system(self, text: str) -> None:
        cleaned = str(text or "").strip()
        if not cleaned:
            return
        with self._lock:
            self._turns.append(VoiceTurn(role="system", text=cleaned, source="voice_system"))
            self._turns = self._turns[-80:]

    def request_interrupt(self) -> dict[str, Any]:
        """Mark the current spoken response as interrupted."""
        with self._lock:
            self._last_interrupt_at = datetime.now().isoformat()
            self.record_system("Voice output interrupted.")
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe state snapshot."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "input_mode": self._input_mode,
                "push_to_talk_active": self._push_to_talk_active,
                "wakeword_enabled": self._wakeword_enabled,
                "wakeword": self._wakeword,
                "wakeword_detected_at": self._wakeword_detected_at,
                "wakeword_active": time.monotonic() < self._wakeword_active_until,
                "last_transcript": self._last_transcript,
                "last_response": self._last_response,
                "last_interrupt_at": self._last_interrupt_at,
                "turns": [turn.__dict__.copy() for turn in self._turns[-24:]],
            }


_voice_mode: VoiceConversationMode | None = None
_voice_mode_lock = threading.Lock()


def get_voice_conversation_mode() -> VoiceConversationMode:
    """Get the process-wide voice conversation mode state."""
    global _voice_mode
    if _voice_mode is None:
        with _voice_mode_lock:
            if _voice_mode is None:
                _voice_mode = VoiceConversationMode()
    return _voice_mode
