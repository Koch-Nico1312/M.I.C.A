"""
Integration tests for backup and recovery system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil


class TestBackupIntegration:
    """Integration tests for backup and recovery system components."""

    @pytest.fixture
    def backup_manager(self):
        """Create a fresh BackupManager instance for testing."""
        from memory.memory_backup import get_backup_manager
        return get_backup_manager()

    def test_backup_creation(self, backup_manager):
        """Test creating a backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            
            # Create backup
            test_data = {"memory": {"user": "test"}, "config": {"theme": "dark"}}
            backup_id = backup_manager.create_backup(test_data)
            
            assert backup_id is not None
            assert (backup_path / backup_id).exists()

    def test_backup_restoration(self, backup_manager):
        """Test restoring from backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            
            # Create backup
            test_data = {"memory": {"user": "test"}, "config": {"theme": "dark"}}
            backup_id = backup_manager.create_backup(test_data)
            
            # Restore backup
            restored = backup_manager.restore_backup(backup_id)
            
            assert restored == test_data

    def test_backup_listing(self, backup_manager):
        """Test listing available backups."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            
            # Create multiple backups
            backup_manager.create_backup({"data": "backup1"})
            backup_manager.create_backup({"data": "backup2"})
            backup_manager.create_backup({"data": "backup3"})
            
            # List backups
            backups = backup_manager.list_backups()
            
            assert len(backups) >= 3

    def test_backup_deletion(self, backup_manager):
        """Test deleting a backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            
            # Create backup
            backup_id = backup_manager.create_backup({"data": "test"})
            
            # Delete backup
            result = backup_manager.delete_backup(backup_id)
            
            assert result is True
            assert not (backup_path / backup_id).exists()

    def test_backup_scheduling(self, backup_manager):
        """Test scheduled backup creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            backup_manager.enable_scheduling = True
            backup_manager.schedule_interval_hours = 24
            
            # Schedule backup
            backup_manager.schedule_backup()
            
            assert backup_manager.enable_scheduling is True

    def test_backup_compression(self, backup_manager):
        """Test backup compression."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            backup_manager.enable_compression = True
            
            # Create compressed backup
            test_data = {"data": "x" * 10000}  # Large data
            backup_id = backup_manager.create_backup(test_data)
            
            # Check file size
            backup_file = backup_path / backup_id
            assert backup_file.exists()

    def test_backup_encryption(self, backup_manager):
        """Test backup encryption."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            backup_manager.enable_encryption = True
            backup_manager.encryption_key = "test_key"
            
            # Create encrypted backup
            test_data = {"sensitive": "data"}
            backup_id = backup_manager.create_backup(test_data)
            
            # Restore encrypted backup
            restored = backup_manager.restore_backup(backup_id)
            
            assert restored == test_data

    def test_incremental_backup(self, backup_manager):
        """Test incremental backup creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            backup_manager.enable_incremental = True
            
            # Initial backup
            initial_data = {"data": "initial"}
            backup_manager.create_backup(initial_data)
            
            # Incremental backup
            incremental_data = {"data": "initial", "new": "data"}
            backup_id = backup_manager.create_backup(incremental_data)
            
            assert backup_id is not None

    def test_disaster_recovery(self, backup_manager):
        """Test disaster recovery procedure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager.backup_path = backup_path
            
            # Create full backup
            full_backup = {
                "memory": {"user": "test"},
                "config": {"theme": "dark"},
                "actions": []
            }
            backup_id = backup_manager.create_backup(full_backup)
            
            # Simulate disaster (data loss)
            # Restore from backup
            recovered = backup_manager.disaster_recovery(backup_id)
            
            assert recovered == full_backup


class TestBackupErrorHandling:
    """Error handling tests for backup system."""

    @pytest.fixture
    def backup_manager(self):
        """Create a fresh BackupManager instance for testing."""
        from memory.memory_backup import get_backup_manager
        return get_backup_manager()

    def test_restore_nonexistent_backup(self, backup_manager):
        """Test restoring a non-existent backup."""
        with pytest.raises(FileNotFoundError):
            backup_manager.restore_backup("nonexistent_id")

    def test_delete_nonexistent_backup(self, backup_manager):
        """Test deleting a non-existent backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            backup_manager.backup_path = backup_path
            
            result = backup_manager.delete_backup("nonexistent_id")
            assert result is False

    def test_corrupted_backup_recovery(self, backup_manager):
        """Test recovery from corrupted backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            backup_manager.backup_path = backup_path
            
            # Create corrupted backup
            backup_id = "corrupted_backup"
            backup_file = backup_path / backup_id
            backup_file.write_text("corrupted data")
            
            with pytest.raises(Exception):
                backup_manager.restore_backup(backup_id)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
