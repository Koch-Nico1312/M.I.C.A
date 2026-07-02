from memory.memory_curation import build_curation_report


def test_curation_detects_duplicate_without_mutating():
    memory = {
        "notes": {
            "preferred_name": {"value": "Call the user Alex", "confidence": 0.9},
            "preferred_name_copy": {"value": "Call the user Alex", "confidence": 0.8},
        },
        "identity": {},
    }

    report = build_curation_report(memory)

    assert report["counts"]["duplicates"] == 1
    assert report["suggestions"][0]["recommendation"] == "review_or_merge"
    assert "preferred_name_copy" in memory["notes"]


def test_curation_surfaces_low_confidence_entries():
    memory = {"notes": {"maybe": {"value": "Uncertain fact", "confidence": 0.2}}}

    report = build_curation_report(memory)

    assert report["counts"]["low_confidence"] == 1
    assert report["suggestions"][0]["kind"] == "low_confidence"
