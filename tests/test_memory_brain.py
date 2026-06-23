from __future__ import annotations

import json

from memory.brain import MemoryBrain


def test_direct_request_saves_preference(tmp_path):
    brain = MemoryBrain(memory_path=tmp_path / "long_term.json")

    handled, candidates = brain.handle_direct_request("Füge hinzu, dass ich Fußball liebe.", source="ui")

    assert handled is True
    assert candidates
    assert candidates[0].category == "preferences"

    data = json.loads((tmp_path / "long_term.json").read_text(encoding="utf-8"))
    entry = data["preferences"][candidates[0].key]
    assert entry["value"] == "Fußball"
    assert entry["source"] == "ui"


def test_observe_extracts_identity_and_project(tmp_path):
    brain = MemoryBrain(memory_path=tmp_path / "long_term.json")

    candidates = brain.observe("Ich wohne in Linz und ich arbeite an einem C# Assistant Projekt.")

    keys = {candidate.key for candidate in candidates}
    assert "city" in keys
    assert any(candidate.category == "projects" for candidate in candidates)

    data = json.loads((tmp_path / "long_term.json").read_text(encoding="utf-8"))
    assert data["identity"]["city"]["value"] == "Linz"
    assert data["projects"]["current_project"]["value"] == "C# Assistant Projekt"


def test_explicit_fallback_saves_note(tmp_path):
    brain = MemoryBrain(memory_path=tmp_path / "long_term.json")

    handled, candidates = brain.handle_direct_request("Merke dir bitte: der blaue Ordner ist wichtig.", source="ui")

    assert handled is True
    assert candidates

    data = json.loads((tmp_path / "long_term.json").read_text(encoding="utf-8"))
    assert "notes" in data
    assert any(entry["value"] for entry in data["notes"].values())


def test_memory_query_returns_summary(tmp_path):
    brain = MemoryBrain(memory_path=tmp_path / "long_term.json")
    brain.observe("Ich wohne in Linz und ich liebe Calisthenics.")

    reply = brain.handle_memory_query("Was weißt du über mich?")

    assert reply is not None
    assert "Linz" in reply
    assert "Calisthenics" in reply


def test_memory_forget_request_removes_entry(tmp_path):
    brain = MemoryBrain(memory_path=tmp_path / "long_term.json")
    brain.observe("Ich wohne in Linz.")

    handled, reply = brain.handle_forget_request("Vergiss Linz bitte.")

    assert handled is True
    assert "gelöscht" in reply or "nichts gefunden" in reply
    data = json.loads((tmp_path / "long_term.json").read_text(encoding="utf-8"))
    assert not data["identity"]
