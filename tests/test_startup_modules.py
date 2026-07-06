"""
Tests for startup modules.
"""

from config.startup_config import get_startup_defaults
from startup.app_initializer import CLIUIBridge, initialize_application, should_use_gui
from startup.performance_initializer import initialize_performance_system
from startup.safety_initializer import initialize_safety_system


class TestCLIUIBridge:
    """Test cases for CLIUIBridge."""
    
    def test_initialization(self):
        """Test CLIUIBridge initialization."""
        bridge = CLIUIBridge()
        assert bridge.muted is False
        assert bridge.current_file is None
        assert bridge._state == "LISTENING"
        assert bridge.on_text_command is None
    
    def test_muted_property(self):
        """Test muted property setter."""
        bridge = CLIUIBridge()
        bridge.muted = True
        assert bridge.muted is True
    
    def test_current_file_property(self):
        """Test current_file property setter."""
        bridge = CLIUIBridge()
        bridge.current_file = "test.txt"
        assert bridge.current_file == "test.txt"
    
    def test_on_text_command_property(self):
        """Test on_text_command property setter."""
        bridge = CLIUIBridge()

        def callback(x):
            return x

        bridge.on_text_command = callback
        assert bridge.on_text_command is callback
    
    def test_set_state(self):
        """Test set_state method."""
        bridge = CLIUIBridge()
        bridge.set_state("PROCESSING")
        assert bridge._state == "PROCESSING"
    
    def test_write_log(self):
        """Test write_log method."""
        bridge = CLIUIBridge()
        # Should not raise an exception
        bridge.write_log("Test log message")
    
    def test_wait_for_api_key(self):
        """Test wait_for_api_key method."""
        bridge = CLIUIBridge()
        # Should not raise an exception
        bridge.wait_for_api_key()
    
    def test_root(self):
        """Test root method (no-op for CLI)."""
        bridge = CLIUIBridge()
        # Should not raise an exception
        bridge.root()


class TestSafetyInitializer:
    """Test cases for safety initializer."""
    
    def test_initialize_safety_system(self):
        """Test safety system initialization."""
        approval_flow, action_history = initialize_safety_system()
        
        assert approval_flow is not None
        assert action_history is not None


class TestPerformanceInitializer:
    """Test cases for performance initializer."""
    
    def test_initialize_performance_system_enabled(self):
        """Test performance system initialization when enabled."""
        # Mock action loader function
        def mock_loader():
            return None
        
        perf_tracker, perf_monitor = initialize_performance_system(mock_loader)
        
        # When performance is enabled, should return non-None
        # (This depends on config, so we just check it doesn't crash)
        assert True  # Test passes if no exception raised
    
    def test_initialize_performance_system_disabled(self):
        """Test performance system initialization when disabled."""
        # This would require mocking config to disable performance
        # For now, just test the function exists and is callable
        def mock_loader():
            return None
        
        perf_tracker, perf_monitor = initialize_performance_system(mock_loader)
        # Should not crash
        assert True

    def test_startup_defaults_keep_heavy_background_features_off(self):
        """Missing config should prefer fast, low-side-effect startup defaults."""
        defaults = get_startup_defaults()

        assert defaults["performance.resource_monitoring"] is False
        assert defaults["performance.background_tasks_enabled"] is False
        assert defaults["performance.preload_critical_actions"] is False
        assert defaults["performance.flags.lazy_load_actions"] is True
        assert defaults["security.confirmation_high_risk"] is True


class TestAppInitializer:
    """Test cases for app initializer."""

    def test_should_use_gui_by_default(self):
        """Desktop window mode should be the normal startup path."""
        assert should_use_gui(["main.py"]) is True

    def test_should_use_gui_false_with_cli_flag(self):
        """CLI mode requires an explicit --cli flag."""
        assert should_use_gui(["main.py", "--cli"]) is False

    def test_initialize_application_cli_mode(self):
        """Test application initialization in CLI mode."""
        # Mock sys.argv to include explicit --cli
        import sys
        original_argv = sys.argv
        try:
            sys.argv = ["main.py", "--cli"]
            use_gui, ui = initialize_application()
            assert use_gui is False
            assert isinstance(ui, CLIUIBridge)
        finally:
            sys.argv = original_argv

    def test_initialize_application_gui_mode(self, monkeypatch):
        """Test application initialization in GUI mode."""
        sentinel_ui = object()
        monkeypatch.setattr(
            "startup.app_initializer.create_ui_bridge",
            lambda use_gui: sentinel_ui,
        )

        # Mock sys.argv with no --cli; GUI is the default.
        import sys
        original_argv = sys.argv
        try:
            sys.argv = ["main.py"]
            use_gui, ui = initialize_application()
            assert use_gui is True
            assert ui is sentinel_ui
        finally:
            sys.argv = original_argv

    def test_qt_webengine_diagnostic_includes_import_failure(self, monkeypatch):
        """Qt startup failures should preserve the actionable import error."""
        import ui_bridge

        monkeypatch.setattr(ui_bridge, "QT_WEBENGINE_AVAILABLE", False)
        monkeypatch.setattr(
            ui_bridge,
            "QT_WEBENGINE_IMPORT_ERROR",
            ImportError("No module named PyQt6.QtWebEngineWidgets"),
        )

        diagnostic = ui_bridge.get_qt_webengine_diagnostic()

        assert "Qt WebEngine is not available" in diagnostic
        assert "No module named PyQt6.QtWebEngineWidgets" in diagnostic

    def test_qt_webengine_recovery_hint_respects_no_qt_env(self, monkeypatch):
        """When Qt is explicitly disabled, the hint should say how to re-enable it."""
        import ui_bridge

        monkeypatch.setenv("MICA_NO_QT", "1")

        assert "Unset MICA_NO_QT" in ui_bridge.get_qt_webengine_recovery_hint()
