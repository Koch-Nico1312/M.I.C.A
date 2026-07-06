"""
Tests for core.cross_device module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestCrossDevice:
    """Test cases for CrossDevice class."""

    @pytest.fixture
    def cross_device(self):
        """Create a fresh CrossDevice instance for testing."""
        from core.cross_device import CrossDevice
        return CrossDevice()

    def test_cross_device_initialization(self, cross_device):
        """Test CrossDevice initialization."""
        assert cross_device is not None
        assert hasattr(cross_device, 'register_device')
        assert hasattr(cross_device, 'handoff_session')
        assert hasattr(cross_device, 'get_devices')

    def test_register_device(self, cross_device):
        """Test registering a new device."""
        device_id = cross_device.register_device(
            device_name="Test Device",
            device_type="mobile",
            capabilities=["voice", "text"]
        )
        
        assert device_id is not None
        assert device_id in cross_device.devices

    def test_get_device(self, cross_device):
        """Test getting device information."""
        device_id = cross_device.register_device(
            device_name="Test Device",
            device_type="mobile",
            capabilities=["voice"]
        )
        
        device = cross_device.get_device(device_id)
        
        assert device is not None
        assert device['device_name'] == "Test Device"

    def test_unregister_device(self, cross_device):
        """Test unregistering a device."""
        device_id = cross_device.register_device(
            device_name="Test Device",
            device_type="mobile",
            capabilities=["voice"]
        )
        
        cross_device.unregister_device(device_id)
        
        assert device_id not in cross_device.devices

    def test_handoff_session(self, cross_device):
        """Test session handoff between devices."""
        # Register devices
        device1_id = cross_device.register_device("Device 1", "desktop", ["voice", "text"])
        device2_id = cross_device.register_device("Device 2", "mobile", ["voice"])
        
        # Create session
        session_id = cross_device.create_session(device1_id)
        
        # Handoff session
        result = cross_device.handoff_session(session_id, device1_id, device2_id)
        
        assert result is True

    def test_get_active_sessions(self, cross_device):
        """Test getting active sessions."""
        device_id = cross_device.register_device("Test Device", "mobile", ["voice"])
        session_id = cross_device.create_session(device_id)
        
        sessions = cross_device.get_active_sessions()
        
        assert len(sessions) > 0
        assert session_id in [s['session_id'] for s in sessions]

    def test_device_sync(self, cross_device):
        """Test device synchronization."""
        device1_id = cross_device.register_device("Device 1", "desktop", ["voice"])
        device2_id = cross_device.register_device("Device 2", "mobile", ["voice"])
        
        # Sync data
        sync_result = cross_device.sync_devices(device1_id, device2_id)
        
        assert sync_result is True

    def test_device_capabilities_check(self, cross_device):
        """Test checking device capabilities."""
        device_id = cross_device.register_device(
            "Test Device",
            "mobile",
            capabilities=["voice", "text", "video"]
        )
        
        has_voice = cross_device.device_has_capability(device_id, "voice")
        has_video = cross_device.device_has_capability(device_id, "video")
        has_unknown = cross_device.device_has_capability(device_id, "unknown")
        
        assert has_voice is True
        assert has_video is True
        assert has_unknown is False


class TestCrossDeviceErrorHandling:
    """Test error handling in CrossDevice."""

    @pytest.fixture
    def cross_device(self):
        """Create a fresh CrossDevice instance for testing."""
        from core.cross_device import CrossDevice
        return CrossDevice()

    def test_get_nonexistent_device(self, cross_device):
        """Test getting a non-existent device."""
        result = cross_device.get_device("invalid_id")
        assert result is None

    def test_unregister_nonexistent_device(self, cross_device):
        """Test unregistering a non-existent device."""
        result = cross_device.unregister_device("invalid_id")
        assert result is False

    def test_handoff_to_nonexistent_device(self, cross_device):
        """Test handoff to non-existent device."""
        device_id = cross_device.register_device("Device", "mobile", ["voice"])
        session_id = cross_device.create_session(device_id)
        
        result = cross_device.handoff_session(session_id, device_id, "nonexistent_device")
        assert result is False

    def test_invalid_capability_check(self, cross_device):
        """Test checking invalid capability."""
        device_id = cross_device.register_device("Device", "mobile", ["voice"])
        
        result = cross_device.device_has_capability(device_id, None)
        assert result is False


class TestCrossDeviceIntegration:
    """Integration tests for CrossDevice."""

    def test_full_handoff_workflow(self):
        """Test a full cross-device handoff workflow."""
        from core.cross_device import CrossDevice
        
        cross_device = CrossDevice()
        
        # Register devices
        desktop_id = cross_device.register_device("Desktop", "desktop", ["voice", "text", "video"])
        mobile_id = cross_device.register_device("Mobile", "mobile", ["voice", "text"])
        
        # Create session on desktop
        session_id = cross_device.create_session(desktop_id)
        cross_device.add_message_to_session(session_id, "user", "Hello M.I.C.A")
        
        # Handoff to mobile
        handoff_result = cross_device.handoff_session(session_id, desktop_id, mobile_id)
        
        assert handoff_result is True
        
        # Verify session is now on mobile
        session = cross_device.get_session(session_id)
        assert session['current_device'] == mobile_id

    def test_multi_device_sync(self):
        """Test synchronization across multiple devices."""
        from core.cross_device import CrossDevice
        
        cross_device = CrossDevice()
        
        # Register multiple devices
        device1 = cross_device.register_device("Device 1", "desktop", ["voice"])
        device2 = cross_device.register_device("Device 2", "mobile", ["voice"])
        device3 = cross_device.register_device("Device 3", "tablet", ["voice"])
        
        # Sync all devices
        sync_result = cross_device.sync_all_devices()
        
        assert sync_result is True

    def test_device_discovery(self):
        """Test automatic device discovery."""
        from core.cross_device import CrossDevice
        
        cross_device = CrossDevice()
        cross_device.enable_discovery = True
        
        # Start discovery
        cross_device.start_discovery()
        
        # Should discover devices (mocked in real implementation)
        assert cross_device.discovery_active

    def test_session_persistence_across_devices(self):
        """Test that sessions persist across devices."""
        from core.cross_device import CrossDevice
        
        cross_device = CrossDevice()
        
        # Register devices
        device1 = cross_device.register_device("Device 1", "desktop", ["voice"])
        device2 = cross_device.register_device("Device 2", "mobile", ["voice"])
        
        # Create session
        session_id = cross_device.create_session(device1)
        cross_device.add_message_to_session(session_id, "user", "Test message")
        
        # Handoff
        cross_device.handoff_session(session_id, device1, device2)
        
        # Verify messages persist
        session = cross_device.get_session(session_id)
        assert len(session['messages']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
