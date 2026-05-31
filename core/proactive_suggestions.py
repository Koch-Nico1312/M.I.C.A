"""
Proactive Suggestions System
Uses AI context to offer help before being asked
"""

import threading
import time
from typing import List, Dict, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from config.config_loader import get_config


@dataclass
class Suggestion:
    """Represents a proactive suggestion"""
    text: str
    priority: str  # high, medium, low
    category: str  # coding, productivity, system, general
    timestamp: datetime
    context: str = ""


class ProactiveSuggestions:
    """Manages proactive suggestions based on context"""
    
    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get('proactive.enabled', False)
        self.interval = self.config.get('proactive.interval_seconds', 60)
        self.max_suggestions = self.config.get('proactive.max_suggestions', 3)
        
        self.suggestions: List[Suggestion] = []
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.speak_callback: Optional[Callable] = None
        
        # Context tracking
        self.last_action: Optional[str] = None
        self.action_count: Dict[str, int] = {}
        self.error_patterns: List[str] = []
        
        if self.enabled:
            print(
                "[Proactive] ✅ Initialized "
                f"(interval: {self.interval}s, max: {self.max_suggestions})"
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
    
    def _detect_patterns(self) -> List[Suggestion]:
        """Detect patterns and generate suggestions"""
        new_suggestions = []
        
        # Detect repetitive actions
        for action, count in self.action_count.items():
            if count >= 3:
                suggestion = Suggestion(
                    text=f"I notice you've done '{action}' {count} times. Would you like me to automate this?",
                    priority="medium",
                    category="productivity",
                    timestamp=datetime.now(),
                    context=f"repetitive_action:{action}"
                )
                new_suggestions.append(suggestion)
                # Reset count after suggesting
                self.action_count[action] = 0
        
        # Detect error patterns
        if len(self.error_patterns) >= 2:
            suggestion = Suggestion(
                text="I've noticed some errors recently. Would you like me to help troubleshoot?",
                priority="high",
                category="system",
                timestamp=datetime.now(),
                context="error_pattern_detected"
            )
            new_suggestions.append(suggestion)
            self.error_patterns.clear()
        
        return new_suggestions
    
    def _generate_contextual_suggestion(self) -> Optional[Suggestion]:
        """Generate suggestion based on current context"""
        # This would use the AI to analyze context and generate suggestions
        # For now, return None as a placeholder
        return None
    
    def _suggestion_loop(self):
        """Main suggestion generation loop"""
        while self.running:
            try:
                # Detect patterns
                pattern_suggestions = self._detect_patterns()
                
                # Generate contextual suggestion
                contextual = self._generate_contextual_suggestion()
                if contextual:
                    pattern_suggestions.append(contextual)
                
                # Add to suggestions list
                for suggestion in pattern_suggestions:
                    self.suggestions.append(suggestion)
                
                # Limit total suggestions
                if len(self.suggestions) > self.max_suggestions:
                    self.suggestions = self.suggestions[-self.max_suggestions:]
                
                # Speak high-priority suggestions
                for suggestion in self.suggestions:
                    if suggestion.priority == "high" and self.speak_callback:
                        self.speak_callback(f"Sir, {suggestion.text}")
                        self.suggestions.remove(suggestion)
                        break
                
                time.sleep(self.interval)
                
            except Exception as e:
                print(f"[Proactive] ❌ Loop error: {e}")
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
                'text': s.text,
                'priority': s.priority,
                'category': s.category,
                'timestamp': s.timestamp.isoformat()
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
