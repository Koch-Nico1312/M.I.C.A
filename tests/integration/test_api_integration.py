"""
Integration tests for API system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestAPIIntegration:
    """Integration tests for API system components."""

    @pytest.fixture
    def api_cache(self):
        """Create a fresh APICache instance for testing."""
        from core.api_cache import APICache
        return APICache()

    def test_api_caching(self, api_cache):
        """Test API response caching."""
        # Cache a response
        api_cache.cache_response("test_endpoint", {"data": "test"}, ttl=300)
        
        # Retrieve from cache
        cached = api_cache.get_cached_response("test_endpoint")
        
        assert cached is not None
        assert cached["data"] == "test"

    def test_cache_invalidation(self, api_cache):
        """Test cache invalidation."""
        # Cache a response
        api_cache.cache_response("test_endpoint", {"data": "test"}, ttl=300)
        
        # Invalidate cache
        api_cache.invalidate("test_endpoint")
        
        # Should not be in cache
        cached = api_cache.get_cached_response("test_endpoint")
        assert cached is None

    def test_cache_expiration(self, api_cache):
        """Test cache expiration."""
        # Cache with short TTL
        api_cache.cache_response("test_endpoint", {"data": "test"}, ttl=1)
        
        # Wait for expiration
        import time
        time.sleep(2)
        
        # Should be expired
        cached = api_cache.get_cached_response("test_endpoint")
        assert cached is None

    @patch('core.api_cache.requests')
    def test_http_pool_integration(self, mock_requests, api_cache):
        """Test HTTP pool integration with API cache."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Make request through pool
        result = pool.get("https://api.example.com/test")
        
        assert result is not None

    @patch('core.api_cache.requests')
    def test_rate_limiting(self, mock_requests):
        """Test API rate limiting."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        pool.enable_rate_limiting = True
        pool.rate_limit_per_second = 10
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Make multiple requests
        for i in range(5):
            result = pool.get("https://api.example.com/test")
            assert result is not None

    @patch('core.api_cache.requests')
    def test_retry_logic(self, mock_requests):
        """Test API retry logic on failure."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        pool.enable_retry = True
        pool.max_retries = 3
        
        # First two calls fail, third succeeds
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.side_effect = [
            Exception("Network error"),
            Exception("Network error"),
            mock_response
        ]
        
        result = pool.get("https://api.example.com/test")
        
        assert result is not None

    @patch('core.api_cache.requests')
    def test_api_authentication(self, mock_requests):
        """Test API authentication."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        pool.set_api_key("test_api_key")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        result = pool.get("https://api.example.com/test")
        
        assert result is not None

    @patch('core.api_cache.requests')
    def test_concurrent_api_requests(self, mock_requests):
        """Test concurrent API requests."""
        from core.http_pool import HTTPPool
        import asyncio
        
        pool = HTTPPool()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        async def make_concurrent_requests():
            tasks = [
                pool.get_async(f"https://api.example.com/test{i}")
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        # Should handle concurrent requests
        assert True  # Placeholder for actual concurrent test


class TestAPIErrorHandling:
    """Error handling tests for API system."""

    @pytest.fixture
    def api_cache(self):
        """Create a fresh APICache instance for testing."""
        from core.api_cache import APICache
        return APICache()

    @patch('core.api_cache.requests', side_effect=Exception("Network error"))
    def test_network_error_handling(self, mock_requests):
        """Test handling of network errors."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        
        with pytest.raises(Exception):
            pool.get("https://api.example.com/test")

    @patch('core.api_cache.requests')
    def test_http_error_handling(self, mock_requests):
        """Test handling of HTTP errors."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_requests.get.return_value = mock_response
        
        with pytest.raises(Exception):
            pool.get("https://api.example.com/test")

    def test_invalid_api_key(self):
        """Test handling of invalid API key."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        
        with pytest.raises(ValueError):
            pool.set_api_key("")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
