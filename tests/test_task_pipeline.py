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
