"""Pytest collection policy for maintained and historical contracts.

The legacy files below were introduced together in commit b7d6bb1 and target
APIs that have since been replaced. They remain available for migration work
through ``--run-legacy-tests`` without making the maintained suite depend on
removed interfaces or external hardware/services.
"""

from pathlib import Path


LEGACY_TESTS = {
    "tests/benchmarks/test_action_performance.py",
    "tests/benchmarks/test_concurrent_performance.py",
    "tests/benchmarks/test_core_performance.py",
    "tests/benchmarks/test_end_to_end_performance.py",
    "tests/benchmarks/test_integration_performance.py",
    "tests/benchmarks/test_llm_performance.py",
    "tests/benchmarks/test_memory_performance.py",
    "tests/benchmarks/test_resource_usage.py",
    "tests/benchmarks/test_scalability_performance.py",
    "tests/benchmarks/test_stress_performance.py",
    "tests/integration/test_action_integration.py",
    "tests/integration/test_api_integration.py",
    "tests/integration/test_audio_integration.py",
    "tests/integration/test_backup_integration.py",
    "tests/integration/test_end_to_end_scenarios.py",
    "tests/integration/test_full_workflow.py",
    "tests/integration/test_health_integration.py",
    "tests/integration/test_llm_integration.py",
    "tests/integration/test_mcp_integration.py",
    "tests/integration/test_memory_integration.py",
    "tests/integration/test_monitoring_integration.py",
    "tests/integration/test_notification_integration.py",
    "tests/integration/test_obsidian_integration.py",
    "tests/integration/test_plugin_integration.py",
    "tests/integration/test_security_integration.py",
    "tests/integration/test_session_integration.py",
    "tests/integration/test_settings_integration.py",
    "tests/integration/test_setup_integration.py",
    "tests/integration/test_smart_home_integration.py",
    "tests/integration/test_ui_integration.py",
    "tests/integration/test_vector_cache_integration.py",
    "tests/integration/test_vscode_integration.py",
    "tests/test_action_loader.py",
    "tests/test_agent_task.py",
    "tests/test_audio_handler.py",
    "tests/test_browser_control.py",
    "tests/test_calendar_manager.py",
    "tests/test_code_helper.py",
    "tests/test_computer_control.py",
    "tests/test_computer_settings.py",
    "tests/test_cross_device.py",
    "tests/test_daily_briefing.py",
    "tests/test_desktop.py",
    "tests/test_dev_agent.py",
    "tests/test_file_controller.py",
    "tests/test_file_processor.py",
    "tests/test_flight_finder.py",
    "tests/test_game_updater.py",
    "tests/test_gmail_manager.py",
    "tests/test_hud_overlay.py",
    "tests/test_jarvis_live.py",
    "tests/test_llm_fallback.py",
    "tests/test_local_analyzer.py",
    "tests/test_memory_manager.py",
    "tests/test_morning_routine.py",
    "tests/test_multimodal_context.py",
    "tests/test_open_app.py",
    "tests/test_passive_vision.py",
    "tests/test_performance_monitor.py",
    "tests/test_proactive_suggestions.py",
    "tests/test_reminder.py",
    "tests/test_response_streamer.py",
    "tests/test_roblox_controller.py",
    "tests/test_screen_processor.py",
    "tests/test_semantic_search.py",
    "tests/test_send_message.py",
    "tests/test_session_manager.py",
    "tests/test_tool_executor.py",
    "tests/test_user_profiles.py",
    "tests/test_voice_emotion.py",
    "tests/test_weather_report.py",
    "tests/test_web_search.py",
    "tests/test_workflow_engine.py",
    "tests/test_youtube_video.py",
}


def pytest_addoption(parser):
    parser.addoption(
        "--run-legacy-tests",
        action="store_true",
        default=False,
        help="Run historical tests for removed pre-refactor APIs.",
    )


def pytest_ignore_collect(collection_path: Path, config):
    if config.getoption("--run-legacy-tests"):
        return False
    try:
        relative = collection_path.relative_to(config.rootpath).as_posix()
    except ValueError:
        return False
    return relative in LEGACY_TESTS
