"""
Tests for actions.dev_agent module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestDevAgent:
    """Test cases for dev_agent action."""

    @pytest.fixture
    def dev_agent(self):
        """Create a fresh dev_agent instance for testing."""
        from actions.dev_agent import dev_agent
        return dev_agent

    def test_generate_code(self, dev_agent):
        """Test generating code."""
        result = dev_agent.generate(
            description="Create a function that adds two numbers",
            language="python"
        )
        
        assert result is not None
        assert isinstance(result, str)

    def test_refactor_code(self, dev_agent):
        """Test refactoring code."""
        code = "def add(a,b):return a+b"
        
        result = dev_agent.refactor(code)
        
        assert result is not None

    def test_debug_code(self, dev_agent):
        """Test debugging code."""
        code = "def add(a,b):return a+b"
        error = "NameError: name 'a' is not defined"
        
        result = dev_agent.debug(code, error)
        
        assert result is not None

    def test_explain_code(self, dev_agent):
        """Test explaining code."""
        code = "def add(a, b):\n    return a + b"
        
        result = dev_agent.explain(code)
        
        assert result is not None

    def test_write_to_file(self, dev_agent):
        """Test writing code to a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            code = "def hello():\n    print('Hello World')"
            result = dev_agent.write_to_file(str(temp_path), code)
            
            assert result is not None
            assert temp_path.read_text() == code
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_analyze_project(self, dev_agent):
        """Test analyzing a project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "main.py").write_text("print('hello')")
            (temp_path / "utils.py").write_text("def helper(): pass")
            
            result = dev_agent.analyze_project(str(temp_path))
            
            assert result is not None

    def test_suggest_improvements(self, dev_agent):
        """Test suggesting code improvements."""
        code = "def add(a,b):return a+b"
        
        result = dev_agent.suggest_improvements(code)
        
        assert result is not None

    def test_add_tests(self, dev_agent):
        """Test generating tests for code."""
        code = "def add(a, b):\n    return a + b"
        
        result = dev_agent.generate_tests(code)
        
        assert result is not None


class TestDevAgentErrorHandling:
    """Test error handling in dev_agent."""

    @pytest.fixture
    def dev_agent(self):
        """Create a fresh dev_agent instance for testing."""
        from actions.dev_agent import dev_agent
        return dev_agent

    def test_empty_code(self, dev_agent):
        """Test handling of empty code."""
        with pytest.raises(ValueError):
            dev_agent.explain("")

    def test_empty_description(self, dev_agent):
        """Test handling of empty description."""
        with pytest.raises(ValueError):
            dev_agent.generate("", "python")

    def test_invalid_language(self, dev_agent):
        """Test handling of invalid language."""
        with pytest.raises(ValueError):
            dev_agent.generate("Test", "invalid_lang")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
