from __future__ import annotations

"""
Passive Vision System
Background OCR/Vision stream for short-term visual memory
"""

import asyncio
import hashlib
import json
import queue
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.metrics_collector import get_metrics_collector
from core.paths import resolve_relative_path
from core.performance_flags import get_performance_flags

try:
    import cv2
    import mss
    import numpy as np

    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

from config.config_loader import get_config


class VisionMemory:
    """Stores short-term visual memory"""

    def __init__(self, max_minutes: int = 10):
        self.max_minutes = max_minutes
        self.memory: deque = deque()
        self.lock = threading.Lock()

    def add(
        self, timestamp: datetime, ocr_text: str, image_hash: str, metadata: Dict[str, Any] = None
    ):
        """Add a vision memory entry"""
        with self.lock:
            entry = {
                "timestamp": timestamp.isoformat(),
                "ocr_text": ocr_text,
                "image_hash": image_hash,
                "metadata": metadata or {},
            }
            self.memory.append(entry)
            self._cleanup_old()

    def _cleanup_old(self):
        """Remove entries older than max_minutes"""
        cutoff = datetime.now() - timedelta(minutes=self.max_minutes)
        while self.memory and datetime.fromisoformat(self.memory[0]["timestamp"]) < cutoff:
            self.memory.popleft()

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search visual memory for text matching query"""
        with self.lock:
            query_lower = query.lower()
            results = []

            for entry in reversed(self.memory):
                if query_lower in entry["ocr_text"].lower():
                    results.append(entry)
                    if len(results) >= max_results:
                        break

            return results

    def get_recent(self, minutes: int = 2) -> List[Dict]:
        """Get recent vision entries"""
        with self.lock:
            cutoff = datetime.now() - timedelta(minutes=minutes)
            recent = []

            for entry in reversed(self.memory):
                if datetime.fromisoformat(entry["timestamp"]) >= cutoff:
                    recent.append(entry)
                else:
                    break

            return recent

    def get_all(self) -> List[Dict]:
        """Get all vision memory"""
        with self.lock:
            return list(self.memory)


class PassiveVision:
    """Background vision system for continuous screen monitoring"""

    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get("passive_vision.enabled", False)
        self.interval = self.config.get("passive_vision.interval_seconds", 30)
        self.memory_minutes = self.config.get("passive_vision.memory_minutes", 10)

        storage_path = self.config.get(
            "passive_vision.storage_path",
            str(resolve_relative_path("data/vision_memory")),
        )
        self.storage_path = resolve_relative_path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.memory = VisionMemory(max_minutes=self.memory_minutes)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.sct = None
        
        # Batch processing queue
        self._screen_queue: queue.Queue = queue.Queue(maxsize=10)
        self._batch_size = 3
        self._batch_timeout = 2.0
        self._processing_thread: Optional[threading.Thread] = None

        if self.enabled and VISION_AVAILABLE:
            self.sct = mss.mss()
            print(
                "[PassiveVision] ✅ Initialized "
                f"(interval: {self.interval}s, memory: {self.memory_minutes}m)"
            )
        elif not VISION_AVAILABLE:
            print("[PassiveVision] ⚠️ Vision libraries not available")

    def _capture_screen(self) -> Optional[np.ndarray]:
        """Capture screen screenshot"""
        if not self.sct:
            return None

        try:
            monitor = self.sct.monitors[1]  # Primary monitor
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"[PassiveVision] ❌ Capture error: {e}")
            return None

    def _perform_ocr(self, image: np.ndarray) -> str:
        """Perform OCR on image"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Simple text extraction using contour detection
            # For production, you'd want to use Tesseract or a more sophisticated OCR
            # This is a simplified version

            # Apply threshold
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filter for text-like regions
            text_regions = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > 20 and h > 10 and w < 500 and h < 100:
                    text_regions.append((x, y, w, h))

            # Extract text from regions (simplified - would use Tesseract in production)
            # For now, return a placeholder indicating regions found
            return f"[Detected {len(text_regions)} text regions]"

        except Exception as e:
            print(f"[PassiveVision] ❌ OCR error: {e}")
            return ""

    def _compute_hash(self, image: np.ndarray) -> str:
        """Compute hash of image for deduplication"""
        try:
            # Resize to small thumbnail for hashing
            small = cv2.resize(image, (32, 32))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            return hashlib.md5(gray.tobytes()).hexdigest()
        except Exception:
            return ""

    def _vision_loop(self):
        """Main vision capture loop"""
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        while self.running:
            try:
                metrics.start_operation("vision_capture_cycle")

                # Capture screen
                image = self._capture_screen()
                if image is not None:
                    # Check if batch processing is enabled
                    if perf_flags.is_enabled("batch_screen_processing"):
                        # Queue-based batch processing
                        try:
                            self._screen_queue.put_nowait(image)
                        except queue.Full:
                            # Queue full, process immediately
                            self._process_batch()
                            self._screen_queue.put_nowait(image)
                    else:
                        # Sequential processing (original)
                        ocr_text = self._perform_ocr(image)

                        # Compute hash
                        image_hash = self._compute_hash(image)

                        # Store in memory
                        self.memory.add(
                            timestamp=datetime.now(),
                            ocr_text=ocr_text,
                            image_hash=image_hash,
                            metadata={"resolution": image.shape[:2]},
                        )

                    print(
                        f"[PassiveVision] 📸 Captured (batch: {perf_flags.is_enabled('batch_screen_processing')})"
                    )

                metrics.end_operation(
                    "vision_capture_cycle",
                    {"batch_enabled": perf_flags.is_enabled("batch_screen_processing")},
                )

                # Wait for next interval
                time.sleep(self.interval)

            except Exception as e:
                print(f"[PassiveVision] ❌ Loop error: {e}")
                time.sleep(self.interval)

    def _batch_process_screens(self, image: np.ndarray):
        """
        Process screen with parallel OCR and hash computation.

        Args:
            image: Screen image to process
        """
        metrics = get_metrics_collector()
        metrics.start_operation("batch_screen_process")

        try:
            # Use threading for parallel processing
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Submit tasks in parallel
                ocr_future = executor.submit(self._perform_ocr, image)
                hash_future = executor.submit(self._compute_hash, image)

                # Wait for both to complete
                ocr_text = ocr_future.result()
                image_hash = hash_future.result()

            # Store in memory
            self.memory.add(
                timestamp=datetime.now(),
                ocr_text=ocr_text,
                image_hash=image_hash,
                metadata={"resolution": image.shape[:2], "batch_processed": True},
            )

            metrics.end_operation("batch_screen_process", {"tasks_completed": 2, "success": True})
        except Exception as e:
            print(f"[PassiveVision] ❌ Batch processing error: {e}")
            # Fallback to sequential processing
            ocr_text = self._perform_ocr(image)
            image_hash = self._compute_hash(image)
            self.memory.add(
                timestamp=datetime.now(),
                ocr_text=ocr_text,
                image_hash=image_hash,
                metadata={"resolution": image.shape[:2], "batch_processed": False},
            )
            metrics.end_operation(
                "batch_screen_process", {"tasks_completed": 0, "success": False, "fallback": True}
            )

    def _process_batch(self):
        """
        Process a batch of screens from the queue.
        Processes multiple screens in parallel for better performance.
        """
        metrics = get_metrics_collector()
        metrics.start_operation("process_batch")
        
        batch = []
        try:
            # Collect batch from queue
            while len(batch) < self._batch_size:
                try:
                    image = self._screen_queue.get_nowait()
                    batch.append(image)
                except queue.Empty:
                    break
            
            if not batch:
                return
            
            # Process batch in parallel
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(batch), 4)) as executor:
                # Submit all OCR tasks
                ocr_futures = [executor.submit(self._perform_ocr, img) for img in batch]
                # Submit all hash tasks
                hash_futures = [executor.submit(self._compute_hash, img) for img in batch]
                
                # Wait for all to complete
                ocr_results = [f.result() for f in ocr_futures]
                hash_results = [f.result() for f in hash_futures]
            
            # Store results in memory
            for i, (ocr_text, image_hash) in enumerate(zip(ocr_results, hash_results)):
                self.memory.add(
                    timestamp=datetime.now(),
                    ocr_text=ocr_text,
                    image_hash=image_hash,
                    metadata={
                        "resolution": batch[i].shape[:2],
                        "batch_processed": True,
                        "batch_size": len(batch),
                    },
                )
            
            metrics.end_operation("process_batch", {"batch_size": len(batch), "success": True})
            print(f"[PassiveVision] 📦 Processed batch of {len(batch)} screens")
            
        except Exception as e:
            print(f"[PassiveVision] ❌ Batch processing error: {e}")
            # Fallback to sequential processing
            for image in batch:
                try:
                    ocr_text = self._perform_ocr(image)
                    image_hash = self._compute_hash(image)
                    self.memory.add(
                        timestamp=datetime.now(),
                        ocr_text=ocr_text,
                        image_hash=image_hash,
                        metadata={"resolution": image.shape[:2], "batch_processed": False},
                    )
                except Exception as inner_e:
                    print(f"[PassiveVision] ❌ Individual screen error: {inner_e}")
            
            metrics.end_operation("process_batch", {"batch_size": len(batch), "success": False, "fallback": True})

    def start(self):
        """Start passive vision monitoring"""
        if not self.enabled or not VISION_AVAILABLE:
            return False

        if self.running:
            return True

        self.running = True
        self.thread = threading.Thread(target=self._vision_loop, daemon=True)
        self.thread.start()
        
        # Start batch processing thread if enabled
        perf_flags = get_performance_flags()
        if perf_flags.is_enabled("batch_screen_processing"):
            self._processing_thread = threading.Thread(target=self._batch_processing_loop, daemon=True)
            self._processing_thread.start()
            print("[PassiveVision] ▶️ Started monitoring with batch processing")
        else:
            print("[PassiveVision] ▶️ Started monitoring")
        
        return True

    def _batch_processing_loop(self):
        """Background thread for processing queued screens"""
        perf_flags = get_performance_flags()
        while self.running and perf_flags.is_enabled("batch_screen_processing"):
            try:
                # Process batch if queue has items
                if not self._screen_queue.empty():
                    self._process_batch()
                # Small sleep to prevent busy waiting
                time.sleep(0.1)
            except Exception as e:
                print(f"[PassiveVision] ❌ Batch processing loop error: {e}")
                time.sleep(1)

    def stop(self):
        """Stop passive vision monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        if self._processing_thread:
            self._processing_thread.join(timeout=5)
        
        # Process remaining items in queue
        if not self._screen_queue.empty():
            print("[PassiveVision] 🔄 Processing remaining queue items...")
            self._process_batch()
        
        print("[PassiveVision] ⏹️ Stopped monitoring")

    def query_memory(self, question: str) -> str:
        """Query visual memory with a question"""
        recent = self.memory.get_recent(minutes=5)

        if not recent:
            return "I don't have any recent visual memory, sir."

        # Simple keyword matching
        question_lower = question.lower()
        matches = []

        for entry in recent:
            if any(word in entry["ocr_text"].lower() for word in question_lower.split()):
                matches.append(entry)

        if matches:
            return (
                f"Found {len(matches)} relevant entries in visual memory from the last 5 minutes."
            )

        return (
            f"I have {len(recent)} recent visual memories, but none directly match your query, sir."
        )

    def save_memory_to_disk(self):
        """Save current memory to disk"""
        try:
            memory_file = (
                self.storage_path / f"vision_memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(list(self.memory.get_all()), f, indent=2)
            print(f"[PassiveVision] 💾 Saved memory to {memory_file}")
        except Exception as e:
            print(f"[PassiveVision] ❌ Save error: {e}")


# Global instance
_passive_vision: Optional[PassiveVision] = None


def get_passive_vision() -> PassiveVision:
    """Get the global passive vision instance"""
    global _passive_vision
    if _passive_vision is None:
        _passive_vision = PassiveVision()
    return _passive_vision
