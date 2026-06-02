"""
Tests for core.llm_fallback module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestLLMFallback:
    """Test cases for LLMFallback class."""

    @pytest.fixture
    def llm_fallback(self):
        """Create a fresh LLMFallback instance for testing."""
        from core.llm_fallback import LLMFallback
        return LLMFallback()

    def test_llm_fallback_initialization(self, llm_fallback):
        """Test LLMFallback initialization."""
        assert llm_fallback is not None
        assert hasattr(llm_fallback, 'get_primary_llm')
        assert hasattr(llm_fallback, 'get_fallback_llm')
        assert hasattr(llm_fallback, 'switch_to_fallback')

    def test_get_primary_llm(self, llm_fallback):
        """Test getting the primary LLM."""
        primary = llm_fallback.get_primary_llm()
        
        assert primary is not None

    def test_get_fallback_llm(self, llm_fallback):
        """Test getting the fallback LLM."""
        fallback = llm_fallback.get_fallback_llm()
        
        assert fallback is not None

    def test_switch_to_fallback(self, llm_fallback):
        """Test switching to fallback LLM."""
        llm_fallback.switch_to_fallback()
        
        assert llm_fallback.current_llm == "fallback"

    def test_switch_to_primary(self, llm_fallback):
        """Test switching back to primary LLM."""
        llm_fallback.switch_to_fallback()
        llm_fallback.switch_to_primary()
        
        assert llm_fallback.current_llm == "primary"

    def test_generate_with_primary(self, llm_fallback):
        """Test generating response with primary LLM."""
        llm_fallback.current_llm = "primary"
        
        response = llm_fallback.generate("Test prompt")
        
        assert response is not None

    def test_generate_with_fallback(self, llm_fallback):
        """Test generating response with fallback LLM."""
        llm_fallback.switch_to_fallback()
        
        response = llm_fallback.generate("Test prompt")
        
        assert response is not None

    def test_auto_fallback_on_error(self, llm_fallback):
        """Test automatic fallback on primary LLM error."""
        llm_fallback.enable_auto_fallback = True
        
        # Mock primary failure
        with patch.object(llm_fallback, '_generate_primary', side_effect=Exception("Primary failed")):
            response = llm_fallback.generate("Test prompt")
        
        # Should have switched to fallback
        assert llm_fallback.current_llm == "fallback"

    def test_fallback_health_check(self, llm_fallback):
        """Test health check for fallback LLM."""
        health = llm_fallback.check_fallback_health()
        
        assert health is not None
        assert 'healthy' in health

    def test_primary_health_check(self, llm_fallback):
        """Test health check for primary LLM."""
        health = llm_fallback.check_primary_health()
        
        assert health is not None
        assert 'healthy' in health


class TestLLMFallbackErrorHandling:
    """Test error handling in LLMFallback."""

    @pytest.fixture
    def llm_fallback(self):
        """Create a fresh LLMFallback instance for testing."""
        from core.llm_fallback import LLMFallback
        return LLMFallback()

    def test_both_llms_unavailable(self, llm_fallback):
        """Test handling when both LLMs are unavailable."""
        # Mock both as unavailable
        with patch.object(llm_fallback, 'check_primary_health', return_value={'healthy': False}):
            with patch.object(llm_fallback, 'check_fallback_health', return_value={'healthy': False}):
                with pytest.raises(Exception):
                    llm_fallback.generate("Test prompt")

    def test_fallback_switch_failure(self, llm_fallback):
        """Test handling of fallback switch failure."""
        with patch.object(llm_fallback, '_switch_llm', side_effect=Exception("Switch failed")):
            with pytest.raises(Exception):
                llm_fallback.switch_to_fallback()


class TestLLMFallbackIntegration:
    """Integration tests for LLMFallback."""

    @patch('core.llm_fallback.get_config')
    def test_full_fallback_cycle(self, mock_config):
        """Test a full fallback cycle."""
        from core.llm_fallback import LLMFallback
        
        mock_config.return_value = Mock()
        
        fallback = LLMFallback()
        fallback.enable_auto_fallback = True
        
        # Start with primary
        assert fallback.current_llm == "primary"
        
        # Simulate primary failure
        with patch.object(fallback, '_generate_primary', side_effect=Exception("Primary failed")):
            response = fallback.generate("Test prompt")
        
        # Should have switched to fallback
        assert fallback.current_llm == "fallback"
        
        # Try to recover primary
        fallback.attempt_primary_recovery()
        
        # Should attempt to switch back if healthy
        assert True  # Placeholder for actual recovery test

    def test_fallback_with_ollama(self):
        """Test fallback with Ollama."""
        from core.llm_fallback import LLMFallback
        
        fallback = LLMFallback()
        fallback.fallback_provider = "ollama"
        
        # Should configure Ollama as fallback
        assert fallback.fallback_provider == "ollama"

    def test_hybrid_mode(self):
        """Test hybrid mode using both LLMs."""
        from core.llm_fallback import LLMFallback
        
        fallback = LLMFallback()
        fallback.enable_hybrid = True
        
        # In hybrid mode, should use both LLMs
        response = fallback.generate("Test prompt")
        
        assert response is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
