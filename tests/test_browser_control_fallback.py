import actions.browser_control as browser_control_module


class _FakeSession:
    def __init__(self, browser_name, result=None, error=None):
        self.browser_name = browser_name
        self.result = result
        self.error = error

    def go_to(self, url):
        return ("go_to", url)

    def run(self, _coro):
        if self.error:
            raise self.error
        return self.result


class _FakeRegistry:
    def __init__(self):
        self._active_browser = ""
        self.discarded = []
        self.requests = []

    def get(self, browser_name=None):
        name = browser_name or "firefox"
        self.requests.append(name)
        if name == "firefox":
            return _FakeSession(
                "firefox",
                error=RuntimeError("BrowserType.launch_persistent_context: Failed to launch"),
            )
        return _FakeSession(name, result="Opened: https://www.youtube.com/")

    def discard(self, browser_name):
        self.discarded.append(browser_name)

    def switch(self, _target):
        return "switched"

    def list_sessions(self):
        return "sessions"

    def close_all(self):
        return "closed"

    def close_one(self, browser_name):
        return f"{browser_name} closed."


def test_browser_control_falls_back_when_firefox_launch_fails(monkeypatch):
    registry = _FakeRegistry()
    monkeypatch.setattr(browser_control_module, "_registry", registry)
    monkeypatch.setattr(browser_control_module, "_fallback_browsers", lambda primary: ["edge"])

    result = browser_control_module.browser_control(
        {"browser": "firefox", "action": "go_to", "url": "https://www.youtube.com"}
    )

    assert result == "edge fallback: Opened: https://www.youtube.com/"
    assert registry.requests == ["firefox", "edge"]
    assert registry.discarded == ["firefox"]


def test_launch_failure_detection_matches_playwright_error():
    assert browser_control_module._is_browser_launch_failure(
        RuntimeError("BrowserType.launch_persistent_context: Failed to launch the browser process")
    )


def test_real_chromium_profiles_are_opt_in(monkeypatch):
    monkeypatch.delenv("MICA_USE_REAL_BROWSER_PROFILE", raising=False)
    assert browser_control_module._use_real_chromium_profile() is False

    monkeypatch.setenv("MICA_USE_REAL_BROWSER_PROFILE", "1")
    assert browser_control_module._use_real_chromium_profile() is True
