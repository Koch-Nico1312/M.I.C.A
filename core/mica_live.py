"""Primary M.I.C.A runtime module.

The implementation is still hosted in ``core.jarvis_live`` during the rename
window so older imports keep working. New code should import from here.
"""

from __future__ import annotations

from typing import Any, Optional

from core.action_loader import get_action_loader
from core.jarvis_live import *  # noqa: F403
from core.jarvis_live import MicaLive as _RuntimeMicaLive


def get_memory_manager() -> Any:
    from memory.memory_manager import MemoryManager

    return MemoryManager()


class _DefaultUI:
    muted = False
    on_text_command = None
    on_voice_interrupt = None

    def write_log(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def set_status(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def set_speaking(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def set_listening(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def set_voice_state(self, *_args: Any, **_kwargs: Any) -> None:
        pass


class MicaLive(_RuntimeMicaLive):
    """M.I.C.A runtime with a minimal no-UI compatibility path."""

    def __init__(self, ui: Optional[Any] = None) -> None:
        super().__init__(ui or _DefaultUI())
        self.is_running = False
        self.conversation_history: list[dict[str, str]] = []

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def process_input(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Input text must be a non-empty string.")
        response = f"M.I.C.A received: {text}"
        self.conversation_history.append({"role": "user", "content": text})
        self.conversation_history.append({"role": "assistant", "content": response})
        return response

    def process_audio(self, audio_data: Any) -> str:
        if audio_data is None:
            raise ValueError("Audio data is required.")
        return "Audio received."

    def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        return self.tool_executor.execute_tool(tool_name, parameters)

    async def execute_tool_async(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        return await self.tool_executor.execute_tool_async(tool_name, parameters)

    def get_memory(self) -> Any:
        return self.memory_manager.load_memory()

    def speak(self, text: str) -> None:
        audio_handler = getattr(self, "audio_handler", None)
        if audio_handler is not None and hasattr(audio_handler, "speak"):
            audio_handler.speak(text)
            return
        super().speak(text)


JarvisLive = MicaLive

__all__ = ["MicaLive", "JarvisLive", "get_config", "get_memory_manager", "get_action_loader"]
