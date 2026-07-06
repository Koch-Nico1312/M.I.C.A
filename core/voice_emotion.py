"""
Voice Emotional Analysis
Detects user frustration or urgency to adjust M.I.C.A's tone
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

try:
    import librosa
    import soundfile as sf

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

from config.config_loader import get_config


@dataclass
class EmotionResult:
    """Result of emotion analysis"""

    emotion: str  # neutral, happy, sad, angry, frustrated, urgent
    confidence: float
    pitch_mean: float
    pitch_std: float
    energy: float
    speech_rate: float


class VoiceEmotionAnalyzer:
    """Analyzes voice for emotional cues"""

    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get("emotion.enabled", False)
        self.sensitivity = self.config.get("emotion.sensitivity", 0.5)
        self.adjust_tone = self.config.get("emotion.adjust_tone", True)

        # Emotion thresholds
        self.urgency_pitch_threshold = 200.0  # Hz
        self.frustration_energy_threshold = 0.7
        self.anger_pitch_std_threshold = 50.0

        if self.enabled and LIBROSA_AVAILABLE:
            print(f"[Emotion] ✅ Initialized (sensitivity: {self.sensitivity})")
        elif not LIBROSA_AVAILABLE:
            print("[Emotion] ⚠️ Librosa not available")

    def analyze_audio(
        self, audio_data: np.ndarray, sample_rate: int = 16000
    ) -> Optional[EmotionResult]:
        """Analyze audio for emotional cues"""
        if not self.enabled or not LIBROSA_AVAILABLE:
            return None

        try:
            # Extract features
            pitch = self._extract_pitch(audio_data, sample_rate)
            energy = self._extract_energy(audio_data)
            speech_rate = self._estimate_speech_rate(audio_data, sample_rate)

            pitch_mean = np.mean(pitch) if len(pitch) > 0 else 0
            pitch_std = np.std(pitch) if len(pitch) > 0 else 0

            # Classify emotion
            emotion, confidence = self._classify_emotion(pitch_mean, pitch_std, energy, speech_rate)

            return EmotionResult(
                emotion=emotion,
                confidence=confidence,
                pitch_mean=pitch_mean,
                pitch_std=pitch_std,
                energy=energy,
                speech_rate=speech_rate,
            )

        except Exception as e:
            print(f"[Emotion] ❌ Analysis error: {e}")
            return None

    def _extract_pitch(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract pitch using librosa"""
        pitches, magnitudes = librosa.piptrack(y=audio, sr=sr, threshold=0.1, fmin=50, fmax=500)

        # Get the pitch with maximum magnitude for each frame
        pitch_values = []
        for i in range(pitches.shape[1]):
            index = magnitudes[:, i].argmax()
            pitch = pitches[index, i]
            if pitch > 0:
                pitch_values.append(pitch)

        return np.array(pitch_values)

    def _extract_energy(self, audio: np.ndarray) -> float:
        """Extract RMS energy"""
        return float(np.sqrt(np.mean(audio**2)))

    def _estimate_speech_rate(self, audio: np.ndarray, sr: int) -> float:
        """Estimate speech rate (syllables per second)"""
        # Simple estimation based on zero crossings
        zero_crossings = np.sum(np.diff(np.sign(audio)) != 0)
        duration = len(audio) / sr
        return zero_crossings / duration if duration > 0 else 0

    def _classify_emotion(
        self, pitch_mean: float, pitch_std: float, energy: float, speech_rate: float
    ) -> Tuple[str, float]:
        """Classify emotion based on features"""
        scores = {
            "neutral": 0.5,
            "happy": 0.0,
            "sad": 0.0,
            "angry": 0.0,
            "frustrated": 0.0,
            "urgent": 0.0,
        }

        # Urgency: high pitch, high energy, fast speech
        if pitch_mean > self.urgency_pitch_threshold:
            scores["urgent"] += 0.4
            scores["angry"] += 0.2

        # Frustration: high energy, variable pitch
        if energy > self.frustration_energy_threshold:
            scores["frustrated"] += 0.3
            scores["angry"] += 0.2

        # Anger: high pitch variability, high energy
        if pitch_std > self.anger_pitch_std_threshold:
            scores["angry"] += 0.4
            scores["frustrated"] += 0.2

        # Happy: moderate pitch, moderate energy
        if 100 < pitch_mean < 200 and 0.3 < energy < 0.7:
            scores["happy"] += 0.3

        # Sad: low pitch, low energy
        if pitch_mean < 100 and energy < 0.3:
            scores["sad"] += 0.4

        # Find highest scoring emotion
        emotion = max(scores, key=scores.get)
        confidence = scores[emotion]

        return emotion, confidence

    def get_tone_adjustment(self, emotion: str) -> Dict[str, str]:
        """Get tone adjustment based on detected emotion"""
        if not self.adjust_tone:
            return {}

        adjustments = {
            "neutral": {"style": "casual", "pace": "normal", "formality": "medium"},
            "happy": {"style": "enthusiastic", "pace": "normal", "formality": "low"},
            "sad": {"style": "gentle", "pace": "slow", "formality": "medium"},
            "angry": {"style": "calm", "pace": "slow", "formality": "high"},
            "frustrated": {"style": "direct", "pace": "fast", "formality": "high"},
            "urgent": {"style": "concise", "pace": "fast", "formality": "high"},
        }

        return adjustments.get(emotion, adjustments["neutral"])

    def format_response_for_emotion(self, response: str, emotion: str) -> str:
        """Adjust response based on detected emotion"""
        if not self.adjust_tone or emotion == "neutral":
            return response

        tone = self.get_tone_adjustment(emotion)

        if emotion in ["angry", "frustrated"]:
            # Be more direct and concise
            if len(response) > 100:
                response = response[:100] + "..."

        elif emotion == "urgent":
            # Be very concise
            words = response.split()
            if len(words) > 10:
                response = " ".join(words[:10]) + "..."

        elif emotion == "sad":
            # Be more gentle
            if not response.startswith("Sir, "):
                response = "Sir, " + response.lower()

        return response


# Global instance
_emotion_analyzer: Optional[VoiceEmotionAnalyzer] = None


def get_emotion_analyzer() -> VoiceEmotionAnalyzer:
    """Get the global emotion analyzer instance"""
    global _emotion_analyzer
    if _emotion_analyzer is None:
        _emotion_analyzer = VoiceEmotionAnalyzer()
    return _emotion_analyzer
