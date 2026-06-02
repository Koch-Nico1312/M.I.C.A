"""
Proactive Suggestions System
Uses AI context to offer help before being asked
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from config.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Suggestion:
    """Represents a proactive suggestion"""

    text: str
    priority: str  # high, medium, low
    category: str  # coding, productivity, system, general, health, file_analysis
    timestamp: datetime
    context: str = ""
    action_required: bool = False


class ProactiveSuggestions:
    """Manages proactive suggestions based on context"""

    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get("proactive.enabled", False)
        self.mode = self.config.get("proactive.mode", "normal")  # off, subtle, normal, active
        self.interval = self.config.get("proactive.interval_seconds", 60)
        self.max_suggestions = self.config.get("proactive.max_suggestions", 3)

        self.suggestions: List[Suggestion] = []
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.speak_callback: Optional[Callable] = None

        # Context tracking
        self.last_action: Optional[str] = None
        self.action_count: Dict[str, int] = {}
        self.error_patterns: List[str] = []
        self.last_file: Optional[Path] = None
        self.last_image: Optional[Path] = None
        self.suggestion_cooldown: Dict[str, datetime] = {}
        self.cooldown_minutes = 30  # Don't repeat same suggestion within 30 minutes

        if self.enabled:
            logger.info(
                f"Proactive suggestions initialized (mode: {self.mode}, interval: {self.interval}s)"
            )

    def set_speak_callback(self, callback: Callable):
        """Set the callback function for speaking suggestions"""
        self.speak_callback = callback

    def track_action(self, action: str, success: bool = True):
        """Track user actions for pattern detection"""
        self.last_action = action

        if success:
            self.action_count[action] = self.action_count.get(action, 0) + 1
        else:
            self.error_patterns.append(action)
            # Keep only last 10 errors
            if len(self.error_patterns) > 10:
                self.error_patterns.pop(0)

    def track_file(self, file_path: Path):
        """Track file interactions"""
        self.last_file = file_path

    def track_image(self, image_path: Path):
        """Track image interactions"""
        self.last_image = image_path

    def _suggestion_loop(self):
        """Background loop for generating proactive suggestions"""
        while self.running:
            try:
                new_suggestions = self._detect_patterns()
                
                if new_suggestions:
                    for suggestion in new_suggestions:
                        self.suggestions.append(suggestion)
                    
                    # Keep only max suggestions
                    if len(self.suggestions) > self.max_suggestions:
                        self.suggestions = self.suggestions[-self.max_suggestions:]
                    
                    # Speak the first suggestion if callback is set
                    if self.suggestions and self.speak_callback:
                        self.speak_callback(self.suggestions[0].text)
                
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in suggestion loop: {e}")
                time.sleep(self.interval)

    def _detect_patterns(self) -> List[Suggestion]:
        """Detect patterns and generate suggestions"""
        new_suggestions = []

        if self.mode == "off":
            return new_suggestions

        # Detect repetitive actions
        for action, count in self.action_count.items():
            if count >= 3:
                suggestion_key = f"repetitive_{action}"
                if self._check_cooldown(suggestion_key):
                    suggestion = Suggestion(
                        text=f"I notice you've done '{action}' {count} times. Would you like me to automate this?",
                        priority="medium",
                        category="productivity",
                        timestamp=datetime.now(),
                        context=f"repetitive_action:{action}",
                    )
                    new_suggestions.append(suggestion)
                    self._set_cooldown(suggestion_key)
                    # Reset count after suggesting
                    self.action_count[action] = 0

        # Detect error patterns
        if len(self.error_patterns) >= 2:
            suggestion_key = "error_pattern"
            if self._check_cooldown(suggestion_key):
                suggestion = Suggestion(
                    text="I've noticed some errors recently. Would you like me to help troubleshoot?",
                    priority="high",
                    category="system",
                    timestamp=datetime.now(),
                    context="error_pattern_detected",
                )
                new_suggestions.append(suggestion)
                self._set_cooldown(suggestion_key)
                self.error_patterns.clear()

        # File-based suggestions
        if self.last_file:
            suggestion_key = f"file_analysis_{self.last_file.suffix}"
            if self._check_cooldown(suggestion_key):
                suggestion = Suggestion(
                    text=f"Would you like me to analyze this {self.last_file.suffix} file?",
                    priority="medium",
                    category="file_analysis",
                    timestamp=datetime.now(),
                    context=f"file:{self.last_file.name}",
                    action_required=True,
                )
                new_suggestions.append(suggestion)
                self._set_cooldown(suggestion_key)

        # Image-based suggestions
        if self.last_image:
            suggestion_key = "image_analysis"
            if self._check_cooldown(suggestion_key):
                suggestion = Suggestion(
                    text="Would you like me to analyze this image?",
                    priority="medium",
                    category="file_analysis",
                    timestamp=datetime.now(),
                    context=f"image:{self.last_image.name}",
                    action_required=True,
                )
                new_suggestions.append(suggestion)
                self._set_cooldown(suggestion_key)

        return new_suggestions

    def _generate_contextual_suggestion(self) -> Optional[Suggestion]:
        """Generate suggestion based on current context"""
        # This would use the AI to analyze context and generate suggestions
        # For now, return None as this would require AI integration
        return None

    def _check_cooldown(self, suggestion_key: str) -> bool:
        """Check if suggestion is on cooldown"""
        if suggestion_key not in self.suggestion_cooldown:
            return True

        cooldown_end = self.suggestion_cooldown[suggestion_key]
        if datetime.now() > cooldown_end:
            del self.suggestion_cooldown[suggestion_key]
            return True

        return False

    def _set_cooldown(self, suggestion_key: str):
        """Set cooldown for a suggestion"""
        cooldown_end = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        self.suggestion_cooldown[suggestion_key] = cooldown_end

    def generate_suggestions(self, context: Optional[Dict] = None) -> List[Suggestion]:
        """
        Generate proactive suggestions based on context and patterns.

        Args:
            context: Optional context dictionary with additional information

        Returns:
            List of suggestions
        """
        if not self.enabled or self.mode == "off":
            return []

        new_suggestions = self._detect_patterns()

        # Add contextual suggestion if available
        contextual = self._generate_contextual_suggestion()
        if contextual:
            new_suggestions.append(contextual)

        # Filter by mode
        if self.mode == "subtle":
            # Only high priority suggestions
            new_suggestions = [s for s in new_suggestions if s.priority == "high"]
        elif self.mode == "active":
            # All suggestions
            pass
        else:  # normal
            # High and medium priority
            new_suggestions = [s for s in new_suggestions if s.priority in ["high", "medium"]]

        # Add to suggestions list
        self.suggestions.extend(new_suggestions)

        # Trim to max
        if len(self.suggestions) > self.max_suggestions:
            self.suggestions = self.suggestions[-self.max_suggestions :]

        return new_suggestions

    def get_suggestions(self) -> List[Suggestion]:
        """Get current suggestions"""
        return self.suggestions.copy()

    def clear_suggestions(self):
        """Clear all suggestions"""
        self.suggestions.clear()
        logger.debug("Suggestions cleared")

    def dismiss_suggestion(self, index: int):
        """Dismiss a suggestion by index"""
        if 0 <= index < len(self.suggestions):
            dismissed = self.suggestions.pop(index)
            logger.debug(f"Dismissed suggestion: {dismissed.text[:50]}...")

    def start(self):
        """Start the proactive suggestions background thread"""
        if self.running:
            logger.warning("Proactive suggestions already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Proactive suggestions started")

    def stop(self):
        """Stop the proactive suggestions background thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info("Proactive suggestions stopped")

    def _run_loop(self):
        """Background loop for generating suggestions"""
        while self.running:
            try:
                suggestions = self.generate_suggestions()

                # Speak suggestions if callback is set
                if suggestions and self.speak_callback:
                    for suggestion in suggestions:
                        if suggestion.priority == "high":
                            try:
                                self.speak_callback(suggestion.text)
                            except Exception as e:
                                logger.error(f"Failed to speak suggestion: {e}")

                time.sleep(self.interval)

            except Exception as e:
                logger.error(f"Proactive suggestions loop error: {e}")
                time.sleep(self.interval)

    def start(self):
        """Start proactive suggestion monitoring"""
        if not self.enabled:
            return False

        if self.running:
            return True

        self.running = True
        self.thread = threading.Thread(target=self._suggestion_loop, daemon=True)
        self.thread.start()
        print("[Proactive] ▶️ Started monitoring")
        return True

    def stop(self):
        """Stop proactive suggestion monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[Proactive] ⏹️ Stopped monitoring")

    def get_suggestions(self) -> List[Dict[str, str]]:
        """Get current suggestions"""
        return [
            {
                "text": s.text,
                "priority": s.priority,
                "category": s.category,
                "timestamp": s.timestamp.isoformat(),
            }
            for s in self.suggestions
        ]

    def clear_suggestions(self):
        """Clear all suggestions"""
        self.suggestions.clear()

    def dismiss_suggestion(self, index: int):
        """Dismiss a suggestion by index"""
        if 0 <= index < len(self.suggestions):
            self.suggestions.pop(index)


# Global instance
_proactive_suggestions: Optional[ProactiveSuggestions] = None


def get_proactive_suggestions() -> ProactiveSuggestions:
    """Get the global proactive suggestions instance"""
    global _proactive_suggestions
    if _proactive_suggestions is None:
        _proactive_suggestions = ProactiveSuggestions()
    return _proactive_suggestions
