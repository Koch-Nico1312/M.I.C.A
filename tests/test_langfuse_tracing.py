def test_langfuse_trace_disabled_is_noop(monkeypatch):
    from core.langfuse_tracing import trace_tool_execution

    monkeypatch.setenv("LANGFUSE_ENABLED", "false")

    with trace_tool_execution("demo", {"token": "secret"}) as span:
        span.update(output="ok", metadata={"success": True})
