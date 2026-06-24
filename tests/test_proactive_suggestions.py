"""
Tests for core.proactive_suggestions module.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.proactive_suggestions import ProactiveSuggestions


class Clock:
    def __init__(self, start: datetime):
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs):
        self.current += timedelta(**kwargs)


@pytest.fixture
def clock():
    return Clock(datetime(2026, 6, 24, 9, 0, 0))


@pytest.fixture
def state_path(tmp_path: Path):
    return tmp_path / "proactive_state.json"


@pytest.fixture
def proactive_suggestions(clock, state_path):
    suggestions = ProactiveSuggestions(state_path=state_path, now_provider=clock.now)
    suggestions.enabled = True
    suggestions.mode = "active"
    suggestions.max_suggestions = 5
    suggestions.cooldown_minutes = 30
    suggestions.dismiss_minutes = 60
    suggestions.mute_minutes = 60
    return suggestions


def test_track_action_keeps_backward_compatible_history(proactive_suggestions):
    proactive_suggestions.track_action("open_chrome", success=True)

    assert "open_chrome" in proactive_suggestions.action_history
    assert proactive_suggestions.action_history["open_chrome"]["count"] == 1
    assert proactive_suggestions.action_count["open_chrome"] == 1


def test_repetitive_actions_are_deduped_and_put_on_cooldown(proactive_suggestions):
    for _ in range(3):
        proactive_suggestions.track_action("check_weather", success=True)

    first = proactive_suggestions.generate_suggestions()
    second = proactive_suggestions.generate_suggestions()

    assert len(first) == 1
    assert first[0].key == "repetitive:check_weather"
    assert len(second) == 0
    assert len(proactive_suggestions.get_suggestions()) == 1
    assert not proactive_suggestions._check_cooldown("repetitive:check_weather")


def test_cooldown_expires_and_allows_suggestion_again(
    proactive_suggestions,
    clock,
):
    for _ in range(3):
        proactive_suggestions.track_action("open_chrome", success=True)
    assert proactive_suggestions.generate_suggestions()

    proactive_suggestions.clear_suggestions()
    clock.advance(minutes=31)
    for _ in range(3):
        proactive_suggestions.track_action("open_chrome", success=True)

    generated = proactive_suggestions.generate_suggestions()

    assert len(generated) == 1
    assert generated[0].reason


def test_dismiss_suppresses_suggestion_until_expiry(
    proactive_suggestions,
    clock,
):
    proactive_suggestions.track_file(Path("main.py"))
    assert proactive_suggestions.generate_suggestions()
    proactive_suggestions.dismiss_suggestion(0, minutes=20)

    clock.advance(minutes=10)
    blocked = proactive_suggestions.generate_suggestions()
    clock.advance(minutes=21)
    allowed = proactive_suggestions.generate_suggestions()

    assert blocked == []
    assert len(allowed) == 1
    assert allowed[0].key == "file:.py:main.py"


def test_mute_suppresses_category_until_expiry(proactive_suggestions, clock):
    context = {
        "system": {"memory_percent": 95},
        "now": clock.now(),
    }
    proactive_suggestions.mute("system", minutes=15)

    muted = proactive_suggestions.generate_suggestions(context)
    clock.advance(minutes=16)
    context["now"] = clock.now()
    unmuted = proactive_suggestions.generate_suggestions(context)

    assert muted == []
    assert len(unmuted) == 1
    assert unmuted[0].category == "system"


def test_suppressions_are_persisted_and_loaded(state_path, clock):
    suggestions = ProactiveSuggestions(state_path=state_path, now_provider=clock.now)
    suggestions.dismiss("tasks:overdue", minutes=30, reason="test dismiss")
    suggestions.mute("system", minutes=45, reason="test mute")
    suggestions._set_cooldown("calendar:prep:Standup", now=clock.now())
    suggestions._save_state()

    loaded = ProactiveSuggestions(state_path=state_path, now_provider=clock.now)

    assert "tasks:overdue" in loaded.dismissed
    assert loaded.dismissed["tasks:overdue"].reason == "test dismiss"
    assert "system" in loaded.mutes
    assert "calendar:prep:Standup" in loaded.cooldowns


def test_contextual_reasons_for_calendar_tasks_and_system(
    proactive_suggestions,
    clock,
):
    context = {
        "now": clock.now(),
        "calendar": {
            "next_event": {
                "title": "Standup",
                "start": (clock.now() + timedelta(minutes=12)).isoformat(),
            }
        },
        "tasks": {"overdue": [{"title": "pay bill"}]},
        "system": {"cpu_percent": 94},
    }

    generated = proactive_suggestions.generate_suggestions(context)
    reasons = {item.key: item.reason for item in generated}

    assert "calendar:prep:Standup" in reasons
    assert "within 30 minutes" in reasons["calendar:prep:Standup"]
    assert "tasks:overdue" in reasons
    assert any("1 overdue" in item.text for item in generated)
    assert "system:cpu" in reasons
    assert "cpu_percent=94%" in reasons["system:cpu"]


def test_file_suggestion_is_situational(proactive_suggestions):
    proactive_suggestions.track_file(Path("component.tsx"))

    generated = proactive_suggestions.generate_suggestions()

    assert generated[0].category == "coding"
    assert "React component" in generated[0].text
    assert generated[0].reason == "The most recent file context is component.tsx."


def test_get_suggestions_returns_legacy_dict_shape(proactive_suggestions):
    proactive_suggestions.track_file(Path("notes.md"))
    proactive_suggestions.generate_suggestions()

    item = proactive_suggestions.get_suggestions()[0]

    assert item["text"]
    assert item["priority"] == "medium"
    assert item["category"] == "productivity"
    assert item["timestamp"]
    assert item["reason"]


def test_detect_patterns_legacy_wrapper(proactive_suggestions):
    for _ in range(3):
        proactive_suggestions.track_action("open_chrome", success=True)

    patterns = proactive_suggestions.detect_patterns()

    assert len(patterns) == 1
    assert patterns[0].key == "repetitive:open_chrome"


def test_should_suggest_legacy_global_cooldown(proactive_suggestions, clock):
    proactive_suggestions.last_suggestion_time = clock.now()

    assert not proactive_suggestions.should_suggest()

    clock.advance(minutes=31)

    assert proactive_suggestions.should_suggest()


def test_speak_suggestion_handles_callback_errors(proactive_suggestions):
    mock_speak = Mock(side_effect=Exception("Speak error"))
    proactive_suggestions.set_speak_callback(mock_speak)

    proactive_suggestions.speak_suggestion("Test suggestion")

    mock_speak.assert_called_once_with("Test suggestion")


def test_start_stop_legacy_running_property(proactive_suggestions):
    proactive_suggestions.interval = 3600

    assert proactive_suggestions.start() is True
    assert proactive_suggestions.is_running

    proactive_suggestions.stop()

    assert not proactive_suggestions.is_running


def test_state_file_is_json(proactive_suggestions):
    proactive_suggestions.mute("all", minutes=10)

    data = json.loads(proactive_suggestions.state_path.read_text(encoding="utf-8"))

    assert "mutes" in data
    assert data["mutes"]["all"]["expires_at"]
