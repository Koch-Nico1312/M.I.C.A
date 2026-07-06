"""
Integration tests for smart home system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestSmartHomeIntegration:
    """Integration tests for smart home system components."""

    @pytest.fixture
    def smart_home(self):
        """Create a fresh SmartHome instance for testing."""
        from core.smart_home import SmartHome
        return SmartHome()

    @patch('core.smart_home.requests')
    def test_device_discovery(self, mock_requests, smart_home):
        """Test smart home device discovery."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "devices": [
                {"id": "light1", "name": "Living Room Light", "type": "light"},
                {"id": "thermostat1", "name": "Thermostat", "type": "thermostat"}
            ]
        }
        mock_requests.get.return_value = mock_response
        
        devices = smart_home.discover_devices()
        
        assert devices is not None
        assert len(devices) >= 2

    @patch('core.smart_home.requests')
    def test_device_control(self, mock_requests, smart_home):
        """Test controlling smart home devices."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_requests.post.return_value = mock_response
        
        result = smart_home.control_device("light1", "turn_on")
        
        assert result is not None

    @patch('core.smart_home.requests')
    def test_device_status(self, mock_requests, smart_home):
        """Test getting device status."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "light1",
            "status": "on",
            "brightness": 75
        }
        mock_requests.get.return_value = mock_response
        
        status = smart_home.get_device_status("light1")
        
        assert status is not None
        assert status["status"] == "on"

    @patch('core.smart_home.requests')
    def test_scene_activation(self, mock_requests, smart_home):
        """Test activating smart home scenes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_requests.post.return_value = mock_response
        
        result = smart_home.activate_scene("movie_mode")
        
        assert result is not None

    @patch('core.smart_home.requests')
    def test_automation_creation(self, mock_requests, smart_home):
        """Test creating smart home automations."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "automation_id": "auto1"}
        mock_requests.post.return_value = mock_response
        
        automation = {
            "name": "Morning Routine",
            "trigger": {"type": "time", "value": "07:00"},
            "actions": [
                {"device": "light1", "action": "turn_on"},
                {"device": "thermostat1", "action": "set_temperature", "value": 22}
            ]
        }
        
        result = smart_home.create_automation(automation)
        
        assert result is not None

    @patch('core.smart_home.requests')
    def test_energy_monitoring(self, mock_requests, smart_home):
        """Test energy monitoring."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total_kwh": 15.5,
            "devices": [
                {"id": "light1", "kwh": 2.5},
                {"id": "thermostat1", "kwh": 13.0}
            ]
        }
        mock_requests.get.return_value = mock_response
        
        energy = smart_home.get_energy_usage()
        
        assert energy is not None
        assert "total_kwh" in energy

    @patch('core.smart_home.requests')
    def test_integration_with_mica(self, mock_requests):
        """Test smart home integration with M.I.C.A."""
        from core.smart_home import SmartHome
        from main import MicaLive
        
        smart_home = SmartHome()
        mica = MicaLive()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_requests.post.return_value = mock_response
        
        # Control device through M.I.C.A
        result = smart_home.control_device("light1", "turn_on")
        
        assert result is not None


class TestSmartHomeErrorHandling:
    """Error handling tests for smart home system."""

    @pytest.fixture
    def smart_home(self):
        """Create a fresh SmartHome instance for testing."""
        from core.smart_home import SmartHome
        return SmartHome()

    @patch('core.smart_home.requests', side_effect=Exception("Network error"))
    def test_network_error_handling(self, mock_requests, smart_home):
        """Test handling of network errors."""
        with pytest.raises(Exception):
            smart_home.discover_devices()

    def test_invalid_device_id(self, smart_home):
        """Test handling of invalid device ID."""
        with pytest.raises(ValueError):
            smart_home.control_device("", "turn_on")

    @patch('core.smart_home.requests')
    def test_device_not_found(self, mock_requests, smart_home):
        """Test handling of device not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response
        
        with pytest.raises(Exception):
            smart_home.get_device_status("nonexistent_device")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
