"""
Tests for actions.roblox_controller module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestRobloxController:
    """Test cases for roblox_controller action."""

    @pytest.fixture
    def roblox_controller(self):
        """Create a fresh roblox_controller instance for testing."""
        from actions.roblox_controller import roblox_controller
        return roblox_controller

    @patch('actions.roblox_controller.subprocess')
    def test_launch_roblox(self, mock_subprocess, roblox_controller):
        """Test launching Roblox."""
        mock_subprocess.Popen.return_value = MagicMock()
        
        result = roblox_controller.launch()
        
        assert result is not None
        mock_subprocess.Popen.assert_called_once()

    @patch('actions.roblox_controller.subprocess')
    def test_launch_specific_game(self, mock_subprocess, roblox_controller):
        """Test launching a specific Roblox game."""
        mock_subprocess.Popen.return_value = MagicMock()
        
        result = roblox_controller.launch_game(game_id="123456789")
        
        assert result is not None

    @patch('actions.roblox_controller.requests')
    def test_get_game_info(self, mock_requests, roblox_controller):
        """Test getting game information."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123456789,
            "name": "Test Game",
            "description": "Test description",
            "playing": 1000
        }
        mock_requests.get.return_value = mock_response
        
        result = roblox_controller.get_game_info("123456789")
        
        assert result is not None
        assert result["name"] == "Test Game"

    @patch('actions.roblox_controller.requests')
    def test_search_games(self, mock_requests, roblox_controller):
        """Test searching for games."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": 1, "name": "Game 1"},
                {"id": 2, "name": "Game 2"}
            ]
        }
        mock_requests.get.return_value = mock_response
        
        result = roblox_controller.search("test query")
        
        assert result is not None
        assert len(result) >= 2

    @patch('actions.roblox_controller.subprocess')
    def test_close_roblox(self, mock_subprocess, roblox_controller):
        """Test closing Roblox."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = roblox_controller.close()
        
        assert result is not None


class TestRobloxControllerErrorHandling:
    """Test error handling in roblox_controller."""

    @pytest.fixture
    def roblox_controller(self):
        """Create a fresh roblox_controller instance for testing."""
        from actions.roblox_controller import roblox_controller
        return roblox_controller

    @patch('actions.roblox_controller.subprocess', side_effect=Exception("Subprocess error"))
    def test_launch_error(self, mock_subprocess, roblox_controller):
        """Test error handling when launch fails."""
        with pytest.raises(Exception):
            roblox_controller.launch()

    @patch('actions.roblox_controller.requests', side_effect=Exception("API error"))
    def test_api_error(self, mock_requests, roblox_controller):
        """Test error handling when API fails."""
        with pytest.raises(Exception):
            roblox_controller.get_game_info("123456789")

    def test_invalid_game_id(self, roblox_controller):
        """Test handling of invalid game ID."""
        with pytest.raises(ValueError):
            roblox_controller.launch_game("invalid_id")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
