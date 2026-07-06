"""
File Watcher for M.I.C.A AI Assistant.

This module provides file system monitoring capabilities to trigger actions
when files are created, modified, or deleted.
Supports both polling (legacy) and event-based (watchdog) monitoring.
"""

import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.logger import get_logger
from core.performance_flags import get_performance_flags

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

logger = get_logger(__name__)


class Debouncer:
    """Debounces rapid file events to prevent callback spam."""
    
    def __init__(self, debounce_seconds: float = 1.0):
        self.debounce_seconds = debounce_seconds
        self._pending_events: Dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def should_process(self, path: str) -> bool:
        """
        Check if event should be processed (not debounced).
        
        Args:
            path: File path to check
            
        Returns:
            True if event should be processed
        """
        with self._lock:
            now = datetime.now()
            if path in self._pending_events:
                last_time = self._pending_events[path]
                if (now - last_time).total_seconds() < self.debounce_seconds:
                    return False
            
            self._pending_events[path] = now
            return True
    
    def cleanup_old(self):
        """Clean up old entries from debouncer."""
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.debounce_seconds * 2)
            self._pending_events = {
                k: v for k, v in self._pending_events.items() 
                if v > cutoff
            }


class WatchdogEventHandler(FileSystemEventHandler):
    """Watchdog event handler that converts events to FileEvents."""
    
    def __init__(self, callback: Callable[[FileEvent], None], debouncer: Optional[Debouncer] = None):
        super().__init__()
        self.callback = callback
        self.debouncer = debouncer
    
    def _process_event(self, event: FileSystemEvent, event_type: str):
        """Process a watchdog event."""
        if self.debouncer and not self.debouncer.should_process(event.src_path):
            return
        
        file_event = FileEvent(event_type, event.src_path)
        try:
            self.callback(file_event)
        except Exception as e:
            logger.error(f"Error in event callback: {e}")
    
    def on_created(self, event):
        if not event.is_directory:
            self._process_event(event, "created")
    
    def on_modified(self, event):
        if not event.is_directory:
            self._process_event(event, "modified")
    
    def on_deleted(self, event):
        if not event.is_directory:
            self._process_event(event, "deleted")
    
    def on_moved(self, event):
        if not event.is_directory:
            # Handle as delete of source and create of destination
            self._process_event(FileSystemEvent("deleted", event.src_path), "deleted")
            self._process_event(FileSystemEvent("created", event.dest_path), "created")


class FileEvent:
    """Represents a file system event."""
    
    def __init__(self, event_type: str, path: str, timestamp: Optional[datetime] = None):
        self.event_type = event_type  # 'created', 'modified', 'deleted'
        self.path = path
        self.timestamp = timestamp or datetime.now()
    
    def __repr__(self):
        return f"FileEvent({self.event_type}, {self.path}, {self.timestamp})"


class WatchedPath:
    """Represents a watched path with its callbacks."""
    
    def __init__(
        self,
        path: str,
        on_created: Optional[Callable] = None,
        on_modified: Optional[Callable] = None,
        on_deleted: Optional[Callable] = None,
        recursive: bool = True
    ):
        self.path = path
        self.on_created = on_created
        self.on_modified = on_modified
        self.on_deleted = on_deleted
        self.recursive = recursive
        self._file_states: Dict[str, float] = {}
        self._scan_path()
    
    def _scan_path(self):
        """Scan the path and record initial file states."""
        try:
            if self.recursive:
                for root, dirs, files in os.walk(self.path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        self._file_states[file_path] = os.path.getmtime(file_path)
            else:
                for item in os.listdir(self.path):
                    item_path = os.path.join(self.path, item)
                    if os.path.isfile(item_path):
                        self._file_states[item_path] = os.path.getmtime(item_path)
        except Exception as e:
            logger.error(f"Error scanning path {self.path}: {e}")
    
    def check_changes(self) -> List[FileEvent]:
        """Check for file changes and return events."""
        events = []
        current_files = set()
        
        try:
            if self.recursive:
                for root, dirs, files in os.walk(self.path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        current_files.add(file_path)
                        mtime = os.path.getmtime(file_path)
                        
                        if file_path not in self._file_states:
                            # New file
                            events.append(FileEvent("created", file_path))
                            self._file_states[file_path] = mtime
                        elif self._file_states[file_path] != mtime:
                            # Modified file
                            events.append(FileEvent("modified", file_path))
                            self._file_states[file_path] = mtime
            else:
                for item in os.listdir(self.path):
                    item_path = os.path.join(self.path, item)
                    if os.path.isfile(item_path):
                        current_files.add(item_path)
                        mtime = os.path.getmtime(item_path)
                        
                        if item_path not in self._file_states:
                            events.append(FileEvent("created", item_path))
                            self._file_states[item_path] = mtime
                        elif self._file_states[item_path] != mtime:
                            events.append(FileEvent("modified", item_path))
                            self._file_states[item_path] = mtime
            
            # Check for deleted files
            for file_path in list(self._file_states.keys()):
                if file_path not in current_files:
                    events.append(FileEvent("deleted", file_path))
                    del self._file_states[file_path]
        
        except Exception as e:
            logger.error(f"Error checking changes in {self.path}: {e}")
        
        return events


class FileWatcher:
    """
    File system watcher for M.I.C.A.
    
    Monitors directories for file changes and triggers callbacks.
    Supports both polling (legacy) and event-based (watchdog) monitoring.
    """
    
    def __init__(self, check_interval: float = 1.0, debounce_seconds: float = 1.0):
        self._watched_paths: Dict[str, WatchedPath] = {}
        self._check_interval = check_interval
        self._debounce_seconds = debounce_seconds
        self._running = False
        self._watcher_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._event_handlers: List[Callable] = []
        
        # Event-based monitoring
        self._observer = None
        self._debouncer = Debouncer(debounce_seconds)
        self._use_event_based = False
    
    def add_watch(
        self,
        path: str,
        on_created: Optional[Callable] = None,
        on_modified: Optional[Callable] = None,
        on_deleted: Optional[Callable] = None,
        recursive: bool = True
    ):
        """
        Add a path to watch.
        
        Args:
            path: Path to watch
            on_created: Callback for file creation
            on_modified: Callback for file modification
            on_deleted: Callback for file deletion
            recursive: Whether to watch subdirectories
        """
        if not os.path.exists(path):
            raise ValueError(f"Path does not exist: {path}")
        
        watched = WatchedPath(path, on_created, on_modified, on_deleted, recursive)
        self._watched_paths[path] = watched
        logger.info(f"Added watch for path: {path}")
    
    def remove_watch(self, path: str) -> bool:
        """
        Remove a watched path.
        
        Args:
            path: Path to stop watching
            
        Returns:
            bool: True if path was removed
        """
        if path in self._watched_paths:
            del self._watched_paths[path]
            logger.info(f"Removed watch for path: {path}")
            return True
        return False
    
    def add_event_handler(self, handler: Callable):
        """
        Add a global event handler.
        
        Args:
            handler: Callback that receives FileEvent objects
        """
        self._event_handlers.append(handler)
    
    def _watch_loop(self):
        """Main watch loop."""
        while self._running and not self._stop_event.is_set():
            try:
                for path, watched in self._watched_paths.items():
                    events = watched.check_changes()
                    
                    for event in events:
                        # Call specific callbacks
                        if event.event_type == "created" and watched.on_created:
                            try:
                                watched.on_created(event)
                            except Exception as e:
                                logger.error(f"Error in on_created callback: {e}")
                        
                        elif event.event_type == "modified" and watched.on_modified:
                            try:
                                watched.on_modified(event)
                            except Exception as e:
                                logger.error(f"Error in on_modified callback: {e}")
                        
                        elif event.event_type == "deleted" and watched.on_deleted:
                            try:
                                watched.on_deleted(event)
                            except Exception as e:
                                logger.error(f"Error in on_deleted callback: {e}")
                        
                        # Call global handlers
                        for handler in self._event_handlers:
                            try:
                                handler(event)
                            except Exception as e:
                                logger.error(f"Error in event handler: {e}")
                
                time.sleep(self._check_interval)
            
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                time.sleep(5)
    
    def start(self):
        """Start the file watcher."""
        if self._running:
            logger.warning("File watcher already running")
            return
        
        # Check if event-based monitoring is enabled
        perf_flags = get_performance_flags()
        use_event_based = perf_flags.is_enabled("event_file_watching") and WATCHDOG_AVAILABLE
        
        self._running = True
        self._stop_event.clear()
        self._use_event_based = use_event_based
        
        if use_event_based:
            # Use event-based monitoring with watchdog
            self._observer = Observer()
            
            # Create event handler
            def event_callback(file_event: FileEvent):
                """Callback for watchdog events."""
                # Call specific callbacks
                for path, watched in self._watched_paths.items():
                    if file_event.path.startswith(path):
                        if file_event.event_type == "created" and watched.on_created:
                            try:
                                watched.on_created(file_event)
                            except Exception as e:
                                logger.error(f"Error in on_created callback: {e}")
                        elif file_event.event_type == "modified" and watched.on_modified:
                            try:
                                watched.on_modified(file_event)
                            except Exception as e:
                                logger.error(f"Error in on_modified callback: {e}")
                        elif file_event.event_type == "deleted" and watched.on_deleted:
                            try:
                                watched.on_deleted(file_event)
                            except Exception as e:
                                logger.error(f"Error in on_deleted callback: {e}")
                
                # Call global handlers
                for handler in self._event_handlers:
                    try:
                        handler(file_event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
            
            # Add watches for all paths
            for path, watched in self._watched_paths.items():
                handler = WatchdogEventHandler(event_callback, self._debouncer)
                self._observer.schedule(handler, path, recursive=watched.recursive)
                logger.info(f"Added event-based watch for: {path}")
            
            self._observer.start()
            logger.info("File watcher started (event-based)")
        else:
            # Use polling (legacy)
            self._watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._watcher_thread.start()
            logger.info("File watcher started (polling)")
    
    def stop(self):
        """Stop the file watcher."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._use_event_based and self._observer:
            # Stop watchdog observer
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("File watcher stopped (event-based)")
        elif self._watcher_thread:
            # Stop polling thread
            self._watcher_thread.join(timeout=5)
            logger.info("File watcher stopped (polling)")
        
        # Cleanup debouncer
        self._debouncer.cleanup_old()
    
    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._running
    
    def clear_watches(self):
        """Clear all watched paths."""
        self._watched_paths.clear()
        logger.info("Cleared all watches")


# Global file watcher instance
_file_watcher: Optional[FileWatcher] = None


def get_file_watcher(check_interval: float = 1.0, debounce_seconds: float = 1.0) -> FileWatcher:
    """
    Get the global file watcher instance.
    
    Args:
        check_interval: Interval between checks in seconds (for polling mode)
        debounce_seconds: Debounce time for rapid events (for event-based mode)
        
    Returns:
        FileWatcher: The global file watcher
    """
    global _file_watcher
    if _file_watcher is None:
        _file_watcher = FileWatcher(check_interval=check_interval, debounce_seconds=debounce_seconds)
    return _file_watcher
