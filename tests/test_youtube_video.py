"""
Tests for actions.youtube_video module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestYouTubeVideo:
    """Test cases for youtube_video action."""

    @pytest.fixture
    def youtube_video(self):
        """Create a fresh youtube_video instance for testing."""
        from actions.youtube_video import youtube_video
        return youtube_video

    @patch('actions.youtube_video.youtube_transcript_api')
    def test_get_transcript(self, mock_youtube_api, youtube_video):
        """Test getting video transcript."""
        mock_transcript = [
            {"text": "Hello world", "start": 0.0, "duration": 2.0},
            {"text": "This is a test", "start": 2.0, "duration": 3.0}
        ]
        mock_youtube_api.YouTranscriptApi.get_transcript.return_value = mock_transcript
        
        result = youtube_video.get_transcript("video_id_123")
        
        assert result is not None
        assert len(result) >= 2

    @patch('actions.youtube_video.youtube_transcript_api')
    def test_get_transcript_with_language(self, mock_youtube_api, youtube_video):
        """Test getting transcript with specific language."""
        mock_transcript = [{"text": "Hola mundo", "start": 0.0, "duration": 2.0}]
        mock_youtube_api.YouTranscriptApi.get_transcript.return_value = mock_transcript
        
        result = youtube_video.get_transcript("video_id_123", language="es")
        
        assert result is not None

    @patch('actions.youtube_video.youtube_transcript_api')
    def test_search_transcript(self, mock_youtube_api, youtube_video):
        """Test searching within transcript."""
        mock_transcript = [
            {"text": "Hello world", "start": 0.0, "duration": 2.0},
            {"text": "Python programming", "start": 2.0, "duration": 3.0}
        ]
        mock_youtube_api.YouTranscriptApi.get_transcript.return_value = mock_transcript
        
        result = youtube_video.search_transcript("video_id_123", "Python")
        
        assert result is not None

    @patch('actions.youtube_video.youtube_transcript_api')
    def test_get_video_info(self, mock_youtube_api, youtube_video):
        """Test getting video information."""
        mock_info = {
            "title": "Test Video",
            "author": "Test Channel",
            "length": 300,
            "view_count": 1000
        }
        mock_youtube_api.YouTube.get_info.return_value = mock_info
        
        result = youtube_video.get_info("video_id_123")
        
        assert result is not None

    @patch('actions.youtube_video.youtube_transcript_api')
    def test_download_transcript(self, mock_youtube_api, youtube_video):
        """Test downloading transcript to file."""
        mock_transcript = [{"text": "Hello", "start": 0.0, "duration": 1.0}]
        mock_youtube_api.YouTranscriptApi.get_transcript.return_value = mock_transcript
        
        result = youtube_video.download_transcript("video_id_123", "transcript.txt")
        
        assert result is not None


class TestYouTubeVideoErrorHandling:
    """Test error handling in youtube_video."""

    @pytest.fixture
    def youtube_video(self):
        """Create a fresh youtube_video instance for testing."""
        from actions.youtube_video import youtube_video
        return youtube_video

    @patch('actions.youtube_video.youtube_transcript_api', side_effect=Exception("API error"))
    def test_api_error(self, mock_youtube_api, youtube_video):
        """Test error handling when API fails."""
        with pytest.raises(Exception):
            youtube_video.get_transcript("video_id_123")

    def test_empty_video_id(self, youtube_video):
        """Test handling of empty video ID."""
        with pytest.raises(ValueError):
            youtube_video.get_transcript("")

    @patch('actions.youtube_video.youtube_transcript_api')
    def test_no_transcript_available(self, mock_youtube_api, youtube_video):
        """Test handling when no transcript is available."""
        mock_youtube_api.YouTranscriptApi.get_transcript.side_effect = Exception("No transcript")
        
        with pytest.raises(Exception):
            youtube_video.get_transcript("video_id_123")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
