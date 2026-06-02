"""
Performance benchmarks for LLM operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestLLMGenerationPerformance:
    """Performance benchmarks for LLM generation."""

    @pytest.fixture
    def llm(self):
        """Create a fresh LLM instance for benchmarking."""
        from core.llm_fallback import LLMFallback
        return LLMFallback()

    def test_short_prompt_performance(self, llm, benchmark):
        """Benchmark short prompt generation."""
        llm._generate_primary = Mock(return_value="Short response")
        
        def generate_short():
            return llm.generate("Hi")
        
        result = benchmark(generate_short)
        assert result is not None

    def test_long_prompt_performance(self, llm, benchmark):
        """Benchmark long prompt generation."""
        llm._generate_primary = Mock(return_value="Long response")
        long_prompt = "This is a very long prompt " * 100
        
        def generate_long():
            return llm.generate(long_prompt)
        
        result = benchmark(generate_long)
        assert result is not None

    def test_multiturn_conversation_performance(self, llm, benchmark):
        """Benchmark multi-turn conversation."""
        llm._generate_primary = Mock(return_value="Response")
        
        def multi_turn():
            for i in range(10):
                llm.generate(f"Message {i}")
            return True
        
        result = benchmark(multi_turn)
        assert result is True


class TestStreamingPerformance:
    """Performance benchmarks for response streaming."""

    @pytest.fixture
    def streamer(self):
        """Create a fresh ResponseStreamer instance for benchmarking."""
        from core.response_streamer import ResponseStreamer
        return ResponseStreamer()

    def test_streaming_performance(self, streamer, benchmark):
        """Benchmark streaming response."""
        long_text = "This is a long response " * 100
        
        def stream():
            return list(streamer.stream_response(long_text))
        
        result = benchmark(stream)
        assert result is not None

    def test_chunk_size_performance(self, streamer, benchmark):
        """Benchmark different chunk sizes."""
        long_text = "This is a long response " * 100
        streamer.chunk_size = 50
        
        def stream_with_chunks():
            return list(streamer.stream_response(long_text))
        
        result = benchmark(stream_with_chunks)
        assert result is not None


class TestContextManagementPerformance:
    """Performance benchmarks for context management."""

    @pytest.fixture
    def multimodal_context(self):
        """Create a fresh MultimodalContext instance for benchmarking."""
        from core.multimodal_context import MultimodalContext
        return MultimodalContext()

    def test_large_context_performance(self, multimodal_context, benchmark):
        """Benchmark handling large context."""
        # Add many context items
        for i in range(100):
            multimodal_context.add_text(f"Context item {i}")
        
        def get_large_context():
            return multimodal_context.get_context()
        
        result = benchmark(get_large_context)
        assert result is not None

    def test_context_with_images_performance(self, multimodal_context, benchmark):
        """Benchmark context with images."""
        import numpy as np
        
        # Add images
        for i in range(10):
            image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            multimodal_context.add_image(image, description=f"Image {i}")
        
        def get_image_context():
            return multimodal_context.get_context()
        
        result = benchmark(get_image_context)
        assert result is not None


class TestToolExecutionPerformance:
    """Performance benchmarks for tool execution."""

    @pytest.fixture
    def tool_executor(self):
        """Create a fresh ToolExecutor instance for benchmarking."""
        from core.tool_executor import ToolExecutor
        return ToolExecutor()

    def test_single_tool_execution_performance(self, tool_executor, benchmark):
        """Benchmark single tool execution."""
        def test_tool():
            return "result"
        
        tool_executor.register_tool("test_tool", test_tool, "Test", {})
        
        def execute_tool():
            return tool_executor.execute_tool("test_tool", {})
        
        result = benchmark(execute_tool)
        assert result is not None

    def test_parallel_tool_execution_performance(self, tool_executor, benchmark):
        """Benchmark parallel tool execution."""
        import asyncio
        
        def tool1():
            return "result1"
        
        def tool2():
            return "result2"
        
        tool_executor.register_tool("tool1", tool1, "Tool 1", {})
        tool_executor.register_tool("tool2", tool2, "Tool 2", {})
        
        async def execute_parallel():
            results = await asyncio.gather(
                tool_executor.execute_tool_async("tool1", {}),
                tool_executor.execute_tool_async("tool2", {})
            )
            return results
        
        result = benchmark(asyncio.run, execute_parallel())
        assert result is not None


class TestAPICachingPerformance:
    """Performance benchmarks for API caching."""

    @pytest.fixture
    def api_cache(self):
        """Create a fresh APICache instance for benchmarking."""
        from core.api_cache import APICache
        return APICache()

    def test_cache_hit_performance(self, api_cache, benchmark):
        """Benchmark cache hit performance."""
        api_cache.cache_response("test_endpoint", {"data": "test"}, ttl=300)
        
        def cache_hit():
            return api_cache.get_cached_response("test_endpoint")
        
        result = benchmark(cache_hit)
        assert result is not None

    def test_cache_miss_performance(self, api_cache, benchmark):
        """Benchmark cache miss performance."""
        def cache_miss():
            return api_cache.get_cached_response("nonexistent_endpoint")
        
        result = benchmark(cache_miss)
        assert result is None

    def test_batch_cache_operations_performance(self, api_cache, benchmark):
        """Benchmark batch cache operations."""
        def batch_cache():
            for i in range(100):
                api_cache.cache_response(f"endpoint{i}", {"data": f"value{i}"}, ttl=300)
            return True
        
        result = benchmark(batch_cache)
        assert result is not None


class TestFallbackPerformance:
    """Performance benchmarks for fallback mechanisms."""

    @pytest.fixture
    def fallback(self):
        """Create a fresh LLMFallback instance for benchmarking."""
        from core.llm_fallback import LLMFallback
        return LLMFallback()

    def test_fallback_switch_performance(self, fallback, benchmark):
        """Benchmark fallback switch performance."""
        def switch_fallback():
            fallback.switch_to_fallback()
            fallback.switch_to_primary()
            return True
        
        result = benchmark(switch_fallback)
        assert result is not None

    def test_health_check_performance(self, fallback, benchmark):
        """Benchmark health check performance."""
        def health_check():
            return fallback.check_primary_health()
        
        result = benchmark(health_check)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
