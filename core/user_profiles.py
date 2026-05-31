"""
Multi-User Speaker Recognition and User Profiles
==================================================
Implements Nova's speaker profiling system for identifying different users
by voice characteristics and loading personalized memory data, settings,
and greeting styles for each person.
"""

import json
import random
import sqlite3
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("[User Profiles] ⚠️ NumPy not available. Voice features will be limited.")


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
USER_PROFILES_DB = BASE_DIR / "data" / "user_profiles.db"
_lock = threading.Lock()


@dataclass
class VoiceProfile:
    """Voice characteristics for speaker identification."""
    profile_id: str
    user_id: str
    voice_features: Dict[str, float] = field(default_factory=dict)
    pitch_mean: float = 0.0
    pitch_std: float = 0.0
    energy_mean: float = 0.0
    energy_std: float = 0.0
    spectral_centroid_mean: float = 0.0
    spectral_centroid_std: float = 0.0
    created_at: str = ""
    last_updated: str = ""
    sample_count: int = 0


@dataclass
class UserProfile:
    """Complete user profile with preferences and memory."""
    user_id: str
    name: str
    voice_profile_id: Optional[str] = None
    greeting_style: str = "formal"  # formal, casual, friendly
    language: str = "en"
    timezone: str = "UTC"
    permission_level: str = "normal"  # safe, normal, admin
    preferences: Dict[str, Any] = field(default_factory=dict)
    memory_data: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    last_active: str = ""


class UserProfiles:
    """
    Manages user profiles and speaker recognition.
    Identifies users by voice and loads personalized settings.
    """
    
    def __init__(self, db_path: Path = USER_PROFILES_DB):
        self.db_path = db_path
        self._init_db()
        self._current_user: Optional[UserProfile] = None
        
    def _init_db(self) -> None:
        """Initialize the user profiles database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # User profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    voice_profile_id TEXT,
                    greeting_style TEXT DEFAULT 'formal',
                    language TEXT DEFAULT 'en',
                    timezone TEXT DEFAULT 'UTC',
                    permission_level TEXT DEFAULT 'normal',
                    preferences TEXT,
                    memory_data TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (voice_profile_id) REFERENCES voice_profiles(profile_id)
                )
            """)
            
            # Voice profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    profile_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    pitch_mean REAL,
                    pitch_std REAL,
                    energy_mean REAL,
                    energy_std REAL,
                    spectral_centroid_mean REAL,
                    spectral_centroid_std REAL,
                    voice_features TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sample_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)
            
            # Voice samples table (for training/improving recognition)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_samples (
                    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT NOT NULL,
                    audio_features TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES voice_profiles(profile_id)
                )
            """)
            
            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_profiles(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_voice_profile ON voice_profiles(profile_id)")
            
            conn.commit()
            conn.close()
    
    def create_user_profile(
        self,
        user_id: str,
        name: str,
        greeting_style: str = "formal",
        language: str = "en",
        permission_level: str = "normal"
    ) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(
            user_id=user_id,
            name=name,
            greeting_style=greeting_style,
            language=language,
            permission_level=permission_level,
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat()
        )
        
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO user_profiles
                (user_id, name, greeting_style, language, permission_level,
                 preferences, memory_data, created_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                name,
                greeting_style,
                language,
                permission_level,
                json.dumps(profile.preferences),
                json.dumps(profile.memory_data),
                profile.created_at,
                profile.last_active
            ))
            
            conn.commit()
            conn.close()
        
        print(f"[User Profiles] 👤 Created profile for {name} ({user_id})")
        return profile
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get a user profile by ID."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM user_profiles WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
        
        if result:
            return UserProfile(
                user_id=result[0],
                name=result[1],
                voice_profile_id=result[2],
                greeting_style=result[3],
                language=result[4],
                timezone=result[5],
                permission_level=result[6],
                preferences=json.loads(result[7]) if result[7] else {},
                memory_data=json.loads(result[8]) if result[8] else {},
                created_at=result[9],
                last_active=result[10]
            )
        return None
    
    def update_user_profile(self, profile: UserProfile) -> bool:
        """Update an existing user profile."""
        profile.last_active = datetime.now().isoformat()
        
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE user_profiles
                SET name = ?, greeting_style = ?, language = ?, timezone = ?,
                    permission_level = ?, preferences = ?, memory_data = ?, last_active = ?
                WHERE user_id = ?
            """, (
                profile.name,
                profile.greeting_style,
                profile.language,
                profile.timezone,
                profile.permission_level,
                json.dumps(profile.preferences),
                json.dumps(profile.memory_data),
                profile.last_active,
                profile.user_id
            ))
            
            conn.commit()
            conn.close()
        
        print(f"[User Profiles] 📝 Updated profile for {profile.name}")
        return True
    
    def create_voice_profile(
        self,
        user_id: str,
        audio_features: Optional[Dict[str, float]] = None
    ) -> VoiceProfile:
        """Create a voice profile for a user."""
        profile_id = f"voice_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        voice_profile = VoiceProfile(
            profile_id=profile_id,
            user_id=user_id,
            voice_features=audio_features or {},
            created_at=datetime.now().isoformat(),
            last_updated=datetime.now().isoformat()
        )
        
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO voice_profiles
                (profile_id, user_id, voice_features, created_at, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """, (
                profile_id,
                user_id,
                json.dumps(voice_profile.voice_features),
                voice_profile.created_at,
                voice_profile.last_updated
            ))
            
            # Link to user profile
            cursor.execute("""
                UPDATE user_profiles
                SET voice_profile_id = ?
                WHERE user_id = ?
            """, (profile_id, user_id))
            
            conn.commit()
            conn.close()
        
        print(f"[User Profiles] 🎤 Created voice profile {profile_id} for {user_id}")
        return voice_profile
    
    def update_voice_profile(
        self,
        profile_id: str,
        audio_features: Dict[str, float]
    ) -> bool:
        """Update a voice profile with new audio features."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current profile
            cursor.execute("""
                SELECT * FROM voice_profiles WHERE profile_id = ?
            """, (profile_id,))
            
            result = cursor.fetchone()
            if not result:
                conn.close()
                return False
            
            # Update with new features (simple averaging)
            current_features = json.loads(result[7]) if result[7] else {}
            sample_count = result[10] + 1
            
            # Merge features with weighted average
            merged_features = {}
            all_keys = set(current_features.keys()) | set(audio_features.keys())
            
            for key in all_keys:
                old_val = current_features.get(key, 0)
                new_val = audio_features.get(key, 0)
                # Weighted average: give more weight to recent samples
                merged_features[key] = (old_val * 0.7 + new_val * 0.3)
            
            cursor.execute("""
                UPDATE voice_profiles
                SET voice_features = ?, last_updated = ?, sample_count = ?
                WHERE profile_id = ?
            """, (
                json.dumps(merged_features),
                datetime.now().isoformat(),
                sample_count,
                profile_id
            ))
            
            conn.commit()
            conn.close()
        
        print(f"[User Profiles] 🎤 Updated voice profile {profile_id}")
        return True
    
    def identify_speaker(self, audio_features: Dict[str, float]) -> Optional[UserProfile]:
        """
        Identify a speaker based on audio features.
        Returns the matching user profile or None if no match found.
        """
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT profile_id, user_id, voice_features
                FROM voice_profiles
            """)
            
            results = cursor.fetchall()
            conn.close()
        
        if not results:
            return None
        
        best_match = None
        best_score = 0.0
        threshold = 0.7  # Similarity threshold
        
        for profile_id, user_id, features_json in results:
            stored_features = json.loads(features_json) if features_json else {}
            similarity = self._calculate_similarity(audio_features, stored_features)
            
            if similarity > best_score and similarity > threshold:
                best_score = similarity
                best_match = user_id
        
        if best_match:
            profile = self.get_user_profile(best_match)
            if profile:
                print(f"[User Profiles] 🔊 Identified speaker: {profile.name} (confidence: {best_score:.2f})")
                self._current_user = profile
                return profile
        
        print(f"[User Profiles] ❓ Unknown speaker (best match: {best_score:.2f})")
        return None
    
    def _calculate_similarity(self, features_a: Dict[str, float], features_b: Dict[str, float]) -> float:
        """Calculate similarity between two voice feature sets."""
        if not features_a or not features_b:
            return 0.0
        
        if NUMPY_AVAILABLE:
            # Use cosine similarity with numpy
            keys = set(features_a.keys()) & set(features_b.keys())
            if not keys:
                return 0.0
            
            vec_a = np.array([features_a[k] for k in keys])
            vec_b = np.array([features_b[k] for k in keys])
            
            dot_product = np.dot(vec_a, vec_b)
            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return dot_product / (norm_a * norm_b)
        else:
            # Fallback: simple Euclidean distance
            keys = set(features_a.keys()) & set(features_b.keys())
            if not keys:
                return 0.0
            
            sum_sq_diff = sum((features_a[k] - features_b[k]) ** 2 for k in keys)
            max_distance = sum(max(features_a[k], features_b[k]) ** 2 for k in keys)
            
            if max_distance == 0:
                return 1.0
            
            return 1.0 - (sum_sq_diff / max_distance)
    
    def get_current_user(self) -> Optional[UserProfile]:
        """Get the currently identified user."""
        return self._current_user
    
    def set_current_user(self, user_id: str) -> bool:
        """Manually set the current user."""
        profile = self.get_user_profile(user_id)
        if profile:
            self._current_user = profile
            profile.last_active = datetime.now().isoformat()
            self.update_user_profile(profile)
            print(f"[User Profiles] 👤 Set current user to {profile.name}")
            return True
        return False
    
    def get_greeting(self, user_id: Optional[str] = None) -> str:
        """Get a personalized greeting for a user."""
        profile = self.get_user_profile(user_id) if user_id else self._current_user
        
        if not profile:
            return "Hello there."
        
        greetings = {
            "formal": [
                f"Good {self._get_time_of_day()}, {profile.name}.",
                f"Welcome back, {profile.name}.",
                f"Greetings, {profile.name}."
            ],
            "casual": [
                f"Hey {profile.name}!",
                f"What's up, {profile.name}?",
                f"Hi {profile.name}!"
            ],
            "friendly": [
                f"Great to see you, {profile.name}!",
                f"Hello {profile.name}! How can I help you today?",
                f"Hey {profile.name}! Good to have you here."
            ]
        }
        
        style_greetings = greetings.get(profile.greeting_style, greetings["formal"])
        
        # Select greeting based on time of day
        return random.choice(style_greetings)
    
    def _get_time_of_day(self) -> str:
        """Get the current time of day (morning, afternoon, evening)."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        else:
            return "evening"
    
    def list_all_users(self) -> List[Dict[str, Any]]:
        """List all registered users."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, name, greeting_style, language, 
                       permission_level, last_active
                FROM user_profiles
                ORDER BY last_active DESC
            """)
            
            results = cursor.fetchall()
            conn.close()
        
        return [
            {
                "user_id": row[0],
                "name": row[1],
                "greeting_style": row[2],
                "language": row[3],
                "permission_level": row[4],
                "last_active": row[5]
            }
            for row in results
        ]
    
    def delete_user_profile(self, user_id: str) -> bool:
        """Delete a user profile and associated voice profile."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get voice profile ID
            cursor.execute("""
                SELECT voice_profile_id FROM user_profiles WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            
            # Delete voice profile if exists
            if result and result[0]:
                cursor.execute("""
                    DELETE FROM voice_profiles WHERE profile_id = ?
                """, (result[0],))
            
            # Delete user profile
            cursor.execute("""
                DELETE FROM user_profiles WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
            conn.close()
        
        print(f"[User Profiles] 🗑️ Deleted user {user_id}")
        return True


# Global instance management
_user_profiles: Optional[UserProfiles] = None
_profiles_lock = threading.Lock()


def get_user_profiles() -> UserProfiles:
    """Get the global user profiles instance."""
    global _user_profiles
    if _user_profiles is None:
        with _profiles_lock:
            if _user_profiles is None:
                _user_profiles = UserProfiles()
    return _user_profiles


__all__ = [
    "UserProfiles",
    "UserProfile",
    "VoiceProfile",
    "get_user_profiles"
]
