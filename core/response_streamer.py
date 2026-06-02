"""
Response Streamer for JARVIS AI Assistant
=========================================
Provides streaming response generation for reduced perceived latency.
"""

import asyncio
import threading
from queue import Queue
from typing import AsyncGenerator, Callable, Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

logger = get_logger(__name__)


class ResponseStreamer:
    """
    Streams responses token by token for reduced perceived latency.
    """

    def __init__(self, chunk_size: int = 10):
        """
        Initialize the response streamer.

        Args:
            chunk_size: Number of tokens to yield per chunk
        """
        self.chunk_size = chunk_size
        self._lock = threading.Lock()
        logger.info(f"Response streamer initialized (chunk_size: {chunk_size})")

    async def stream_text(
        self, text: str, callback: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream text in chunks.

        Args:
            text: Full text to stream
            callback: Optional callback for each chunk

        Yields:
            Text chunks
        """
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        if not perf_flags.is_enabled("response_streaming"):
            # Return full text if streaming is disabled
            yield text
            return

        metrics.start_operation("response_streaming")

        # Split text into chunks
        chunks = []
        for i in range(0, len(text), self.chunk_size):
            chunk = text[i : i + self.chunk_size]
            chunks.append(chunk)

        # Stream chunks
        for i, chunk in enumerate(chunks):
            # Simulate token generation delay (small delay for realism)
            await asyncio.sleep(0.01)

            # Call callback if provided
            if callback:
                callback(chunk)

            metrics.record_custom("stream_chunk", 1)
            yield chunk

        metrics.end_operation(
            "response_streaming", {"total_chunks": len(chunks), "total_length": len(text)}
        )

    async def stream_tokens(
        self, tokens: list, callback: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens one by one.

        Args:
            tokens: List of tokens to stream
            callback: Optional callback for each token

        Yields:
            Tokens
        """
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        if not perf_flags.is_enabled("response_streaming"):
            # Return all tokens at once if streaming is disabled
            yield " ".join(tokens)
            return

        metrics.start_operation("response_token_streaming")

        # Stream tokens
        for i, token in enumerate(tokens):
            # Simulate token generation delay
            await asyncio.sleep(0.005)

            # Call callback if provided
            if callback:
                callback(token)

            metrics.record_custom("stream_token", 1)
            yield token

        metrics.end_operation("response_token_streaming", {"total_tokens": len(tokens)})

    def get_stream_stats(self) -> dict:
        """
        Get streaming statistics.

        Returns:
            Dictionary with streaming statistics
        """
        metrics = get_metrics_collector()
        return {
            "chunk_size": self.chunk_size,
            "streaming_enabled": get_performance_flags().is_enabled("response_streaming"),
            "chunks_streamed": metrics.get_custom_metric("stream_chunk", 0),
            "tokens_streamed": metrics.get_custom_metric("stream_token", 0),
        }


# Global instance
_response_streamer: Optional[ResponseStreamer] = None
_response_streamer_lock = threading.Lock()


def get_response_streamer() -> ResponseStreamer:
    """
    Get the global response streamer instance.

    Returns:
        ResponseStreamer instance
    """
    global _response_streamer
    if _response_streamer is None:
        with _response_streamer_lock:
            if _response_streamer is None:
                _response_streamer = ResponseStreamer()
    return _response_streamer
