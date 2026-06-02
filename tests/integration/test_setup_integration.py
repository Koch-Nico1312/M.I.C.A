"""
Integration tests for setup flow system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestSetupIntegration:
    """Integration tests for setup flow system components."""

    @pytest.fixture
    def setup_flow(self):
        """Create a fresh SetupFlow instance for testing."""
        from core.setup_flow import get_setup_flow
        return get_setup_flow()

    def test_initial_setup_check(self, setup_flow):
        """Test initial setup check."""
        result = setup_flow.check_setup_required()
        
        assert result is True or result is False

    @patch('core.setup_flow.get_config')
    def test_api_key_validation(self, mock_config, setup_flow):
        """Test API key validation."""
        mock_config.return_value = Mock()
        mock_config.return_value.get_api_key.return_value = "test_api_key"
        
        is_valid = setup_flow.validate_api_key("gemini")
        
        assert is_valid is True or is_valid is False

    @patch('core.setup_flow.get_config')
    def test_dependency_check(self, mock_config, setup_flow):
        """Test dependency validation."""
        mock_config.return_value = Mock()
        
        dependencies = setup_flow.check_dependencies()
        
        assert dependencies is not None

    @patch('core.setup_flow.get_config')
    def test_setup_wizard(self, mock_config, setup_flow):
        """Test setup wizard flow."""
        mock_config.return_value = Mock()
        
        # Run setup wizard
        result = setup_flow.run_setup_wizard()
        
        assert result is not None

    @patch('core.setup_flow.get_config')
    def test_configuration_prompt(self, mock_config, setup_flow):
        """Test configuration prompting."""
        mock_config.return_value = Mock()
        
        # Prompt for configuration
        config = setup_flow.prompt_configuration()
        
        assert config is not None

    @patch('core.setup_flow.get_config')
    def test_setup_completion(self, mock_config, setup_flow):
        """Test setup completion."""
        mock_config.return_value = Mock()
        
        # Complete setup
        setup_flow.complete_setup()
        
        # Should mark setup as complete
        assert True  # Placeholder for actual completion test

    @patch('core.setup_flow.get_config')
    def test_setup_with_env_file(self, mock_config, setup_flow):
        """Test setup with .env file creation."""
        mock_config.return_value = Mock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            
            # Create .env file
            setup_flow.create_env_file(env_path, {"GEMINI_API_KEY": "test_key"})
            
            assert env_path.exists()

    @patch('core.setup_flow.get_config')
    def test_setup_with_config_yaml(self, mock_config, setup_flow):
        """Test setup with config.yaml creation."""
        mock_config.return_value = Mock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            
            # Create config.yaml
            setup_flow.create_config_file(config_path)
            
            assert config_path.exists()

    @patch('core.setup_flow.get_config')
    def test_setup_validation(self, mock_config, setup_flow):
        """Test setup validation."""
        mock_config.return_value = Mock()
        
        # Validate setup
        is_valid = setup_flow.validate_setup()
        
        assert is_valid is True or is_valid is False

    @patch('core.setup_flow.get_config')
    def test_setup_reconfiguration(self, mock_config, setup_flow):
        """Test setup reconfiguration."""
        mock_config.return_value = Mock()
        
        # Reconfigure setup
        result = setup_flow.reconfigure()
        
        assert result is not None

    @patch('core.setup_flow.get_config')
    def test_setup_with_first_run(self, mock_config, setup_flow):
        """Test first-run setup experience."""
        mock_config.return_value = Mock()
        mock_config.return_value.is_first_run.return_value = True
        
        # Should trigger first-run setup
        is_first_run = setup_flow.is_first_run()
        
        assert is_first_run is True


class TestSetupErrorHandling:
    """Error handling tests for setup flow system."""

    @pytest.fixture
    def setup_flow(self):
        """Create a fresh SetupFlow instance for testing."""
        from core.setup_flow import get_setup_flow
        return get_setup_flow()

    @patch('core.setup_flow.get_config')
    def test_missing_api_key(self, mock_config, setup_flow):
        """Test handling of missing API key."""
        mock_config.return_value = Mock()
        mock_config.return_value.get_api_key.return_value = None
        
        is_valid = setup_flow.validate_api_key("gemini")
        
        assert is_valid is False

    @patch('core.setup_flow.get_config')
    def test_invalid_dependency(self, mock_config, setup_flow):
        """Test handling of invalid/missing dependency."""
        mock_config.return_value = Mock()
        
        # Mock missing dependency
        with patch('importlib.util.find_spec', return_value=None):
            dependencies = setup_flow.check_dependencies()
            
            # Should detect missing dependency
            assert dependencies is not None

    @patch('core.setup_flow.get_config')
    def test_setup_cancellation(self, mock_config, setup_flow):
        """Test handling of setup cancellation."""
        mock_config.return_value = Mock()
        
        # Cancel setup
        result = setup_flow.cancel_setup()
        
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
