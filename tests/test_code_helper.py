"""
Tests for actions.code_helper module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestCodeHelper:
    """Test cases for code_helper action."""

    @pytest.fixture
    def code_helper(self):
        """Create a fresh code_helper instance for testing."""
        from actions.code_helper import code_helper
        return code_helper

    def test_generate_code(self, code_helper):
        """Test generating code."""
        result = code_helper.generate(
            language="python",
            description="Create a function that adds two numbers"
        )
        
        assert result is not None
        assert isinstance(result, str)

    def test_explain_code(self, code_helper):
        """Test explaining code."""
        code = "def add(a, b):\n    return a + b"
        
        result = code_helper.explain(code)
        
        assert result is not None
        assert isinstance(result, str)

    def test_debug_code(self, code_helper):
        """Test debugging code."""
        code = "def add(a, b):\n    return a + b"
        
        result = code_helper.debug(code, error="NameError: name 'a' is not defined")
        
        assert result is not None

    def test_optimize_code(self, code_helper):
        """Test optimizing code."""
        code = "def add_numbers(a, b, c, d):\n    return a + b + c + d"
        
        result = code_helper.optimize(code)
        
        assert result is not None

    def test_format_code(self, code_helper):
        """Test formatting code."""
        code = "def add(a,b):return a+b"
        
        result = code_helper.format(code, language="python")
        
        assert result is not None

    def test_add_comments(self, code_helper):
        """Test adding comments to code."""
        code = "def add(a, b):\n    return a + b"
        
        result = code_helper.add_comments(code)
        
        assert result is not None

    def test_refactor_code(self, code_helper):
        """Test refactoring code."""
        code = "def calculate(x, y, z):\n    result = x + y\n    result = result * z\n    return result"
        
        result = code_helper.refactor(code)
        
        assert result is not None

    def test_convert_language(self, code_helper):
        """Test converting code between languages."""
        code = "def add(a, b):\n    return a + b"
        
        result = code_helper.convert(code, from_lang="python", to_lang="javascript")
        
        assert result is not None

    def test_write_to_file(self, code_helper):
        """Test writing code to a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            code = "def hello():\n    print('Hello World')"
            result = code_helper.write_to_file(str(temp_path), code)
            
            assert result is not None
            assert temp_path.read_text() == code
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestCodeHelperErrorHandling:
    """Test error handling in code_helper."""

    @pytest.fixture
    def code_helper(self):
        """Create a fresh code_helper instance for testing."""
        from actions.code_helper import code_helper
        return code_helper

    def test_empty_code(self, code_helper):
        """Test handling of empty code."""
        with pytest.raises(ValueError):
            code_helper.explain("")

    def test_invalid_language(self, code_helper):
        """Test handling of invalid language."""
        with pytest.raises(ValueError):
            code_helper.generate(language="invalid_lang", description="Test")

    def test_write_to_invalid_path(self, code_helper):
        """Test writing to invalid path."""
        with pytest.raises((ValueError, OSError)):
            code_helper.write_to_file("/invalid/path/file.py", "code")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
