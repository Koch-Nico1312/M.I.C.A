"""
Tests for the memory backup system.
"""

import pytest
import tempfile
import json
from pathlib import Path
import time

from memory.memory_backup import MemoryBackupManager, get_backup_manager


@pytest.fixture
def temp_backup_manager():
    """Create a temporary backup manager for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_dir = Path(tmpdir) / "backups"
        memory_file = Path(tmpdir) / "memory.json"
        
        # Create a test memory file
        memory_data = {"identity": {"name": "Test User"}}
        memory_file.write_text(json.dumps(memory_data), encoding="utf-8")
        
        manager = MemoryBackupManager(
            memory_path=memory_file,
            backup_dir=backup_dir,
            max_backups=5,
            backup_interval_hours=0.01  # Very short for testing
        )
        yield manager


def test_backup_manager_initialization(temp_backup_manager):
    """Test that backup manager initializes correctly."""
    assert temp_backup_manager.backup_dir.exists()
    assert temp_backup_manager.memory_path.exists()


def test_create_backup(temp_backup_manager):
    """Test creating a backup."""
    backup_path = temp_backup_manager.create_backup(reason="test")
    assert backup_path.exists()
    assert "test" in backup_path.name


def test_list_backups(temp_backup_manager):
    """Test listing backups."""
    temp_backup_manager.create_backup(reason="test1")
    temp_backup_manager.create_backup(reason="test2")
    
    backups = temp_backup_manager.list_backups()
    assert len(backups) >= 2
    
    # Check that metadata is included
    for backup in backups:
        assert "backup_path" in backup
        assert "timestamp" in backup


def test_restore_backup(temp_backup_manager):
    """Test restoring from backup."""
    # Create a backup
    backup_path = temp_backup_manager.create_backup(reason="before_change")
    
    # Modify the memory file
    new_data = {"identity": {"name": "Changed Name"}}
    temp_backup_manager.memory_path.write_text(json.dumps(new_data), encoding="utf-8")
    
    # Restore from backup
    success = temp_backup_manager.restore_backup(backup_path, verify=False)
    assert success is True
    
    # Verify restoration
    restored_data = json.loads(temp_backup_manager.memory_path.read_text(encoding="utf-8"))
    assert restored_data["identity"]["name"] == "Test User"


def test_restore_latest(temp_backup_manager):
    """Test restoring from the latest backup."""
    temp_backup_manager.create_backup(reason="latest")
    
    # Modify memory
    new_data = {"identity": {"name": "Changed"}}
    temp_backup_manager.memory_path.write_text(json.dumps(new_data), encoding="utf-8")
    
    # Restore latest
    success = temp_backup_manager.restore_latest(verify=False)
    assert success is True


def test_verify_memory_integrity(temp_backup_manager):
    """Test memory integrity verification."""
    is_valid, message = temp_backup_manager.verify_memory_integrity()
    assert is_valid is True
    assert "valid" in message.lower()


def test_verify_corrupted_memory(temp_backup_manager):
    """Test detection of corrupted memory."""
    # Corrupt the memory file
    temp_backup_manager.memory_path.write_text("invalid json", encoding="utf-8")
    
    is_valid, message = temp_backup_manager.verify_memory_integrity()
    assert is_valid is False
    assert "corrupted" in message.lower() or "invalid" in message.lower()


def test_backup_rotation(temp_backup_manager):
    """Test automatic backup rotation."""
    # Create more backups than max_backups
    for i in range(10):
        temp_backup_manager.create_backup(reason=f"backup_{i}")
    
    backups = temp_backup_manager.list_backups()
    # Should not exceed max_backups
    assert len(backups) <= temp_backup_manager.max_backups


def test_emergency_recovery(temp_backup_manager):
    """Test emergency recovery mechanism."""
    # Create a backup first
    temp_backup_manager.create_backup(reason="emergency_test")
    
    # Corrupt memory
    temp_backup_manager.memory_path.write_text("corrupted", encoding="utf-8")
    
    # Attempt emergency recovery
    success = temp_backup_manager.emergency_recovery()
    assert success is True
    
    # Verify recovery
    is_valid, _ = temp_backup_manager.verify_memory_integrity()
    assert is_valid is True


def test_global_backup_manager():
    """Test global backup manager instance."""
    manager1 = get_backup_manager()
    manager2 = get_backup_manager()
    # Note: These might be different instances if MEMORY_PATH differs
    assert manager1 is not None
    assert manager2 is not None
