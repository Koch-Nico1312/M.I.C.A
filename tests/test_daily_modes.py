from core.daily_modes import MODE_PRESETS, list_modes


def test_list_modes_contains_daily_driver_presets():
    payload = list_modes()
    names = {item["name"] for item in payload["modes"]}

    assert {"safe", "work", "focus", "offline", "admin"}.issubset(names)
    assert "security" in MODE_PRESETS["safe"]

