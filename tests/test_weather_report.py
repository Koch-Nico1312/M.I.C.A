"""
Tests for actions.weather_report module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestWeatherReport:
    """Test cases for weather_report action."""

    @pytest.fixture
    def weather_report(self):
        """Create a fresh weather_report instance for testing."""
        from actions.weather_report import weather_action
        return weather_action

    @patch('actions.weather_report.requests')
    def test_get_weather(self, mock_requests, weather_report):
        """Test getting weather report."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "current": {
                "temp_c": 25,
                "condition": {"text": "Sunny"},
                "humidity": 60,
                "wind_kph": 10
            },
            "location": {"name": "Berlin"}
        }
        mock_requests.get.return_value = mock_response
        
        result = weather_report("Berlin")
        
        assert result is not None
        assert "temperature" in result or "temp_c" in result

    @patch('actions.weather_report.requests')
    def test_get_weather_with_units(self, mock_requests, weather_report):
        """Test getting weather with specific units."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "current": {
                "temp_c": 25,
                "temp_f": 77,
                "condition": {"text": "Sunny"}
            }
        }
        mock_requests.get.return_value = mock_response
        
        result = weather_report("Berlin", units="fahrenheit")
        
        assert result is not None

    @patch('actions.weather_report.requests')
    def test_get_forecast(self, mock_requests, weather_report):
        """Test getting weather forecast."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "forecast": {
                "forecastday": [
                    {"date": "2024-01-01", "day": {"maxtemp_c": 25, "mintemp_c": 15}},
                    {"date": "2024-01-02", "day": {"maxtemp_c": 26, "mintemp_c": 16}}
                ]
            }
        }
        mock_requests.get.return_value = mock_response
        
        result = weather_report("Berlin", days=2)
        
        assert result is not None

    @patch('actions.weather_report.requests')
    def test_empty_location(self, mock_requests, weather_report):
        """Test handling of empty location."""
        with pytest.raises(ValueError):
            weather_report("")

    @patch('actions.weather_report.requests')
    def test_api_error(self, mock_requests, weather_report):
        """Test handling of API error."""
        mock_requests.get.side_effect = Exception("API error")
        
        with pytest.raises(Exception):
            weather_report("Berlin")


class TestWeatherReportErrorHandling:
    """Test error handling in weather_report."""

    @pytest.fixture
    def weather_report(self):
        """Create a fresh weather_report instance for testing."""
        from actions.weather_report import weather_action
        return weather_action

    @patch('actions.weather_report.requests')
    def test_invalid_location(self, mock_requests, weather_report):
        """Test handling of invalid location."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "Location not found"}
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response
        
        with pytest.raises(Exception):
            weather_report("InvalidLocation12345")

    @patch('actions.weather_report.requests')
    def test_network_error(self, mock_requests, weather_report):
        """Test handling of network error."""
        mock_requests.get.side_effect = Exception("Network error")
        
        with pytest.raises(Exception):
            weather_report("Berlin")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
