import pytest


def test_main_lazy_exports_ignore_dunder_names(monkeypatch):
    import main

    requested = []

    def fake_get_action_module(action_name):
        requested.append(action_name)
        return None

    monkeypatch.setattr(main, "_get_action_module", fake_get_action_module)

    with pytest.raises(AttributeError):
        getattr(main, "__path__")

    assert requested == []


def test_action_loader_ignores_dunder_action_names():
    from core.action_loader import ActionLoader

    loader = ActionLoader()

    assert loader.load_action("__path__") is None


def test_main_exports_new_integration_actions():
    import main

    assert callable(main.crawl_url)
    assert callable(main.agent_reach)
