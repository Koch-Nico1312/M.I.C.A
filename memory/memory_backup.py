"""
Memory backup and recovery system for JARVIS long-term memory.

This module provides:
- Automatic periodic backups of memory files
- Versioned backups with timestamps
- Recovery mechanism for corrupted memory
- Backup rotation to manage disk space
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import hashlib
import threading
import time

from core.logger import get_logger

logger = get_logger(__name__)


class MemoryBackupManager:
    """
    Manages automatic backups and recovery of JARVIS memory files.
    """
    
    def __init__(
        self,
        memory_path: Path,
        backup_dir: Optional[Path] = None,
        max_backups: int = 10,
        backup_interval_hours: float = 1.0
    ):
        """
        Initialize the memory backup manager.
        
        Args:
            memory_path: Path to the main memory file (long_term.json)
            backup_dir: Directory for storing backups (defaults to ./data/memory_backups)
            max_backups: Maximum number of backups to keep
            backup_interval_hours: Hours between automatic backups
        """
        self.memory_path = Path(memory_path)
        if backup_dir is None:
            backup_dir = Path("./data/memory_backups")
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_interval_hours = backup_interval_hours
        self._backup_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Memory backup manager initialized: {self.memory_path} -> {self.backup_dir}")
    
    def create_backup(self, reason: str = "manual") -> Path:
        """
        Create a backup of the current memory file.
        
        Args:
            reason: Reason for the backup (e.g., "manual", "auto", "before_update")
        
        Returns:
            Path to the created backup file
        """
        if not self.memory_path.exists():
            logger.warning(f"Memory file not found: {self.memory_path}")
            raise FileNotFoundError(f"Memory file not found: {self.memory_path}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"memory_{timestamp}_{reason}.json"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Calculate checksum for integrity verification
            checksum = self._calculate_checksum(self.memory_path)
            
            # Copy the file
            shutil.copy2(self.memory_path, backup_path)
            
            # Create metadata file
            metadata = {
                "timestamp": timestamp,
                "reason": reason,
                "checksum": checksum,
                "original_size": self.memory_path.stat().st_size,
                "backup_size": backup_path.stat().st_size
            }
            metadata_path = self.backup_dir / f"memory_{timestamp}_{reason}.meta.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Memory backup created: {backup_path} (reason: {reason})")
            self._rotate_backups()
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create memory backup: {e}")
            raise
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _rotate_backups(self):
        """Remove old backups beyond max_backups limit."""
        backups = sorted(self.backup_dir.glob("memory_*.json"))
        
        # Separate actual backups from metadata files
        backup_files = [f for f in backups if not f.name.endswith(".meta.json")]
        
        if len(backup_files) > self.max_backups:
            # Remove oldest backups
            for old_backup in backup_files[:-self.max_backups]:
                try:
                    old_backup.unlink()
                    # Also remove corresponding metadata file
                    meta_file = self.backup_dir / f"{old_backup.stem}.meta.json"
                    if meta_file.exists():
                        meta_file.unlink()
                    logger.info(f"Removed old backup: {old_backup}")
                except Exception as e:
                    logger.error(f"Failed to remove old backup {old_backup}: {e}")
    
    def list_backups(self) -> List[dict]:
        """
        List all available backups with metadata.
        
        Returns:
            List of dictionaries containing backup information
        """
        backups = []
        for meta_file in sorted(self.backup_dir.glob("memory_*.meta.json")):
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                backup_file = self.backup_dir / (meta_file.stem.replace(".meta", "") + ".json")
                metadata["backup_path"] = str(backup_file)
                metadata["exists"] = backup_file.exists()
                backups.append(metadata)
            except Exception as e:
                logger.error(f"Failed to read metadata {meta_file}: {e}")
        
        return backups
    
    def restore_backup(self, backup_path: Path, verify: bool = True) -> bool:
        """
        Restore memory from a backup file.
        
        Args:
            backup_path: Path to the backup file to restore
            verify: Whether to verify backup integrity before restoring
        
        Returns:
            True if restore was successful
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        if verify:
            # Verify checksum if metadata exists
            meta_file = self.backup_dir / f"{backup_path.stem}.meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    current_checksum = self._calculate_checksum(backup_path)
                    if current_checksum != metadata.get("checksum"):
                        logger.error(f"Backup checksum mismatch: {backup_path}")
                        return False
                except Exception as e:
                    logger.warning(f"Could not verify backup checksum: {e}")
        
        try:
            # Create a backup of current state before restoring
            if self.memory_path.exists():
                self.create_backup(reason="pre_restore")
            
            # Restore the backup
            shutil.copy2(backup_path, self.memory_path)
            logger.info(f"Memory restored from backup: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore memory from backup: {e}")
            return False
    
    def restore_latest(self, verify: bool = True) -> bool:
        """
        Restore from the most recent backup.
        
        Args:
            verify: Whether to verify backup integrity
        
        Returns:
            True if restore was successful
        """
        backups = self.list_backups()
        if not backups:
            logger.warning("No backups available for restore")
            return False
        
        latest = backups[-1]
        return self.restore_backup(Path(latest["backup_path"]), verify=verify)
    
    def verify_memory_integrity(self) -> tuple[bool, str]:
        """
        Verify the integrity of the current memory file.
        
        Returns:
            Tuple of (is_valid, message)
        """
        if not self.memory_path.exists():
            return False, "Memory file does not exist"
        
        try:
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return False, "Memory file is not a valid JSON object"
            
            # Check for required structure
            if not any(isinstance(v, dict) for v in data.values()):
                return False, "Memory file has invalid structure"
            
            return True, "Memory file is valid"
            
        except json.JSONDecodeError as e:
            return False, f"Memory file is corrupted (JSON decode error): {e}"
        except Exception as e:
            return False, f"Memory file verification failed: {e}"
    
    def start_automatic_backup(self):
        """Start automatic periodic backups in a background thread."""
        if self._backup_thread and self._backup_thread.is_alive():
            logger.warning("Automatic backup thread already running")
            return
        
        self._stop_event.clear()
        self._backup_thread = threading.Thread(
            target=self._backup_loop,
            daemon=True,
            name="MemoryBackupThread"
        )
        self._backup_thread.start()
        logger.info(f"Automatic memory backup started (interval: {self.backup_interval_hours}h)")
    
    def _backup_loop(self):
        """Background thread loop for automatic backups."""
        while not self._stop_event.is_set():
            try:
                self.create_backup(reason="auto")
            except Exception as e:
                logger.error(f"Automatic backup failed: {e}")
            
            # Wait for next backup or stop event
            self._stop_event.wait(timeout=self.backup_interval_hours * 3600)
    
    def stop_automatic_backup(self):
        """Stop automatic periodic backups."""
        if self._backup_thread and self._backup_thread.is_alive():
            self._stop_event.set()
            self._backup_thread.join(timeout=5)
            logger.info("Automatic memory backup stopped")
    
    def emergency_recovery(self) -> bool:
        """
        Attempt emergency recovery if current memory is corrupted.
        
        Returns:
            True if recovery was successful
        """
        is_valid, message = self.verify_memory_integrity()
        
        if is_valid:
            logger.info("Memory is valid, no recovery needed")
            return True
        
        logger.warning(f"Memory corruption detected: {message}")
        logger.info("Attempting emergency recovery from latest backup...")
        
        return self.restore_latest(verify=True)


# Global instance
_backup_manager: Optional[MemoryBackupManager] = None


def get_backup_manager() -> MemoryBackupManager:
    """Get the global memory backup manager instance."""
    global _backup_manager
    if _backup_manager is None:
        from memory.memory_manager import MEMORY_PATH
        _backup_manager = MemoryBackupManager(MEMORY_PATH)
    return _backup_manager
