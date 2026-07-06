"""
Audio handler module for M.I.C.A AI Assistant.

This module provides:
- Audio input/output management
- Microphone handling
- Audio playback
- Audio configuration
"""

import asyncio
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

try:
    import sounddevice as sd
except ImportError:
    sd = None

logger = get_logger(__name__)


@dataclass
class AudioConfig:
    """Audio configuration."""

    send_sample_rate: int = 16000
    receive_sample_rate: int = 24000
    channels: int = 1
    chunk_size: int = 1024
    dtype: str = "int16"
    use_double_buffer: bool = False
    buffer_size: int = 2


class AudioHandler:
    """
    Manages audio input and output for M.I.C.A.
    """

    def __init__(self, config: Optional[AudioConfig] = None):
        """
        Initialize audio handler.

        Args:
            config: Audio configuration (uses defaults if None)
        """
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        # Apply performance optimizations if enabled
        if config is None:
            config = AudioConfig()

        if perf_flags.is_enabled("optimized_audio_chunks"):
            config.chunk_size = 4096  # Increase from 1024 to 4096
            config.use_double_buffer = True
            logger.info("Optimized audio chunks enabled: 4096-byte chunks with double buffering")
            metrics.start_operation("audio_config_optimized")
            metrics.end_operation(
                "audio_config_optimized", {"chunk_size": 4096, "double_buffer": True}
            )

        self.config = config
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self._input_stream: Optional[sd.InputStream] = None
        self._output_stream: Optional[sd.RawOutputStream] = None
        self._audio_in_queue: Optional[asyncio.Queue] = None
        self._out_queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._muted = False

        # Double buffering queues
        self._buffer_queue_1: Optional[asyncio.Queue] = None
        self._buffer_queue_2: Optional[asyncio.Queue] = None
        self._active_buffer = 1

        logger.info("Audio handler initialized")

    def _ensure_audio_backend(self) -> None:
        """Ensure sounddevice is available."""
        if sd is None:
            raise RuntimeError(
                "sounddevice is not installed. Install dependencies with "
                "'pip install -r requirements.txt'."
            )

    def set_speaking(self, value: bool) -> None:
        """
        Set speaking state.

        Args:
            value: Speaking state
        """
        with self._speaking_lock:
            self._is_speaking = value
        logger.debug(f"Speaking state: {value}")

    def set_muted(self, muted: bool) -> None:
        """
        Set muted state.

        Args:
            muted: Muted state
        """
        self._muted = muted
        logger.debug(f"Muted state: {muted}")

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        with self._speaking_lock:
            return self._is_speaking

    def is_muted(self) -> bool:
        """Check if currently muted."""
        return self._muted

    def get_audio_devices(self) -> dict:
        """
        Get available audio devices.

        Returns:
            Dictionary with input and output devices
        """
        self._ensure_audio_backend()
        devices = sd.query_devices()

        input_devices = []
        output_devices = []

        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                input_devices.append(
                    {"id": i, "name": dev["name"], "channels": dev["max_input_channels"]}
                )
            if dev["max_output_channels"] > 0:
                output_devices.append(
                    {"id": i, "name": dev["name"], "channels": dev["max_output_channels"]}
                )

        return {
            "input": input_devices,
            "output": output_devices,
            "default_input": sd.default.device[0],
            "default_output": sd.default.device[1],
        }

    async def start_listening(
        self,
        audio_in_queue: asyncio.Queue,
        out_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        Start listening to microphone input.

        Args:
            audio_in_queue: Queue for incoming audio data
            out_queue: Queue for outgoing audio data
            loop: Event loop for thread-safe calls
        """
        self._ensure_audio_backend()
        self._audio_in_queue = audio_in_queue
        self._out_queue = out_queue
        self._loop = loop

        # Initialize double buffering if enabled
        if self.config.use_double_buffer:
            self._buffer_queue_1 = asyncio.Queue(maxsize=self.config.buffer_size)
            self._buffer_queue_2 = asyncio.Queue(maxsize=self.config.buffer_size)
            asyncio.create_task(self._double_buffer_processor(out_queue))

        logger.info("Starting microphone listener")
        metrics = get_metrics_collector()
        metrics.start_operation("audio_listening")

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                mica_speaking = self._is_speaking
            if not mica_speaking and not self._muted:
                data = indata.tobytes()

                if self.config.use_double_buffer:
                    # Use double buffering
                    def safe_put_buffer():
                        try:
                            if self._active_buffer == 1:
                                self._buffer_queue_1.put_nowait(
                                    {"data": data, "mime_type": "audio/pcm"}
                                )
                            else:
                                self._buffer_queue_2.put_nowait(
                                    {"data": data, "mime_type": "audio/pcm"}
                                )
                        except Exception:
                            pass

                    loop.call_soon_threadsafe(safe_put_buffer)
                else:
                    # Original single-buffer approach
                    def safe_put():
                        try:
                            out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                        except Exception:
                            pass

                    loop.call_soon_threadsafe(safe_put)

        try:
            with sd.InputStream(
                samplerate=self.config.send_sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=self.config.chunk_size,
                callback=callback,
            ) as stream:
                self._input_stream = stream
                logger.info(f"Microphone stream opened (chunk_size: {self.config.chunk_size})")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Microphone error: {e}")
            metrics.end_operation("audio_listening", {"error": True})
            raise

    async def _double_buffer_processor(self, out_queue: asyncio.Queue) -> None:
        """
        Process audio data from double buffers and send to output queue.
        Alternates between buffers to reduce context switches.
        """
        metrics = get_metrics_collector()
        metrics.start_operation("double_buffer_processor")

        while True:
            try:
                # Switch active buffer
                self._active_buffer = 2 if self._active_buffer == 1 else 1

                # Process from inactive buffer
                source_queue = (
                    self._buffer_queue_1 if self._active_buffer == 2 else self._buffer_queue_2
                )

                # Drain the buffer
                while not source_queue.empty():
                    try:
                        item = source_queue.get_nowait()
                        out_queue.put_nowait(item)
                    except asyncio.QueueEmpty:
                        break

                metrics.end_operation(
                    "double_buffer_processor", {"buffer_switch": self._active_buffer}
                )
                await asyncio.sleep(0.01)  # Small delay to reduce CPU usage
            except Exception as e:
                logger.error(f"Double buffer processor error: {e}")
                await asyncio.sleep(0.1)

    async def start_playback(self, audio_in_queue: asyncio.Queue) -> None:
        """
        Start audio playback.

        Args:
            audio_in_queue: Queue with audio data to play
        """
        self._ensure_audio_backend()
        self._audio_in_queue = audio_in_queue

        logger.info("Starting audio playback")

        stream = sd.RawOutputStream(
            samplerate=self.config.receive_sample_rate,
            channels=self.config.channels,
            dtype=self.config.dtype,
            blocksize=self.config.chunk_size,
        )
        stream.start()
        self._output_stream = stream

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(audio_in_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def send_realtime(self, out_queue: asyncio.Queue, session) -> None:
        """
        Send realtime audio data to session.

        Args:
            out_queue: Queue with audio data to send
            session: Gemini Live session
        """
        while True:
            msg = await out_queue.get()
            await session.send_realtime_input(media=msg)

    def stop(self) -> None:
        """Stop all audio streams."""
        logger.info("Stopping audio handler")

        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception as e:
                logger.error(f"Error stopping input stream: {e}")

        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception as e:
                logger.error(f"Error stopping output stream: {e}")

        self._input_stream = None
        self._output_stream = None
