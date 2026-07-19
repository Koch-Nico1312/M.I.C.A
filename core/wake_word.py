"""Real wake-word inference adapter for openWakeWord or Porcupine models."""

from __future__ import annotations

import os
from array import array
from pathlib import Path
from typing import Any


class WakeWordDetector:
    def __init__(
        self,
        *,
        engine: str = "auto",
        model_path: str = "",
        threshold: float = 0.5,
        access_key: str = "",
    ):
        self.engine_requested = str(engine or "auto").lower()
        self.model_path = str(model_path or os.getenv("MICA_WAKEWORD_MODEL") or "")
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.access_key = str(access_key or os.getenv("PICOVOICE_ACCESS_KEY") or "")
        self.engine = "unavailable"
        self.last_error = ""
        self._model: Any = None
        self._sample_buffer: list[int] = []
        self._initialize()

    def status(self) -> dict[str, Any]:
        return {
            "available": self._model is not None,
            "engine": self.engine,
            "engine_requested": self.engine_requested,
            "model_path": self.model_path or None,
            "threshold": self.threshold,
            "last_error": self.last_error or None,
            "requires_real_model": True,
        }

    def process_pcm(self, pcm_bytes: bytes) -> bool:
        if self._model is None or not pcm_bytes:
            return False
        samples = array("h")
        samples.frombytes(pcm_bytes)
        try:
            if self.engine == "openwakeword":
                import numpy as np

                prediction = self._model.predict(np.asarray(samples, dtype=np.int16))
                return any(float(score) >= self.threshold for score in prediction.values())
            if self.engine == "porcupine":
                self._sample_buffer.extend(samples)
                frame_length = int(self._model.frame_length)
                while len(self._sample_buffer) >= frame_length:
                    frame = self._sample_buffer[:frame_length]
                    del self._sample_buffer[:frame_length]
                    if self._model.process(frame) >= 0:
                        return True
        except Exception as exc:
            self.last_error = str(exc)
        return False

    def _initialize(self) -> None:
        model = Path(self.model_path).expanduser() if self.model_path else None
        if model is None or not model.is_file():
            self.last_error = "Set MICA_WAKEWORD_MODEL to a real .onnx or .ppn wake-word model."
            return
        suffix = model.suffix.lower()
        engines = [self.engine_requested] if self.engine_requested != "auto" else [
            "openwakeword" if suffix == ".onnx" else "porcupine",
            "porcupine" if suffix == ".onnx" else "openwakeword",
        ]
        for engine in engines:
            try:
                if engine == "openwakeword":
                    from openwakeword.model import Model

                    self._model = Model(wakeword_models=[str(model)])
                    self.engine = engine
                    self.last_error = ""
                    return
                if engine == "porcupine":
                    import pvporcupine

                    if not self.access_key:
                        raise ValueError("PICOVOICE_ACCESS_KEY is required for Porcupine")
                    self._model = pvporcupine.create(access_key=self.access_key, keyword_paths=[str(model)])
                    self.engine = engine
                    self.last_error = ""
                    return
            except Exception as exc:
                self.last_error = str(exc)


_detector: WakeWordDetector | None = None


def get_wake_word_detector() -> WakeWordDetector:
    global _detector
    if _detector is None:
        _detector = WakeWordDetector()
    return _detector


def configure_wake_word_detector(**kwargs: Any) -> WakeWordDetector:
    global _detector
    _detector = WakeWordDetector(**kwargs)
    return _detector
