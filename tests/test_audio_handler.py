"""
Tests for core.audio_handler module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestAudioHandler:
    """Test cases for AudioHandler class."""

    @pytest.fixture
    def audio_handler(self):
        """Create a fresh AudioHandler instance for testing."""
        from core.audio_handler import AudioHandler
        return AudioHandler()

    def test_audio_handler_initialization(self, audio_handler):
        """Test AudioHandler initialization."""
        assert audio_handler is not None
        assert hasattr(audio_handler, 'start_recording')
        assert hasattr(audio_handler, 'stop_recording')
        assert hasattr(audio_handler, 'play_audio')

    @patch('core.audio_handler.sd')
    def test_start_recording(self, mock_sd, audio_handler):
        """Test starting audio recording."""
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        audio_handler.start_recording()
        
        assert audio_handler.is_recording
        mock_sd.InputStream.assert_called_once()

    @patch('core.audio_handler.sd')
    def test_stop_recording(self, mock_sd, audio_handler):
        """Test stopping audio recording."""
        mock_stream = MagicMock()
        audio_handler.stream = mock_stream
        audio_handler.is_recording = True
        
        audio_handler.stop_recording()
        
        assert not audio_handler.is_recording
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

    @patch('core.audio_handler.sd')
    def test_play_audio(self, mock_sd, audio_handler):
        """Test playing audio."""
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream
        
        audio_data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        audio_handler.play_audio(audio_data)
        
        mock_sd.OutputStream.assert_called_once()

    def test_audio_data_validation(self, audio_handler):
        """Test audio data validation."""
        # Test with valid data
        valid_data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        assert audio_handler._validate_audio_data(valid_data)
        
        # Test with invalid data
        invalid_data = "not an array"
        assert not audio_handler._validate_audio_data(invalid_data)

    def test_sample_rate_handling(self, audio_handler):
        """Test sample rate configuration."""
        assert audio_handler.sample_rate in [16000, 24000, 44100, 48000]

    def test_channel_configuration(self, audio_handler):
        """Test channel configuration (mono/stereo)."""
        assert audio_handler.channels in [1, 2]

    @patch('core.audio_handler.sd')
    def test_device_selection(self, mock_sd, audio_handler):
        """Test audio device selection."""
        mock_sd.query_devices.return_value = [
            {'name': 'Default', 'max_input_channels': 1, 'max_output_channels': 1}
        ]
        
        devices = audio_handler.get_available_devices()
        assert len(devices) > 0

    def test_audio_chunk_processing(self, audio_handler):
        """Test audio chunk processing."""
        chunk_size = 1024
        audio_data = np.random.rand(chunk_size).astype(np.float32)
        
        processed = audio_handler.process_chunk(audio_data)
        assert processed is not None
        assert len(processed) <= len(audio_data)


class TestAudioHandlerErrorHandling:
    """Test error handling in AudioHandler."""

    @pytest.fixture
    def audio_handler(self):
        """Create a fresh AudioHandler instance for testing."""
        from core.audio_handler import AudioHandler
        return AudioHandler()

    @patch('core.audio_handler.sd', side_effect=Exception("Sounddevice error"))
    def test_recording_error_handling(self, mock_sd, audio_handler):
        """Test error handling during recording."""
        with pytest.raises(Exception):
            audio_handler.start_recording()

    @patch('core.audio_handler.sd', side_effect=Exception("Playback error"))
    def test_playback_error_handling(self, mock_sd, audio_handler):
        """Test error handling during playback."""
        audio_data = np.array([0.1, 0.2], dtype=np.float32)
        with pytest.raises(Exception):
            audio_handler.play_audio(audio_data)

    def test_invalid_audio_format(self, audio_handler):
        """Test handling of invalid audio formats."""
        invalid_formats = [
            None,
            [],
            {},
            "string"
        ]
        
        for invalid_format in invalid_formats:
            with pytest.raises((ValueError, TypeError, AttributeError)):
                audio_handler.play_audio(invalid_format)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
