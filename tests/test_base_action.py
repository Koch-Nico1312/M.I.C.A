"""
Tests for the base action interface.
"""

import pytest

from actions.base_action import (
    ActionMetadata,
    ActionPermission,
    ActionRegistry,
    BaseAction,
    get_action_registry,
)


class TestActionMetadata:
    """Test cases for ActionMetadata."""
    
    def test_basic_metadata(self):
        """Test basic metadata creation."""
        metadata = ActionMetadata(
            name="test_action",
            description="Test action description"
        )
        assert metadata.name == "test_action"
        assert metadata.description == "Test action description"
        assert metadata.version == "1.0.0"
        assert metadata.permission == ActionPermission.MEDIUM
        assert metadata.enabled is True
    
    def test_metadata_with_custom_values(self):
        """Test metadata with custom values."""
        metadata = ActionMetadata(
            name="test_action",
            description="Test action description",
            version="2.0.0",
            permission=ActionPermission.HIGH,
            dependencies=["dep1", "dep2"],
            category="test",
            enabled=False
        )
        assert metadata.version == "2.0.0"
        assert metadata.permission == ActionPermission.HIGH
        assert metadata.dependencies == ["dep1", "dep2"]
        assert metadata.category == "test"
        assert metadata.enabled is False


class TestBaseAction:
    """Test cases for BaseAction."""
    
    def test_abstract_class_cannot_be_instantiated(self):
        """Test that BaseAction cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAction()
    
    def test_concrete_action_implementation(self):
        """Test concrete action implementation."""
        
        class TestAction(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(
                    name="test_action",
                    description="Test action"
                )
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        action = TestAction()
        assert action.metadata.name == "test_action"
        assert action.execute({}) == "executed"
        assert action.validate_parameters({}) is True
    
    def test_initialization_and_cleanup(self):
        """Test action initialization and cleanup."""
        
        class TestAction(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="test", description="Test")
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        action = TestAction()
        assert not action._initialized
        
        action.initialize()
        assert action._initialized
        
        action.cleanup()
        assert not action._initialized
    
    def test_get_tool_declaration(self):
        """Test getting tool declaration from action."""
        
        class TestAction(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="test_action", description="Test action")
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
            
            def get_required_parameters(self):
                return ["param1"]
            
            def get_optional_parameters(self):
                return {"param2": "default"}
        
        action = TestAction()
        declaration = action.get_tool_declaration()
        
        assert declaration["name"] == "test_action"
        assert declaration["description"] == "Test action"
        assert "param1" in declaration["parameters"]["required"]
        assert "param2" in declaration["parameters"]["properties"]


class TestActionRegistry:
    """Test cases for ActionRegistry."""
    
    def test_register_and_get_action(self):
        """Test registering and getting an action."""
        registry = ActionRegistry()
        
        class TestAction(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="test", description="Test")
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        action = TestAction()
        registry.register(action)
        
        retrieved = registry.get("test")
        assert retrieved is action
    
    def test_unregister_action(self):
        """Test unregistering an action."""
        registry = ActionRegistry()
        
        class TestAction(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="test", description="Test")
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        action = TestAction()
        registry.register(action)
        assert registry.get("test") is action
        
        registry.unregister("test")
        assert registry.get("test") is None
    
    def test_get_all_actions(self):
        """Test getting all registered actions."""
        registry = ActionRegistry()
        
        class Action1(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="action1", description="Action 1")
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        class Action2(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="action2", description="Action 2")
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        registry.register(Action1())
        registry.register(Action2())
        
        all_actions = registry.get_all()
        assert len(all_actions) == 2
    
    def test_get_enabled_actions(self):
        """Test getting only enabled actions."""
        registry = ActionRegistry()
        
        class EnabledAction(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="enabled", description="Enabled")
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        class DisabledAction(BaseAction):
            @property
            def metadata(self):
                return ActionMetadata(name="disabled", description="Disabled", enabled=False)
            
            def execute(self, parameters):
                return "executed"
            
            def validate_parameters(self, parameters):
                return True
        
        registry.register(EnabledAction())
        registry.register(DisabledAction())
        
        enabled = registry.get_enabled()
        assert len(enabled) == 1
        assert enabled[0].metadata.name == "enabled"


class TestGlobalActionRegistry:
    """Test cases for global action registry."""
    
    def test_get_action_registry_returns_same_instance(self):
        """Test that get_action_registry returns the same instance."""
        registry1 = get_action_registry()
        registry2 = get_action_registry()
        
        assert registry1 is registry2
