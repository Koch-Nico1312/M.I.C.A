"""
Tests for actions.flight_finder module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestFlightFinder:
    """Test cases for flight_finder action."""

    @pytest.fixture
    def flight_finder(self):
        """Create a fresh flight_finder instance for testing."""
        from actions.flight_finder import flight_finder
        return flight_finder

    @patch('actions.flight_finder.amadeus')
    def test_search_flights(self, mock_amadeus, flight_finder):
        """Test searching for flights."""
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "flight1",
                "price": {"total": "299.00"},
                "itineraries": [{
                    "duration": "PT2H30M",
                    "segments": [{
                        "departure": {"iataCode": "JFK", "at": "2024-01-01T10:00:00"},
                        "arrival": {"iataCode": "LAX", "at": "2024-01-01T13:30:00"}
                    }]
                }]
            }
        ]
        mock_amadeus.return_value.shopping.flight_offers.get.return_value = mock_response
        
        result = flight_finder.search(
            origin="JFK",
            destination="LAX",
            departure_date=datetime.now() + timedelta(days=7)
        )
        
        assert result is not None
        assert len(result) >= 1

    @patch('actions.flight_finder.amadeus')
    def test_search_with_filters(self, mock_amadeus, flight_finder):
        """Test searching flights with filters."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_amadeus.return_value.shopping.flight_offers.get.return_value = mock_response
        
        result = flight_finder.search(
            origin="JFK",
            destination="LAX",
            departure_date=datetime.now() + timedelta(days=7),
            max_price=500,
            airlines=["DL", "AA"]
        )
        
        assert result is not None

    @patch('actions.flight_finder.amadeus')
    def test_get_airport_info(self, mock_amadeus, flight_finder):
        """Test getting airport information."""
        mock_response = MagicMock()
        mock_response.data = [
            {
                "iataCode": "JFK",
                "name": "John F. Kennedy International Airport",
                "city": "New York",
                "country": "United States"
            }
        ]
        mock_amadeus.return_value.reference_data.locations.airports.get.return_value = mock_response
        
        result = flight_finder.get_airport_info("JFK")
        
        assert result is not None

    @patch('actions.flight_finder.amadeus')
    def test_get_flight_details(self, mock_amadeus, flight_finder):
        """Test getting detailed flight information."""
        mock_response = MagicMock()
        mock_response.data = {
            "id": "flight1",
            "price": {"total": "299.00"},
            "itineraries": []
        }
        mock_amadeus.return_value.shopping.flight_offers.get.return_value = mock_response
        
        result = flight_finder.get_flight_details("flight1")
        
        assert result is not None


class TestFlightFinderErrorHandling:
    """Test error handling in flight_finder."""

    @pytest.fixture
    def flight_finder(self):
        """Create a fresh flight_finder instance for testing."""
        from actions.flight_finder import flight_finder
        return flight_finder

    @patch('actions.flight_finder.amadeus', side_effect=Exception("API error"))
    def test_api_error(self, mock_amadeus, flight_finder):
        """Test error handling when API fails."""
        with pytest.raises(Exception):
            flight_finder.search("JFK", "LAX", datetime.now())

    def test_invalid_airport_code(self, flight_finder):
        """Test handling of invalid airport code."""
        with pytest.raises(ValueError):
            flight_finder.search("INVALID", "LAX", datetime.now())

    def test_past_departure_date(self, flight_finder):
        """Test handling of past departure date."""
        past_date = datetime.now() - timedelta(days=1)
        
        with pytest.raises(ValueError):
            flight_finder.search("JFK", "LAX", past_date)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
