from agent.task_pipeline import TaskPipelineManager


def test_pipeline_advances_steps_and_records_verification(tmp_path):
    manager = TaskPipelineManager(path=tmp_path / "pipelines.json")
    pipeline = manager.create_pipeline("Build feature", steps=["Plan", "Implement", "Verify"])

    assert pipeline.steps[0].role == "planner"
    assert pipeline.steps[0].expected_output
    assert pipeline.checkpoints[0].status == "created"

    first = manager.advance(pipeline.id, note="Plan done")
    assert first["steps"][0]["status"] == "completed"
    assert first["steps"][0]["verification"][0]["status"] == "passed"
    assert first["checkpoints"][-1]["status"] == "running"
    assert first["status"] == "running"

    manager.advance(pipeline.id, note="Implementation done")
    completed = manager.advance(pipeline.id, note="Verified")
    assert completed["status"] == "completed"


def test_pipeline_pause_blocks_advance(tmp_path):
    manager = TaskPipelineManager(path=tmp_path / "pipelines.json")
    pipeline = manager.create_pipeline("Review files", steps=["Inspect"])

    manager.pause(pipeline.id)
    try:
        manager.advance(pipeline.id)
    except ValueError as exc:
        assert "paused" in str(exc)
    else:
        raise AssertionError("paused pipeline advanced")


def test_pipeline_applies_and_enforces_personal_budget(tmp_path):
    manager = TaskPipelineManager(path=tmp_path / "pipelines.json")
    pipeline = manager.create_pipeline(
        "Bounded work", steps=["One", "Two", "Three"],
        budget={"max_steps": 2, "max_minutes": 60, "max_agent_calls": 1, "stop_on_limit": True},
    )

    assert len(pipeline.steps) == 2
    first = manager.advance(pipeline.id)
    assert first["budget_usage"]["agent_calls"] == 1
    stopped = manager.advance(pipeline.id)
    assert stopped["status"] == "budget_exceeded"
    assert stopped["checkpoints"][-1]["status"] == "budget_exceeded"


def test_pipeline_duplicate_and_rerun_keep_origin_and_reset_progress(tmp_path):
    manager = TaskPipelineManager(path=tmp_path / "pipelines.json")
    source = manager.create_pipeline("Repeatable", steps=["Plan", "Build"])
    manager.advance(source.id)

    duplicate = manager.clone(source.id, "duplicate")
    rerun = manager.clone(source.id, "rerun")

    assert duplicate["origin_id"] == source.id
    assert duplicate["origin_relation"] == "duplicate"
    assert all(step["status"] == "pending" for step in duplicate["steps"])
    assert rerun["origin_relation"] == "rerun"
    assert rerun["checkpoints"][-1]["status"] == "rerun"

    manager.delete(duplicate["id"])
    assert manager.get_pipeline(duplicate["id"]) is None


def test_retry_and_rollback_preserve_history(tmp_path):
    manager = TaskPipelineManager(path=tmp_path / "pipelines.json")
    pipeline = manager.create_pipeline("Recoverable", steps=["Plan", "Build", "Verify"])
    manager.advance(pipeline.id, "plan complete")
    manager.verify_step(pipeline.id, "step-2", "failed", "build broke")

    retried = manager.retry_step(pipeline.id, "step-2", "fixed dependency")
    assert retried["status"] == "ready"
    assert retried["steps"][1]["status"] == "pending"
    assert retried["steps"][1]["verification"][-1]["status"] == "retry"
    assert retried["checkpoints"][-1]["status"] == "retry"

    manager.advance(pipeline.id, "build complete")
    rolled_back = manager.rollback_to_step(pipeline.id, "step-1", "rework implementation")
    assert rolled_back["steps"][0]["status"] == "completed"
    assert rolled_back["steps"][1]["status"] == "pending"
    assert rolled_back["checkpoints"][-1]["status"] == "rollback"
