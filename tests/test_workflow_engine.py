"""
Tests for core.workflow_engine module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json


class TestWorkflowEngine:
    """Test cases for WorkflowEngine class."""

    @pytest.fixture
    def workflow_engine(self):
        """Create a fresh WorkflowEngine instance for testing."""
        from core.workflow_engine import WorkflowEngine
        return WorkflowEngine(max_concurrent_workflows=2)

    def test_workflow_engine_initialization(self, workflow_engine):
        """Test WorkflowEngine initialization."""
        assert workflow_engine is not None
        assert hasattr(workflow_engine, 'create_workflow')
        assert hasattr(workflow_engine, 'submit_workflow')
        assert hasattr(workflow_engine, 'get_workflow')

    def test_create_workflow(self, workflow_engine):
        """Test creating a new workflow."""
        steps = [
            {"name": "Step 1", "action": "test_action", "parameters": {}},
            {"name": "Step 2", "action": "test_action", "parameters": {}}
        ]
        
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        
        assert workflow is not None
        assert workflow.name == "Test Workflow"
        assert len(workflow.steps) == 2

    def test_submit_workflow(self, workflow_engine):
        """Test submitting a workflow for execution."""
        steps = [{"name": "Step 1", "action": "test_action", "parameters": {}}]
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        
        workflow_id = workflow_engine.submit_workflow(workflow)
        
        assert workflow_id is not None
        assert workflow_id in workflow_engine.workflows

    def test_get_workflow(self, workflow_engine):
        """Test retrieving a workflow by ID."""
        steps = [{"name": "Step 1", "action": "test_action", "parameters": {}}]
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        workflow_id = workflow_engine.submit_workflow(workflow)
        
        retrieved = workflow_engine.get_workflow(workflow_id)
        
        assert retrieved is not None
        assert retrieved.workflow_id == workflow_id

    def test_pause_workflow(self, workflow_engine):
        """Test pausing a running workflow."""
        steps = [{"name": "Step 1", "action": "test_action", "parameters": {}}]
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        workflow_id = workflow_engine.submit_workflow(workflow)
        workflow.status = workflow_engine.WorkflowStatus.RUNNING
        
        result = workflow_engine.pause_workflow(workflow_id)
        
        assert result is True
        assert workflow.status == workflow_engine.WorkflowStatus.PAUSED

    def test_resume_workflow(self, workflow_engine):
        """Test resuming a paused workflow."""
        steps = [{"name": "Step 1", "action": "test_action", "parameters": {}}]
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        workflow_id = workflow_engine.submit_workflow(workflow)
        workflow.status = workflow_engine.WorkflowStatus.PAUSED
        
        result = workflow_engine.resume_workflow(workflow_id)
        
        assert result is True
        assert workflow.status == workflow_engine.WorkflowStatus.RUNNING

    def test_cancel_workflow(self, workflow_engine):
        """Test cancelling a workflow."""
        steps = [{"name": "Step 1", "action": "test_action", "parameters": {}}]
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        workflow_id = workflow_engine.submit_workflow(workflow)
        
        result = workflow_engine.cancel_workflow(workflow_id)
        
        assert result is True
        assert workflow.status == workflow_engine.WorkflowStatus.CANCELLED

    def test_workflow_statistics(self, workflow_engine):
        """Test getting workflow engine statistics."""
        stats = workflow_engine.get_statistics()
        
        assert 'total_workflows' in stats
        assert 'queued' in stats
        assert 'running' in stats
        assert 'completed' in stats

    def test_workflow_persistence(self, workflow_engine):
        """Test workflow persistence to disk."""
        steps = [{"name": "Step 1", "action": "test_action", "parameters": {}}]
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        workflow_id = workflow_engine.submit_workflow(workflow)
        
        # Save workflow
        result = workflow_engine.save_workflow(workflow_id)
        
        assert result is True

    def test_delete_workflow(self, workflow_engine):
        """Test deleting a workflow."""
        steps = [{"name": "Step 1", "action": "test_action", "parameters": {}}]
        workflow = workflow_engine.create_workflow(
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=steps
        )
        workflow_id = workflow_engine.submit_workflow(workflow)
        
        result = workflow_engine.delete_workflow(workflow_id)
        
        assert result is True
        assert workflow_id not in workflow_engine.workflows


class TestWorkflowStep:
    """Test cases for WorkflowStep class."""

    @pytest.fixture
    def workflow_step(self):
        """Create a fresh WorkflowStep instance for testing."""
        from core.workflow_engine import WorkflowStep
        return WorkflowStep(
            step_id="step_1",
            name="Test Step",
            action="test_action",
            parameters={"param": "value"}
        )

    def test_workflow_step_initialization(self, workflow_step):
        """Test WorkflowStep initialization."""
        assert workflow_step.step_id == "step_1"
        assert workflow_step.name == "Test Step"
        assert workflow_step.action == "test_action"
        assert workflow_step.status == workflow_step.StepStatus.PENDING

    def test_workflow_step_dependencies(self, workflow_step):
        """Test workflow step dependencies."""
        workflow_step.dependencies = ["step_0"]
        
        assert "step_0" in workflow_step.dependencies

    def test_workflow_step_retry_logic(self, workflow_step):
        """Test workflow step retry logic."""
        workflow_step.max_retries = 3
        workflow_step.retry_on_failure = True
        
        # Simulate failure and retry
        workflow_step.status = workflow_step.StepStatus.FAILED
        workflow_step.retry_count += 1
        
        assert workflow_step.retry_count == 1
        assert workflow_step.retry_count < workflow_step.max_retries


class TestWorkflowEngineErrorHandling:
    """Test error handling in WorkflowEngine."""

    @pytest.fixture
    def workflow_engine(self):
        """Create a fresh WorkflowEngine instance for testing."""
        from core.workflow_engine import WorkflowEngine
        return WorkflowEngine(max_concurrent_workflows=2)

    def test_invalid_workflow_id(self, workflow_engine):
        """Test handling of invalid workflow ID."""
        result = workflow_engine.get_workflow("invalid_id")
        assert result is None

    def test_pause_nonexistent_workflow(self, workflow_engine):
        """Test pausing a non-existent workflow."""
        result = workflow_engine.pause_workflow("invalid_id")
        assert result is False

    def test_step_execution_failure(self, workflow_engine):
        """Test handling of step execution failure."""
        from core.workflow_engine import WorkflowStep, Workflow
        
        step = WorkflowStep(
            step_id="step_1",
            name="Failing Step",
            action="failing_action",
            parameters={}
        )
        step.status = step.StepStatus.FAILED
        step.error = "Test error"
        
        workflow = Workflow(
            workflow_id="workflow_1",
            name="Test Workflow",
            goal="Test goal",
            description="Test description",
            steps=[step]
        )
        
        assert step.status == step.StepStatus.FAILED
        assert step.error is not None


class TestWorkflowEngineIntegration:
    """Integration tests for WorkflowEngine."""

    @patch('core.workflow_engine.get_approval_flow')
    @patch('core.workflow_engine.check_action')
    def test_workflow_with_approval(self, mock_check, mock_approval):
        """Test workflow execution with approval flow."""
        from core.workflow_engine import WorkflowEngine
        
        mock_approval.return_value = Mock()
        mock_approval.return_value.check_and_request_approval.return_value = (True, "Approved")
        mock_check.return_value = (True, "Allowed")
        
        engine = WorkflowEngine(max_concurrent_workflows=2)
        
        steps = [
            {
                "name": "High Risk Step",
                "action": "risky_action",
                "parameters": {},
                "risk_level": "high",
                "requires_confirmation": True
            }
        ]
        
        workflow = engine.create_workflow(
            name="Approval Workflow",
            goal="Test approval flow",
            description="Test workflow with approval",
            steps=steps
        )
        
        assert workflow is not None
        assert len(workflow.steps) == 1
        assert workflow.steps[0].risk_level == "high"

    def test_workflow_with_dependencies(self):
        """Test workflow execution with step dependencies."""
        from core.workflow_engine import WorkflowEngine
        
        engine = WorkflowEngine(max_concurrent_workflows=2)
        
        steps = [
            {
                "name": "Step 1",
                "action": "action1",
                "parameters": {},
                "dependencies": []
            },
            {
                "name": "Step 2",
                "action": "action2",
                "parameters": {},
                "dependencies": ["workflow_step_0"]
            },
            {
                "name": "Step 3",
                "action": "action3",
                "parameters": {},
                "dependencies": ["workflow_step_1"]
            }
        ]
        
        workflow = engine.create_workflow(
            name="Dependency Workflow",
            goal="Test dependencies",
            description="Test workflow with step dependencies",
            steps=steps
        )
        
        # Verify dependency structure
        assert len(workflow.steps) == 3
        assert len(workflow.steps[0].dependencies) == 0
        assert len(workflow.steps[1].dependencies) == 1
        assert len(workflow.steps[2].dependencies) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
