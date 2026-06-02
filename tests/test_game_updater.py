"""
Tests for actions.game_updater module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestGameUpdater:
    """Test cases for game_updater action."""

    @pytest.fixture
    def game_updater(self):
        """Create a fresh game_updater instance for testing."""
        from actions.game_updater import game_updater
        return game_updater

    @patch('actions.game_updater.steam')
    def test_check_game_update(self, mock_steam, game_updater):
        """Test checking for game updates."""
        mock_steam.return_value.apps.return_value.update_available.return_value = True
        
        result = game_updater.check_update("Game Name")
        
        assert result is not None

    @patch('actions.game_updater.steam')
    def test_update_game(self, mock_steam, game_updater):
        """Test updating a game."""
        mock_steam.return_value.apps.return_value.update.return_value = True
        
        result = game_updater.update("Game Name")
        
        assert result is not None

    @patch('actions.game_updater.steam')
    def test_get_installed_games(self, mock_steam, game_updater):
        """Test getting list of installed games."""
        mock_steam.return_value.apps.return_value.installed.return_value = [
            {"name": "Game 1", "appid": 123},
            {"name": "Game 2", "appid": 456}
        ]
        
        result = game_updater.list_installed()
        
        assert result is not None
        assert len(result) >= 2

    @patch('actions.game_updater.steam')
    def test_launch_game(self, mock_steam, game_updater):
        """Test launching a game."""
        mock_steam.return_value.apps.return_value.launch.return_value = True
        
        result = game_updater.launch("Game Name")
        
        assert result is not None

    @patch('actions.game_updater.steam')
    def test_verify_game_integrity(self, mock_steam, game_updater):
        """Test verifying game integrity."""
        mock_steam.return_value.apps.return_value.verify.return_value = True
        
        result = game_updater.verify("Game Name")
        
        assert result is not None


class TestGameUpdaterErrorHandling:
    """Test error handling in game_updater."""

    @pytest.fixture
    def game_updater(self):
        """Create a fresh game_updater instance for testing."""
        from actions.game_updater import game_updater
        return game_up

    @patch('actions.game_updater.steam', side_effect=Exception("Steam error"))
    def test_steam_error(self, mock_steam, game_updater):
        """Test error handling when Steam fails."""
        with pytest.raises(Exception):
            game_updater.check_update("Game Name")

    def test_empty_game_name(self, game_updater):
        """Test handling of empty game name."""
        with pytest.raises(ValueError):
            game_updater.check_update("")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
