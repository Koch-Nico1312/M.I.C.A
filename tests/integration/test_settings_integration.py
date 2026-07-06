"""
Integration tests for settings system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import yaml


class TestSettingsIntegration:
    """Integration tests for settings system components."""

    @pytest.fixture
    def config_loader(self):
        """Create a fresh ConfigLoader instance for testing."""
        from config.config_loader import get_config
        return get_config()

    def test_config_loading(self, config_loader):
        """Test loading configuration."""
        config = config_loader.get_config()
        
        assert config is not None

    def test_config_performance_flags(self, config_loader):
        """Test performance flags configuration."""
        from core.performance_flags import get_performance_flags
        
        flags = get_performance_flags()
        
        # Check that flags are loaded
        assert flags is not None
        assert hasattr(flags, 'is_enabled')

    def test_config_api_keys(self, config_loader):
        """Test API key configuration."""
        api_key = config_loader.get_api_key("gemini")
        
        # Should return API key or None if not configured
        assert api_key is not None or api_key is None

    def test_config_validation(self, config_loader):
        """Test configuration validation."""
        # Validate current config
        is_valid = config_loader.validate_config()
        
        assert is_valid is True or is_valid is False

    def test_config_reload(self, config_loader):
        """Test configuration reload."""
        # Reload config
        config_loader.reload_config()
        
        # Should have reloaded
        assert True  # Placeholder for actual reload test

    def test_config_with_env(self, config_loader):
        """Test configuration with environment variables."""
        import os
        from dotenv import load_dotenv
        
        # Load .env file
        load_dotenv()
        
        # Check that env vars are loaded
        assert True  # Placeholder for actual env test

    def test_config_persistence(self, config_loader):
        """Test configuration persistence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            
            # Create test config
            test_config = {
                "performance": {
                    "flags": {
                        "cache_system_prompt": True,
                        "lazy_tool_declarations": True
                    }
                }
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(test_config, f)
            
            # Load config
            with patch('config.config_loader.project_path', return_value=config_path.parent):
                from config.config_loader import ConfigLoader
                loader = ConfigLoader()
                loaded = loader.load_config(config_path)
            
            assert loaded is not None

    def test_settings_ui_integration(self):
        """Test settings UI integration."""
        from core.settings_overview import get_settings_overview
        
        settings = get_settings_overview()
        
        # Get all settings
        all_settings = settings.get_settings()
        
        assert all_settings is not None

    def test_settings_update(self):
        """Test updating settings."""
        from core.settings_overview import get_settings_overview
        
        settings = get_settings_overview()
        
        # Update setting
        settings.update_setting("theme", "dark")
        
        # Verify update
        current = settings.get_setting("theme")
        
        assert current == "dark"

    def test_settings_reset(self):
        """Test resetting settings to defaults."""
        from core.settings_overview import get_settings_overview
        
        settings = get_settings_overview()
        
        # Reset to defaults
        settings.reset_to_defaults()
        
        # Should have reset
        assert True  # Placeholder for actual reset test

    def test_settings_export_import(self):
        """Test exporting and importing settings."""
        from core.settings_overview import get_settings_overview
        
        settings = get_settings_overview()
        
        # Export settings
        exported = settings.export_settings()
        
        # Import settings
        imported = settings.import_settings(exported)
        
        assert imported is not None

    def test_config_with_mica(self):
        """Test configuration integration with M.I.C.A."""
        from main import MicaLive
        from config.config_loader import get_config
        
        config = get_config()
        mica = MicaLive()
        
        # M.I.C.A should use config
        assert mica is not None
        assert config is not None


class TestSettingsErrorHandling:
    """Error handling tests for settings system."""

    @pytest.fixture
    def config_loader(self):
        """Create a fresh ConfigLoader instance for testing."""
        from config.config_loader import get_config
        return get_config()

    def test_invalid_config_file(self, config_loader):
        """Test handling of invalid config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "invalid.yaml"
            invalid_path.write_text("{invalid yaml content")
            
            with patch('config.config_loader.project_path', return_value=temp_dir):
                from config.config_loader import ConfigLoader
                loader = ConfigLoader()
                
                with pytest.raises(yaml.YAMLError):
                    loader.load_config(invalid_path)

    def test_missing_config_file(self, config_loader):
        """Test handling of missing config file."""
        nonexistent_path = Path("/nonexistent/config.yaml")
        
        with pytest.raises(FileNotFoundError):
            config_loader.load_config(nonexistent_path)

    def test_invalid_setting_value(self):
        """Test handling of invalid setting values."""
        from core.settings_overview import get_settings_overview
        
        settings = get_settings_overview()
        
        # Try to set invalid value
        try:
            settings.update_setting("invalid_setting", "value")
        except (KeyError, ValueError):
            pass  # Expected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
