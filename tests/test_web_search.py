"""
Tests for actions.web_search module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestWebSearch:
    """Test cases for web_search action."""

    @pytest.fixture
    def web_search(self):
        """Create a fresh web_search instance for testing."""
        from actions.web_search import web_search_action
        return web_search_action

    @patch('actions.web_search.DDGS')
    def test_search_query(self, mock_ddgs, web_search):
        """Test performing a web search."""
        mock_results = [
            {"title": "Result 1", "body": "Description 1", "href": "https://example.com/1"},
            {"title": "Result 2", "body": "Description 2", "href": "https://example.com/2"}
        ]
        mock_ddgs.return_value.__enter__.return_value.text.return_value = mock_results
        
        result = web_search("test query")
        
        assert result is not None
        assert len(result) >= 2

    @patch('actions.web_search.DDGS')
    def test_search_with_limit(self, mock_ddgs, web_search):
        """Test search with result limit."""
        mock_results = [
            {"title": f"Result {i}", "body": f"Description {i}", "href": f"https://example.com/{i}"}
            for i in range(10)
        ]
        mock_ddgs.return_value.__enter__.return_value.text.return_value = mock_results
        
        result = web_search("test query", max_results=5)
        
        assert result is not None
        assert len(result) <= 5

    @patch('actions.web_search.DDGS')
    def test_search_with_region(self, mock_ddgs, web_search):
        """Test search with region specification."""
        mock_results = [{"title": "Result", "body": "Description", "href": "https://example.com"}]
        mock_ddgs.return_value.__enter__.return_value.text.return_value = mock_results
        
        result = web_search("test query", region="de-de")
        
        assert result is not None

    @patch('actions.web_search.DDGS')
    def test_search_with_time(self, mock_ddgs, web_search):
        """Test search with time filter."""
        mock_results = [{"title": "Result", "body": "Description", "href": "https://example.com"}]
        mock_ddgs.return_value.__enter__.return_value.text.return_value = mock_results
        
        result = web_search("test query", time="d")  # Last day
        
        assert result is not None

    @patch('actions.web_search.DDGS')
    def test_empty_query(self, mock_ddgs, web_search):
        """Test handling of empty query."""
        with pytest.raises(ValueError):
            web_search("")

    @patch('actions.web_search.DDGS')
    def test_search_with_safesearch(self, mock_ddgs, web_search):
        """Test search with safe search enabled."""
        mock_results = [{"title": "Result", "body": "Description", "href": "https://example.com"}]
        mock_ddgs.return_value.__enter__.return_value.text.return_value = mock_results
        
        result = web_search("test query", safesearch="moderate")
        
        assert result is not None


class TestWebSearchErrorHandling:
    """Test error handling in web_search."""

    @pytest.fixture
    def web_search(self):
        """Create a fresh web_search instance for testing."""
        from actions.web_search import web_search_action
        return web_search

    @patch('actions.web_search.DDGS', side_effect=Exception("Search error"))
    def test_search_error_handling(self, mock_ddgs, web_search):
        """Test error handling when search fails."""
        with pytest.raises(Exception):
            web_search("test query")

    @patch('actions.web_search.DDGS')
    def test_no_results(self, mock_ddgs, web_search):
        """Test handling of no search results."""
        mock_ddgs.return_value.__enter__.return_value.text.return_value = []
        
        result = web_search("test query")
        
        assert result == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
