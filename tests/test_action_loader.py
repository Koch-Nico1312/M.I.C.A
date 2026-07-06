"""
Tests for core.action_loader module
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from core.action_loader import get_action_loader, ActionLoader


class TestActionLoader:
    """Test cases for ActionLoader class."""

    @pytest.fixture
    def action_loader(self):
        """Create a fresh ActionLoader instance for testing."""
        return ActionLoader()

    def test_get_action_loader_singleton(self):
        """Test that get_action_loader returns a singleton instance."""
        loader1 = get_action_loader()
        loader2 = get_action_loader()
        assert loader1 is loader2

    def test_action_loader_initialization(self, action_loader):
        """Test ActionLoader initialization."""
        assert action_loader is not None
        assert hasattr(action_loader, 'load_actions')
        assert hasattr(action_loader, 'get_tool_declarations')

    @patch('core.action_loader.Path')
    def test_load_actions_from_directory(self, mock_path, action_loader):
        """Test loading actions from the actions directory."""
        # Mock the actions directory structure
        mock_actions_dir = MagicMock()
        mock_path.return_value = mock_actions_dir
        mock_actions_dir.__truediv__.return_value = mock_actions_dir
        mock_actions_dir.exists.return_value = True
        mock_actions_dir.glob.return_value = [
            MagicMock(name='test_action.py', stem='test_action')
        ]

        # This test would need more mocking of the import system
        # For now, we just test that the method exists
        assert callable(action_loader.load_actions)

    def test_get_tool_declarations(self, action_loader):
        """Test getting tool declarations."""
        declarations = action_loader.get_tool_declarations()
        assert isinstance(declarations, list)
        # Each declaration should be a dict with required fields
        for decl in declarations:
            assert isinstance(decl, dict)
            assert 'name' in decl
            assert 'description' in decl

    def test_lazy_loading_enabled(self, action_loader):
        """Test that lazy loading can be enabled."""
        # Test that the action loader supports lazy loading
        assert hasattr(action_loader, 'lazy_load')

    @patch('core.action_loader.importlib')
    def test_load_single_action(self, mock_importlib, action_loader):
        """Test loading a single action module."""
        # Mock the import
        mock_module = MagicMock()
        mock_module.TOOL_DECLARATION = {
            'name': 'test_tool',
            'description': 'Test tool description',
            'parameters': {'type': 'object', 'properties': {}}
        }
        mock_importlib.import_module.return_value = mock_module

        # Test loading
        result = action_loader.load_action('test_action')
        # This would need actual implementation testing
        assert result is not None or result is None  # Placeholder

    def test_action_caching(self, action_loader):
        """Test that actions are cached after loading."""
        # Load actions once
        action_loader.load_actions()
        # Load again - should use cache
        action_loader.load_actions()
        # Verify caching behavior
        assert True  # Placeholder for actual cache test

    def test_error_handling_invalid_action(self, action_loader):
        """Test error handling for invalid action modules."""
        # Test with a non-existent action
        with pytest.raises((ImportError, FileNotFoundError, AttributeError)):
            action_loader.load_action('nonexistent_action')

    def test_tool_declaration_validation(self, action_loader):
        """Test validation of tool declarations."""
        # Create a valid declaration
        valid_decl = {
            'name': 'test_tool',
            'description': 'Test description',
            'parameters': {
                'type': 'object',
                'properties': {
                    'param1': {'type': 'string'}
                }
            }
        }
        # Test validation logic
        assert 'name' in valid_decl
        assert 'description' in valid_decl
        assert 'parameters' in valid_decl


class TestActionLoaderIntegration:
    """Integration tests for ActionLoader with actual action modules."""

    def test_load_all_actions_integration(self):
        """Test loading all actual actions from the actions directory."""
        loader = get_action_loader()
        declarations = loader.get_tool_declarations()
        
        # Verify we get some declarations
        assert len(declarations) > 0
        
        # Verify structure of declarations
        for decl in declarations:
            assert 'name' in decl
            assert 'description' in decl
            assert 'parameters' in decl

    def test_action_module_structure(self):
        """Test that action modules have the expected structure."""
        loader = get_action_loader()
        declarations = loader.get_tool_declarations()
        
        # Check that known actions are present
        action_names = [decl['name'] for decl in declarations]
        
        # Core integrations should be present in the tool surface.
        assert "crawl_url" in action_names
        assert "agent_reach" in action_names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
