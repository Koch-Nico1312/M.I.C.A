from __future__ import annotations

import asyncio


def test_live_event_bus_resumes_from_sequence():
    from core.live_events import LiveEventBus

    bus = LiveEventBus(max_events=3)
    first = bus.publish("state", {"state": "THINKING"})
    bus.publish("state", {"state": "LISTENING"})

    events = bus.events_after(first["id"])

    assert [event["payload"]["state"] for event in events] == ["LISTENING"]


def test_adaptive_tool_router_keeps_relevant_and_required_tools():
    from core.tool_router import AdaptiveToolRouter

    declarations = [
        {"name": f"tool_{index}", "description": "generic operation"} for index in range(12)
    ]
    declarations[8] = {"name": "file_controller", "description": "read and write files"}
    router = AdaptiveToolRouter(minimum_tools=3, maximum_tools=5)

    selected = router.select("please read this file", declarations, always_include=["tool_11"])
    names = {item["name"] for item in selected}

    assert "file_controller" in names
    assert "tool_11" in names
    assert 3 <= len(selected) <= 5


def test_task_graph_respects_dependencies_and_parallelizes_ready_steps():
    from core.task_graph import TaskGraphExecutor

    executor = TaskGraphExecutor(max_parallel=3)
    graph = executor.create(
        [
            {"id": "a", "tool": "a", "parallel_safe": True},
            {"id": "b", "tool": "b", "parallel_safe": True},
            {"id": "c", "tool": "c", "depends_on": ["a", "b"]},
        ]
    )
    timeline = []

    async def runner(name, _args):
        timeline.append((name, "start"))
        await asyncio.sleep(0.01)
        timeline.append((name, "end"))
        return {"success": True, "result": name}

    result = asyncio.run(executor.execute(graph["id"], runner))

    assert result["status"] == "completed"
    assert timeline.index(("c", "start")) > timeline.index(("a", "end"))
    assert timeline.index(("c", "start")) > timeline.index(("b", "end"))


def test_teach_mode_records_safe_workflow(tmp_path):
    from core.teach_mode import TeachMode

    manager = TeachMode(tmp_path / "teach.json")
    manager.start("Research")
    manager.record("web_search", {"query": "M.I.C.A"})
    lesson = manager.finish()

    assert lesson["status"] == "ready"
    assert manager.snapshot()["items"][0]["steps"][0]["tool"] == "web_search"


def test_session_messages_use_small_journal_and_replay(tmp_path):
    from core.session_manager import SessionContextManager

    path = tmp_path / "chat_history.json"
    manager = SessionContextManager(history_path=path)
    manager.record_user_message("hello")
    snapshot_size = path.stat().st_size
    journal = path.with_suffix(".jsonl")

    assert journal.exists()
    assert journal.stat().st_size < snapshot_size

    replayed = SessionContextManager(history_path=path)
    assert replayed.get_current_messages()[-1]["content"] == "hello"
    manager.flush()
    replayed.flush()


def test_action_history_uses_single_jsonl_suffix(tmp_path):
    from core.action_history import ActionHistory

    history = ActionHistory(tmp_path / "actions.json")

    assert history.journal_file.name == "actions.jsonl"
    history.close()


def test_model_runner_routes_large_function_catalog(monkeypatch):
    from core.model_runner import ModelCall, ModelRunner

    runner = ModelRunner(provider_clients={})
    declarations = [
        {"name": f"tool_{index}", "description": "generic"} for index in range(20)
    ]
    declarations[15] = {"name": "web_search", "description": "search the web"}
    call = ModelCall(
        prompt="search the web",
        tools=[{"function_declarations": declarations}],
    )

    routed = runner._route_call_tools(call)

    selected = routed.tools[0]["function_declarations"]
    assert len(selected) <= 10
    assert any(item["name"] == "web_search" for item in selected)


def test_live_catalog_uses_tool_gateway_instead_of_full_schema():
    from core.jarvis_live import MicaLive

    class Config:
        def get(self, key, default=None):
            return True if key == "performance.contextual_live_tools" else default

    class Plugins:
        def get_tool_declarations(self):
            return []

    mica = object.__new__(MicaLive)
    mica.config = Config()
    mica.plugin_manager = Plugins()

    catalog = mica._build_tool_declarations()
    names = {item["name"] for item in catalog}

    assert {"find_tools", "run_tool", "open_app", "file_controller"} <= names
    assert len(catalog) < len(mica._all_tool_declarations)


def test_dashboard_section_deduplicates_nested_builds():
    from ui_bridge import _dashboard_section

    class Example:
        def __init__(self):
            import threading

            self._dashboard_build_local = threading.local()
            self.calls = 0

        @_dashboard_section
        def section(self):
            self.calls += 1
            return {"value": self.calls}

    example = Example()
    example._dashboard_build_local.sections = {}

    assert example.section() == example.section()
    assert example.calls == 1
