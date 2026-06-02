"""
Multimodal Context Processing for Mark-XXXIX
============================================
Combines user query, conversation history, memory, files, images, and screen state
to provide intelligent context-aware responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.local_analyzer import get_local_analyzer
from core.logger import get_logger
from core.passive_vision import PassiveVision, VisionMemory
from memory.hybrid_retrieval import RetrievalResult, get_hybrid_retrieval

logger = get_logger(__name__)


class ContextSource(Enum):
    """Sources of context information."""

    USER_QUERY = "user_query"
    CONVERSATION_HISTORY = "conversation_history"
    LONG_TERM_MEMORY = "long_term_memory"
    CURRENT_FILE = "current_file"
    CURRENT_IMAGE = "current_image"
    SCREEN_STATE = "screen_state"
    RECENT_ACTIONS = "recent_actions"
    ACTIVE_ROUTINE = "active_routine"


class ContextDecision(Enum):
    """Decision on how to respond to context."""

    DIRECT_RESPONSE = "direct_response"
    ANALYZE_FILE = "analyze_file"
    ANALYZE_IMAGE = "analyze_image"
    ASK_CLARIFICATION = "ask_clarification"
    SHOW_SUGGESTION = "show_suggestion"
    TRIGGER_REMINDER = "trigger_reminder"
    COMBINED_RESPONSE = "combined_response"


@dataclass
class ContextSignal:
    """Represents a single context signal."""

    source: ContextSource
    content: Any
    timestamp: datetime
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextModel:
    """
    Combined context model that integrates multiple signals.
    """

    user_query: Optional[str] = None
    conversation_history: List[str] = field(default_factory=list)
    memory_results: List[RetrievalResult] = field(default_factory=list)
    current_file: Optional[Path] = None
    current_image: Optional[Path] = None
    screen_text: Optional[str] = None
    recent_actions: List[str] = field(default_factory=list)
    active_routine: Optional[str] = None
    signals: List[ContextSignal] = field(default_factory=list)

    def add_signal(
        self,
        source: ContextSource,
        content: Any,
        confidence: float = 0.5,
        metadata: Dict[str, Any] = None,
    ):
        """Add a context signal."""
        signal = ContextSignal(
            source=source,
            content=content,
            timestamp=datetime.now(),
            confidence=confidence,
            metadata=metadata or {},
        )
        self.signals.append(signal)

    def get_relevant_context(self, max_signals: int = 5) -> List[ContextSignal]:
        """Get most relevant context signals sorted by confidence."""
        sorted_signals = sorted(self.signals, key=lambda s: s.confidence, reverse=True)
        return sorted_signals[:max_signals]


class MultimodalContext:
    """
    Processes multimodal context from various sources.
    Decides on appropriate response strategy.
    """

    def __init__(self):
        """Initialize the multimodal context processor."""
        self.local_analyzer = get_local_analyzer()
        self.hybrid_retrieval = get_hybrid_retrieval()
        self.passive_vision: Optional[PassiveVision] = None

        # Configuration
        self.context_threshold = 0.3
        self.max_context_signals = 10
        self.suggestion_threshold = 0.7

        logger.info("Multimodal context processor initialized")

    def build_context(
        self,
        user_query: Optional[str] = None,
        conversation_history: Optional[List[str]] = None,
        current_file: Optional[Path] = None,
        current_image: Optional[Path] = None,
        screen_state: Optional[Dict[str, Any]] = None,
    ) -> ContextModel:
        """
        Build a comprehensive context model from available signals.

        Args:
            user_query: Current user query
            conversation_history: Recent conversation history
            current_file: Current file being worked on
            current_image: Current image being analyzed
            screen_state: Current screen state

        Returns:
            ContextModel with integrated context
        """
        context = ContextModel(
            user_query=user_query,
            conversation_history=conversation_history or [],
            current_file=current_file,
            current_image=current_image,
        )

        # Add user query signal
        if user_query:
            context.add_signal(
                ContextSource.USER_QUERY, user_query, confidence=1.0, metadata={"type": "text"}
            )

        # Retrieve relevant memory
        if user_query:
            memory_results = self.hybrid_retrieval.retrieve(user_query, max_results=5)
            context.memory_results = memory_results

            for result in memory_results:
                context.add_signal(
                    ContextSource.LONG_TERM_MEMORY,
                    result.entry.value,
                    confidence=result.relevance_score,
                    metadata={
                        "category": result.entry.category,
                        "age_days": result.age_days,
                        "match_type": result.match_type,
                    },
                )

        # Add file context
        if current_file and current_file.exists():
            context.add_signal(
                ContextSource.CURRENT_FILE,
                str(current_file),
                confidence=0.8,
                metadata={"file_type": current_file.suffix},
            )

        # Add image context
        if current_image and current_image.exists():
            context.add_signal(
                ContextSource.CURRENT_IMAGE,
                str(current_image),
                confidence=0.8,
                metadata={"file_type": current_image.suffix},
            )

        # Add screen context if available
        if screen_state:
            context.screen_text = screen_state.get("ocr_text")
            context.add_signal(
                ContextSource.SCREEN_STATE,
                screen_state,
                confidence=0.6,
                metadata={"has_text": bool(context.screen_text)},
            )

        logger.debug(f"Built context with {len(context.signals)} signals")
        return context

    def decide_response_strategy(self, context: ContextModel) -> ContextDecision:
        """
        Decide on the best response strategy based on context.

        Args:
            context: Context model

        Returns:
            ContextDecision enum value
        """
        # Check if there's a file to analyze
        if context.current_file and context.user_query:
            if any(
                word in context.user_query.lower()
                for word in ["analyze", "read", "summarize", "what"]
            ):
                return ContextDecision.ANALYZE_FILE

        # Check if there's an image to analyze
        if context.current_image and context.user_query:
            if any(
                word in context.user_query.lower() for word in ["analyze", "what", "skin", "check"]
            ):
                return ContextDecision.ANALYZE_IMAGE

        # Check if context is unclear
        if not context.user_query or len(context.user_query) < 3:
            if context.memory_results:
                return ContextDecision.SHOW_SUGGESTION
            return ContextDecision.ASK_CLARIFICATION

        # Check if there's strong memory match
        if context.memory_results:
            top_result = context.memory_results[0]
            if top_result.relevance_score > self.suggestion_threshold:
                return ContextDecision.COMBINED_RESPONSE

        # Check for active routine
        if context.active_routine:
            return ContextDecision.TRIGGER_REMINDER

        # Default to direct response
        return ContextDecision.DIRECT_RESPONSE

    def generate_proactive_suggestions(self, context: ContextModel) -> List[str]:
        """
        Generate proactive suggestions based on context.

        Args:
            context: Context model

        Returns:
            List of suggestion strings
        """
        suggestions = []

        # File-related suggestions
        if context.current_file:
            suggestions.append(f"Would you like me to analyze {context.current_file.name}?")

        # Image-related suggestions
        if context.current_image:
            suggestions.append("Would you like me to analyze this image?")

        # Memory-based suggestions
        if context.memory_results:
            top_result = context.memory_results[0]
            if top_result.relevance_score > 0.6:
                suggestions.append(
                    f"I found relevant information about {top_result.entry.key}. Would you like me to elaborate?"
                )

        # Context-conflict suggestions
        conflicts = self.hybrid_retrieval.detect_conflicts(context.user_query or "")
        if conflicts:
            suggestions.append("I noticed some conflicting information. Should I clarify?")

        return suggestions[:3]  # Limit to 3 suggestions

    def analyze_with_context(self, context: ContextModel) -> Dict[str, Any]:
        """
        Analyze context and provide integrated response.

        Args:
            context: Context model

        Returns:
            Dictionary with analysis results
        """
        decision = self.decide_response_strategy(context)

        result = {
            "decision": decision.value,
            "context_summary": {
                "has_query": bool(context.user_query),
                "has_file": bool(context.current_file),
                "has_image": bool(context.current_image),
                "memory_matches": len(context.memory_results),
                "context_signals": len(context.signals),
            },
            "suggestions": [],
            "analysis": None,
        }

        # Execute based on decision
        if decision == ContextDecision.ANALYZE_FILE and context.current_file:
            try:
                file_result = self.local_analyzer.analyze_document(context.current_file)
                result["analysis"] = file_result.to_dict()
            except Exception as e:
                logger.error(f"File analysis failed: {e}")
                result["analysis"] = {"error": str(e)}

        elif decision == ContextDecision.ANALYZE_IMAGE and context.current_image:
            try:
                image_result = self.local_analyzer.analyze_image(context.current_image)
                result["analysis"] = image_result.to_dict()
            except Exception as e:
                logger.error(f"Image analysis failed: {e}")
                result["analysis"] = {"error": str(e)}

        # Generate suggestions
        result["suggestions"] = self.generate_proactive_suggestions(context)

        return result


# Global instance
_multimodal_context: Optional[MultimodalContext] = None


def get_multimodal_context() -> MultimodalContext:
    """Get the global multimodal context instance."""
    global _multimodal_context
    if _multimodal_context is None:
        _multimodal_context = MultimodalContext()
    return _multimodal_context
