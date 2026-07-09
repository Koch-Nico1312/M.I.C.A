import pytest

from actions.screen_processor import _VisionSession, _is_auth_error


def test_vision_auth_error_detection_matches_gemini_live_close():
    assert _is_auth_error(
        RuntimeError(
            "Request had invalid authentication credentials. Expected OAuth 2 access token."
        )
    )


def test_vision_session_start_fails_fast_after_fatal_error():
    session = _VisionSession()
    session._fatal_error = RuntimeError("invalid authentication credentials")

    with pytest.raises(RuntimeError, match="Vision session unavailable"):
        session.start()
