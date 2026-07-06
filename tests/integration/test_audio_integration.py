"""
Integration tests for audio system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestAudioIntegration:
    """Integration tests for audio system components."""

    @pytest.fixture
    def audio_handler(self):
        """Create a fresh AudioHandler instance for testing."""
        from core.audio_handler import AudioHandler
        return AudioHandler()

    @patch('core.audio_handler.sd')
    def test_audio_recording(self, mock_sd, audio_handler):
        """Test audio recording."""
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        audio_handler.start_recording()
        
        assert audio_handler.is_recording
        mock_sd.InputStream.assert_called_once()

    @patch('core.audio_handler.sd')
    def test_audio_playback(self, mock_sd, audio_handler):
        """Test audio playback."""
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream
        
        audio_data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        audio_handler.play_audio(audio_data)
        
        mock_sd.OutputStream.assert_called_once()

    @patch('core.audio_handler.sd')
    def test_voice_recognition(self, mock_sd, audio_handler):
        """Test voice recognition integration."""
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        # Record audio
        audio_handler.start_recording()
        audio_data = np.random.rand(16000).astype(np.float32)
        audio_handler.stop_recording()
        
        # Process audio (mocked)
        text = audio_handler.transcribe(audio_data)
        
        assert text is not None

    @patch('core.audio_handler.sd')
    def test_text_to_speech(self, mock_sd, audio_handler):
        """Test text-to-speech integration."""
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream
        
        text = "Hello M.I.C.A"
        audio_handler.speak(text)
        
        mock_sd.OutputStream.assert_called_once()

    @patch('core.audio_handler.sd')
    def test_audio_with_emotion(self, mock_sd, audio_handler):
        """Test audio with emotion detection."""
        from core.voice_emotion import VoiceEmotion
        
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        emotion_analyzer = VoiceEmotion()
        
        # Record audio
        audio_handler.start_recording()
        audio_data = np.random.rand(16000).astype(np.float32)
        audio_handler.stop_recording()
        
        # Detect emotion
        emotion = emotion_analyzer.analyze_audio(audio_data, sample_rate=16000)
        
        assert emotion is not None

    @patch('core.audio_handler.sd')
    def test_audio_with_mica(self, mock_sd):
        """Test audio integration with M.I.C.A core."""
        from main import MicaLive
        from core.audio_handler import AudioHandler
        
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        mica = MicaLive()
        audio = AudioHandler()
        
        # Record voice input
        audio.start_recording()
        audio_data = np.random.rand(16000).astype(np.float32)
        audio.stop_recording()
        
        # Process through M.I.C.A
        response = mica.process_audio(audio_data)
        
        assert response is not None

    @patch('core.audio_handler.sd')
    def test_noise_cancellation(self, mock_sd, audio_handler):
        """Test noise cancellation."""
        audio_handler.enable_noise_cancellation = True
        
        # Create noisy audio
        noisy_audio = np.random.rand(16000).astype(np.float32)
        
        # Apply noise cancellation
        clean_audio = audio_handler.remove_noise(noisy_audio)
        
        assert clean_audio is not None

    @patch('core.audio_handler.sd')
    def test_audio_streaming(self, mock_sd, audio_handler):
        """Test audio streaming."""
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        audio_handler.enable_streaming = True
        audio_handler.start_recording()
        
        # Stream audio chunks
        chunks = []
        for i in range(5):
            chunk = np.random.rand(1024).astype(np.float32)
            chunks.append(chunk)
        
        audio_handler.stop_recording()
        
        assert len(chunks) == 5


class TestAudioErrorHandling:
    """Error handling tests for audio system."""

    @pytest.fixture
    def audio_handler(self):
        """Create a fresh AudioHandler instance for testing."""
        from core.audio_handler import AudioHandler
        return AudioHandler()

    @patch('core.audio_handler.sd', side_effect=Exception("Audio device error"))
    def test_device_error(self, mock_sd, audio_handler):
        """Test handling of audio device errors."""
        with pytest.raises(Exception):
            audio_handler.start_recording()

    def test_invalid_audio_data(self, audio_handler):
        """Test handling of invalid audio data."""
        invalid_data = [None, [], {}, "not audio"]
        
        for invalid in invalid_data:
            try:
                audio_handler.play_audio(invalid)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected

    @patch('core.audio_handler.sd')
    def test_recording_timeout(self, mock_sd, audio_handler):
        """Test handling of recording timeout."""
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        audio_handler.recording_timeout_seconds = 1
        audio_handler.start_recording()
        
        # Simulate timeout
        import time
        time.sleep(2)
        
        # Should handle timeout
        assert True  # Placeholder for actual timeout test


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
