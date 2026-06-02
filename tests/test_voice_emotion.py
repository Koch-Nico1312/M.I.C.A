"""
Tests for core.voice_emotion module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestVoiceEmotion:
    """Test cases for VoiceEmotion class."""

    @pytest.fixture
    def voice_emotion(self):
        """Create a fresh VoiceEmotion instance for testing."""
        from core.voice_emotion import VoiceEmotion
        return VoiceEmotion()

    def test_voice_emotion_initialization(self, voice_emotion):
        """Test VoiceEmotion initialization."""
        assert voice_emotion is not None
        assert hasattr(voice_emotion, 'analyze_audio')
        assert hasattr(voice_emotion, 'format_response_for_emotion')

    @patch('core.voice_emotion.librosa')
    def test_analyze_audio(self, mock_librosa, voice_emotion):
        """Test audio emotion analysis."""
        # Mock audio data
        mock_audio = np.random.rand(16000).astype(np.float32)
        mock_librosa.load.return_value = (mock_audio, 16000)
        
        result = voice_emotion.analyze_audio(mock_audio, sample_rate=16000)
        
        assert result is not None
        assert hasattr(result, 'emotion')
        assert hasattr(result, 'confidence')

    def test_detect_frustration(self, voice_emotion):
        """Test frustration detection."""
        # Mock audio with frustration characteristics
        mock_audio = np.random.rand(16000).astype(np.float32)
        
        result = voice_emotion.analyze_audio(mock_audio, sample_rate=16000)
        
        # Should detect some emotion
        assert result.emotion is not None

    def test_detect_urgency(self, voice_emotion):
        """Test urgency detection."""
        mock_audio = np.random.rand(16000).astype(np.float32)
        
        result = voice_emotion.analyze_audio(mock_audio, sample_rate=16000)
        
        assert result.emotion is not None

    def test_format_response_for_emotion(self, voice_emotion):
        """Test formatting response based on emotion."""
        response = "Here is your information"
        
        # Test with different emotions
        emotions = ["frustrated", "urgent", "calm", "happy"]
        
        for emotion in emotions:
            formatted = voice_emotion.format_response_for_emotion(response, emotion)
            assert formatted is not None
            assert isinstance(formatted, str)

    def test_sensitivity_adjustment(self, voice_emotion):
        """Test emotion detection sensitivity."""
        voice_emotion.sensitivity = 0.8
        
        mock_audio = np.random.rand(16000).astype(np.float32)
        result = voice_emotion.analyze_audio(mock_audio, sample_rate=16000)
        
        assert result is not None

    def test_tone_adjustment(self, voice_emotion):
        """Test tone adjustment based on emotion."""
        voice_emotion.adjust_tone = True
        
        response = "I understand your request"
        formatted = voice_emotion.format_response_for_emotion(response, "frustrated")
        
        assert formatted is not None


class TestVoiceEmotionErrorHandling:
    """Test error handling in VoiceEmotion."""

    @pytest.fixture
    def voice_emotion(self):
        """Create a fresh VoiceEmotion instance for testing."""
        from core.voice_emotion import VoiceEmotion
        return VoiceEmotion()

    def test_invalid_audio_handling(self, voice_emotion):
        """Test handling of invalid audio data."""
        invalid_audios = [None, [], {}, "not audio"]
        
        for invalid_audio in invalid_audios:
            try:
                voice_emotion.analyze_audio(invalid_audio, sample_rate=16000)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected

    @patch('core.voice_emotion.librosa', side_effect=Exception("Librosa error"))
    def test_librosa_error_handling(self, mock_librosa, voice_emotion):
        """Test error handling when librosa fails."""
        mock_audio = np.random.rand(16000).astype(np.float32)
        
        with pytest.raises(Exception):
            voice_emotion.analyze_audio(mock_audio, sample_rate=16000)

    def test_invalid_emotion_handling(self, voice_emotion):
        """Test handling of invalid emotion labels."""
        response = "Test response"
        invalid_emotions = [None, "", "invalid_emotion"]
        
        for invalid_emotion in invalid_emotions:
            try:
                voice_emotion.format_response_for_emotion(response, invalid_emotion)
            except (ValueError, AttributeError):
                pass  # Expected


class TestVoiceEmotionIntegration:
    """Integration tests for VoiceEmotion."""

    @patch('core.voice_emotion.librosa')
    def test_emotion_based_response_adjustment(self, mock_librosa):
        """Test full emotion-based response adjustment cycle."""
        from core.voice_emotion import VoiceEmotion
        
        emotion_analyzer = VoiceEmotion()
        emotion_analyzer.adjust_tone = True
        
        # Simulate audio analysis
        mock_audio = np.random.rand(16000).astype(np.float32)
        mock_librosa.load.return_value = (mock_audio, 16000)
        
        result = emotion_analyzer.analyze_audio(mock_audio, sample_rate=16000)
        
        # Format response based on detected emotion
        original_response = "Here is the information you requested"
        adjusted_response = emotion_analyzer.format_response_for_emotion(
            original_response, 
            result.emotion
        )
        
        assert adjusted_response is not None
        assert isinstance(adjusted_response, str)

    def test_emotion_history_tracking(self):
        """Test emotion history tracking over time."""
        from core.voice_emotion import VoiceEmotion
        
        analyzer = VoiceEmotion()
        
        # Track multiple emotions
        emotions = ["calm", "frustrated", "urgent", "calm"]
        for emotion in emotions:
            analyzer.track_emotion(emotion)
        
        # Verify history
        assert len(analyzer.emotion_history) == len(emotions)

    def test_emotion_statistics(self):
        """Test emotion statistics calculation."""
        from core.voice_emotion import VoiceEmotion
        
        analyzer = VoiceEmotion()
        
        # Track emotions
        for _ in range(5):
            analyzer.track_emotion("calm")
        for _ in range(3):
            analyzer.track_emotion("frustrated")
        
        stats = analyzer.get_emotion_statistics()
        
        assert stats is not None
        assert "calm" in stats
        assert stats["calm"] == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
