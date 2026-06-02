"""
Spotify Controller for JARVIS
Controls Spotify music playback using the Spotify Web API.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    SPOTIFY_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when spotipy is missing
    spotipy = None  # type: ignore[assignment]
    SpotifyOAuth = None  # type: ignore[assignment]
    SPOTIFY_AVAILABLE = False

from config.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

_SPOTIFY_URL_RE = re.compile(
    r"^https?://open\.spotify\.com/(track|album|playlist|artist)/([A-Za-z0-9]+)",
    re.IGNORECASE,
)
_SPOTIFY_URI_RE = re.compile(
    r"^spotify:(track|album|playlist|artist):([A-Za-z0-9]+)$",
    re.IGNORECASE,
)

_PLAY_PREFIX_RE = re.compile(
    r"^(?:play|start|resume|listen to|put on)\s+",
    re.IGNORECASE,
)

_TARGET_PREFIX_RE = re.compile(
    r"^(playlist|album|artist|track|song)\s*[:\-]?\s*(.+)$",
    re.IGNORECASE,
)

_LIKED_QUERY_RE = re.compile(
    r"\b(liked songs?|my likes?|favorites?|favourites?)\b",
    re.IGNORECASE,
)


def _coerce_int(
    value: Any, default: int, minimum: int | None = None, maximum: int | None = None
) -> int:
    try:
        number = int(value)
    except Exception:
        number = default

    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return default


class SpotifyController:
    """Manages Spotify playback control."""

    SCOPES = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "playlist-read-private",
        "user-library-read",
    ]

    CACHE_TTLS = {
        "current": 3.0,
        "devices": 10.0,
        "search": 15.0,
        "playlists": 30.0,
        "liked": 30.0,
    }

    def __init__(self, sp_client: Optional[Any] = None) -> None:
        self.config = get_config()
        self.sp = sp_client
        self.cache_path: Optional[Path] = None
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.RLock()

        if self.sp is not None:
            logger.info("Spotify controller initialized with injected client")
            return

        if not SPOTIFY_AVAILABLE:
            logger.warning("Spotify integration unavailable: spotipy is not installed")
            return

        client_id = self.config.get("spotify.client_id", "")
        client_secret = self.config.get("spotify.client_secret", "")
        redirect_uri = self.config.get("spotify.redirect_uri", "http://localhost:8888/callback")

        if not client_id or not client_secret:
            logger.warning("Spotify integration disabled: client ID or client secret missing")
            return

        base_dir = Path(self.config.get("paths.base_dir", "."))
        self.cache_path = base_dir / "config" / "spotify_token_cache"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    scope=" ".join(self.SCOPES),
                    cache_path=str(self.cache_path),
                    open_browser=False,
                )
            )
            logger.info("Spotify controller initialized")
        except Exception as e:
            logger.exception("Spotify initialization failed: %s", e)

    def _available(self) -> bool:
        return self.sp is not None

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_kind(kind: Any, default: str = "track") -> str:
        text = str(kind or default).strip().lower()
        if text in {"song"}:
            return "track"
        if text in {"any", "all"}:
            return "any"
        if text not in {"track", "album", "playlist", "artist"}:
            return default
        return text

    @staticmethod
    def _normalize_repeat_state(state: Any) -> str:
        text = str(state or "off").strip().lower()
        aliases = {
            "off": "off",
            "track": "track",
            "song": "track",
            "context": "context",
            "album": "context",
            "playlist": "context",
            "on": "context",
            "all": "context",
        }
        return aliases.get(text, "off")

    @staticmethod
    def _normalize_shuffle_state(state: Any) -> bool:
        return _coerce_bool(state, default=True)

    @staticmethod
    def _extract_reference(query: str) -> tuple[Optional[str], Optional[str]]:
        text = query.strip()
        uri_match = _SPOTIFY_URI_RE.match(text)
        if uri_match:
            kind = uri_match.group(1).lower()
            track_id = uri_match.group(2)
            return kind, f"spotify:{kind}:{track_id}"

        url_match = _SPOTIFY_URL_RE.match(text)
        if url_match:
            kind = url_match.group(1).lower()
            track_id = url_match.group(2)
            return kind, f"spotify:{kind}:{track_id}"

        return None, None

    @staticmethod
    def _strip_play_prefix(query: str) -> str:
        stripped = _PLAY_PREFIX_RE.sub("", query.strip(), count=1)
        return stripped.strip()

    @staticmethod
    def _extract_target_prefix(query: str) -> tuple[Optional[str], str]:
        match = _TARGET_PREFIX_RE.match(query.strip())
        if not match:
            return None, query.strip()
        kind = match.group(1).lower()
        remainder = match.group(2).strip()
        return kind, remainder

    @staticmethod
    def _is_liked_query(query: str) -> bool:
        return bool(_LIKED_QUERY_RE.search(query))

    def _cache_get(self, key: str, refresh: bool = False) -> Any | None:
        if refresh:
            return None
        with self._cache_lock:
            cached = self._cache.get(key)
            if not cached:
                return None
            expires_at, value = cached
            if expires_at <= time.monotonic():
                self._cache.pop(key, None)
                return None
            return value

    def _cache_set(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self._cache_lock:
            self._cache[key] = (time.monotonic() + ttl_seconds, value)

    def _search_items(
        self,
        query: str,
        search_type: str = "track",
        limit: int = 5,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        if not self.sp:
            return []

        search_type = self._normalize_kind(search_type)
        limit = _coerce_int(limit, 5, minimum=1, maximum=10)
        cache_key = f"search|{search_type}|{limit}|{query.lower()}"

        cached = self._cache_get(cache_key, refresh=refresh)
        if cached is not None:
            return cached

        result = self.sp.search(q=query, type=search_type, limit=limit)
        bucket_name = f"{search_type}s"
        items = list(result.get(bucket_name, {}).get("items", []))
        self._cache_set(cache_key, items, self.CACHE_TTLS["search"])
        return items

    def _get_current_playback(self, refresh: bool = False) -> dict[str, Any] | None:
        if not self.sp:
            return None

        cache_key = "current|playback"
        cached = self._cache_get(cache_key, refresh=refresh)
        if cached is not None:
            return cached

        playback = None
        try:
            playback = self.sp.current_playback()
        except Exception:
            playback = None

        if not playback:
            try:
                playback = self.sp.current_user_playing_track()
            except Exception:
                playback = None

        if playback:
            self._cache_set(cache_key, playback, self.CACHE_TTLS["current"])
        return playback

    def _get_devices(self, refresh: bool = False) -> list[dict[str, Any]]:
        if not self.sp:
            return []

        cache_key = "devices|all"
        cached = self._cache_get(cache_key, refresh=refresh)
        if cached is not None:
            return cached

        try:
            payload = self.sp.devices() or {}
        except Exception:
            payload = {}

        devices = list(payload.get("devices", []))
        self._cache_set(cache_key, devices, self.CACHE_TTLS["devices"])
        return devices

    def _get_playlists(self, refresh: bool = False) -> list[dict[str, Any]]:
        if not self.sp:
            return []

        cache_key = "playlists|current"
        cached = self._cache_get(cache_key, refresh=refresh)
        if cached is not None:
            return cached

        try:
            payload = self.sp.current_user_playlists(limit=20) or {}
        except Exception:
            payload = {}

        playlists = list(payload.get("items", []))
        self._cache_set(cache_key, playlists, self.CACHE_TTLS["playlists"])
        return playlists

    def _get_liked_tracks(self, refresh: bool = False) -> list[dict[str, Any]]:
        if not self.sp:
            return []

        cache_key = "liked|tracks"
        cached = self._cache_get(cache_key, refresh=refresh)
        if cached is not None:
            return cached

        try:
            payload = self.sp.current_user_saved_tracks(limit=50) or {}
        except Exception:
            payload = {}

        items = [item.get("track", {}) for item in payload.get("items", []) if item.get("track")]
        self._cache_set(cache_key, items, self.CACHE_TTLS["liked"])
        return items

    @staticmethod
    def _format_track(track: dict[str, Any], index: Optional[int] = None) -> str:
        artists = ", ".join(artist.get("name", "Unknown") for artist in track.get("artists", []))
        prefix = f"{index}. " if index is not None else ""
        return f"{prefix}{track.get('name', 'Unknown')} by {artists or 'Unknown'}"

    @staticmethod
    def _format_album(album: dict[str, Any], index: Optional[int] = None) -> str:
        artists = ", ".join(artist.get("name", "Unknown") for artist in album.get("artists", []))
        prefix = f"{index}. " if index is not None else ""
        return f"{prefix}{album.get('name', 'Unknown')} by {artists or 'Unknown'}"

    @staticmethod
    def _format_playlist(playlist: dict[str, Any], index: Optional[int] = None) -> str:
        owner = playlist.get("owner", {}).get("display_name") or "Unknown"
        prefix = f"{index}. " if index is not None else ""
        return f"{prefix}{playlist.get('name', 'Unknown')} by {owner}"

    @staticmethod
    def _format_artist(artist: dict[str, Any], index: Optional[int] = None) -> str:
        prefix = f"{index}. " if index is not None else ""
        return f"{prefix}{artist.get('name', 'Unknown')}"

    def _format_section(self, search_type: str, query: str, items: list[dict[str, Any]]) -> str:
        label = {
            "track": "tracks",
            "album": "albums",
            "playlist": "playlists",
            "artist": "artists",
        }.get(search_type, search_type)

        lines = [f"Found {len(items)} {label} for '{query}':"]
        for index, item in enumerate(items[:10], start=1):
            if search_type == "track":
                lines.append(self._format_track(item, index))
            elif search_type == "album":
                lines.append(self._format_album(item, index))
            elif search_type == "playlist":
                lines.append(self._format_playlist(item, index))
            elif search_type == "artist":
                lines.append(self._format_artist(item, index))
            else:
                lines.append(f"{index}. {item.get('name', 'Unknown')}")
        return "\n".join(lines)

    def _play_best_match(self, query: str, order: tuple[str, ...]) -> str:
        for search_type in order:
            result = self._play_by_type(query, search_type, fallback=False)
            if not result.startswith("No "):
                return result
        return f"No Spotify results found for '{query}', sir."

    def _play_by_type(self, query: str, search_type: str, fallback: bool = True) -> str:
        if not self.sp:
            return "Spotify not available, sir."

        search_type = self._normalize_kind(search_type)
        query = self._normalize_text(query)
        if not query:
            return "Please provide a search query, sir."

        items = self._search_items(query, search_type, limit=1)
        if not items and fallback and search_type == "track":
            return self._play_best_match(query, ("album", "playlist", "artist"))

        if not items:
            return f"No {search_type}s found for '{query}', sir."

        item = items[0]
        try:
            if search_type == "track":
                self.sp.start_playback(uris=[item["uri"]])
                logger.info("Spotify playing track: %s", item.get("name"))
                return f"Playing {self._format_track(item)}, sir."

            self.sp.start_playback(context_uri=item["uri"])
            logger.info("Spotify playing %s: %s", search_type, item.get("name"))
            if search_type == "playlist":
                return f"Playing playlist {self._format_playlist(item)}, sir."
            if search_type == "album":
                return f"Playing album {self._format_album(item)}, sir."
            if search_type == "artist":
                return f"Playing artist {self._format_artist(item)}, sir."
        except Exception as e:
            logger.exception("Spotify play failed: %s", e)
            return f"Failed to play: {e}"

        return f"Playing {search_type} {item.get('name', 'Unknown')}, sir."

    def play(self, query: str = None, kind: str = "track") -> str:
        """Play a song, playlist, album, or artist."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            if not query:
                self.sp.start_playback()
                logger.info("Spotify playback resumed")
                return "Resumed playback, sir."

            query = self._normalize_text(query)
            if not query:
                self.sp.start_playback()
                logger.info("Spotify playback resumed")
                return "Resumed playback, sir."

            stripped_query = self._strip_play_prefix(query)
            if self._is_liked_query(stripped_query):
                return self.liked()

            target_kind = self._normalize_kind(kind)
            prefix_kind, prefix_query = self._extract_target_prefix(stripped_query)
            if prefix_kind:
                target_kind = "track" if prefix_kind == "song" else prefix_kind
                stripped_query = prefix_query

            parsed_kind, parsed_uri = self._extract_reference(stripped_query)
            if parsed_uri:
                if parsed_kind == "track":
                    self.sp.start_playback(uris=[parsed_uri])
                    return "Playing the requested Spotify track, sir."
                self.sp.start_playback(context_uri=parsed_uri)
                return f"Playing the requested Spotify {parsed_kind}, sir."

            if target_kind == "any":
                return self._play_best_match(
                    stripped_query, ("track", "album", "playlist", "artist")
                )

            return self._play_by_type(stripped_query, target_kind)
        except Exception as e:
            logger.exception("Spotify play error: %s", e)
            return f"Failed to play: {e}"

    def pause(self) -> str:
        """Pause playback."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            self.sp.pause_playback()
            logger.info("Spotify paused")
            return "Paused, sir."
        except Exception as e:
            logger.exception("Spotify pause error: %s", e)
            return f"Failed to pause: {e}"

    def resume(self) -> str:
        """Resume playback."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            self.sp.start_playback()
            logger.info("Spotify resumed")
            return "Resumed, sir."
        except Exception as e:
            logger.exception("Spotify resume error: %s", e)
            return f"Failed to resume: {e}"

    def next(self) -> str:
        """Skip to next track."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            self.sp.next_track()
            logger.info("Spotify skipped to next track")
            return "Skipped to next track, sir."
        except Exception as e:
            logger.exception("Spotify next error: %s", e)
            return f"Failed to skip: {e}"

    def previous(self) -> str:
        """Skip to previous track."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            self.sp.previous_track()
            logger.info("Spotify skipped to previous track")
            return "Skipped to previous track, sir."
        except Exception as e:
            logger.exception("Spotify previous error: %s", e)
            return f"Failed to skip: {e}"

    def current(self, refresh: bool = False) -> str:
        """Get currently playing track."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            current = self._get_current_playback(refresh=refresh)
            if current and current.get("item"):
                track = current["item"]
                name = track.get("name", "Unknown")
                artists = (
                    ", ".join(a.get("name", "Unknown") for a in track.get("artists", []))
                    or "Unknown"
                )
                album = track.get("album", {}).get("name", "Unknown")
                is_playing = current.get("is_playing", False)
                status = "Playing" if is_playing else "Paused"
                device = current.get("device", {}).get("name")
                progress_ms = current.get("progress_ms")
                duration_ms = track.get("duration_ms")
                progress_text = ""
                if (
                    isinstance(progress_ms, int)
                    and isinstance(duration_ms, int)
                    and duration_ms > 0
                ):
                    progress_text = f" ({progress_ms // 1000}/{duration_ms // 1000}s)"
                device_text = f" on {device}" if device else ""
                logger.info("Spotify current track: %s", name)
                return f"{status}: {name} by {artists} from {album}{progress_text}{device_text}"

            return "Nothing is currently playing, sir."
        except Exception as e:
            logger.exception("Spotify current error: %s", e)
            return f"Failed to get current track: {e}"

    def volume(self, value: int) -> str:
        """Set volume (0-100)."""
        if not self.sp:
            return "Spotify not available, sir."

        value = _coerce_int(value, 50, minimum=0, maximum=100)

        try:
            self.sp.volume(value)
            logger.info("Spotify volume set to %s", value)
            return f"Volume set to {value}, sir."
        except Exception as e:
            logger.exception("Spotify volume error: %s", e)
            return f"Failed to set volume: {e}"

    def search(
        self, query: str, search_type: str = "track", limit: int = 5, refresh: bool = False
    ) -> str:
        """Search for music."""
        if not self.sp:
            return "Spotify not available, sir."

        query = self._normalize_text(query)
        if not query:
            return "Please provide a search query, sir."

        search_type = self._normalize_kind(search_type, default="track")
        limit = _coerce_int(limit, 5, minimum=1, maximum=10)

        try:
            if search_type == "any":
                sections = []
                for kind in ("track", "album", "playlist", "artist"):
                    items = self._search_items(query, kind, limit=limit, refresh=refresh)
                    if items:
                        sections.append(self._format_section(kind, query, items))
                if not sections:
                    return f"No Spotify results found for '{query}', sir."
                return "\n\n".join(sections)

            items = self._search_items(query, search_type, limit=limit, refresh=refresh)
            if not items:
                return f"No {search_type}s found for '{query}', sir."

            return self._format_section(search_type, query, items)
        except Exception as e:
            logger.exception("Spotify search error: %s", e)
            return f"Failed to search: {e}"

    def queue(self, query: str) -> str:
        """Add a song to the queue."""
        if not self.sp:
            return "Spotify not available, sir."

        query = self._normalize_text(query)
        if not query:
            return "Please provide a song to queue, sir."

        try:
            parsed_kind, parsed_uri = self._extract_reference(query)
            if parsed_uri and parsed_kind == "track":
                self.sp.add_to_queue(uri=parsed_uri)
                return "Added the requested track to queue, sir."

            items = self._search_items(query, "track", limit=1)
            if not items:
                return f"No results found for '{query}', sir."

            track = items[0]
            self.sp.add_to_queue(uri=track["uri"])
            logger.info("Spotify added to queue: %s", track.get("name"))
            return f"Added {self._format_track(track)} to queue, sir."
        except Exception as e:
            logger.exception("Spotify queue error: %s", e)
            return f"Failed to add to queue: {e}"

    def playlists(self, refresh: bool = False) -> str:
        """List user playlists."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            playlists = self._get_playlists(refresh=refresh)
            if not playlists:
                return "No playlists found, sir."

            lines = [f"Found {len(playlists)} playlists:"]
            for index, playlist in enumerate(playlists[:20], start=1):
                lines.append(self._format_playlist(playlist, index))
            return "\n".join(lines)
        except Exception as e:
            logger.exception("Spotify playlists error: %s", e)
            return f"Failed to get playlists: {e}"

    def shuffle(self, state: str) -> str:
        """Toggle shuffle on or off."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            shuffle_state = self._normalize_shuffle_state(state)
            self.sp.shuffle(state=shuffle_state)
            logger.info("Spotify shuffle set to %s", shuffle_state)
            return f"Shuffle set to {'on' if shuffle_state else 'off'}, sir."
        except Exception as e:
            logger.exception("Spotify shuffle error: %s", e)
            return f"Failed to set shuffle: {e}"

    def repeat(self, state: str) -> str:
        """Set repeat mode."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            repeat_state = self._normalize_repeat_state(state)
            self.sp.repeat(state=repeat_state)
            logger.info("Spotify repeat set to %s", repeat_state)
            return f"Repeat set to {repeat_state}, sir."
        except Exception as e:
            logger.exception("Spotify repeat error: %s", e)
            return f"Failed to set repeat: {e}"

    def devices(self, refresh: bool = False) -> str:
        """List available devices."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            devices = self._get_devices(refresh=refresh)
            if not devices:
                return "No devices found, sir."

            lines = [f"Found {len(devices)} devices:"]
            for index, device in enumerate(devices[:20], start=1):
                status = " (Active)" if device.get("is_active") else ""
                lines.append(
                    f"{index}. {device.get('name', 'Unknown')} ({device.get('type', 'Unknown')}){status}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.exception("Spotify devices error: %s", e)
            return f"Failed to get devices: {e}"

    def transfer(self, device_name: str) -> str:
        """Transfer playback to another device."""
        if not self.sp:
            return "Spotify not available, sir."

        device_name = self._normalize_text(device_name)
        if not device_name:
            return "Please provide a device name, sir."

        try:
            devices = self._get_devices(refresh=True)
            target = None
            needle = device_name.lower()

            for device in devices:
                name = str(device.get("name", "")).lower()
                if name == needle:
                    target = device
                    break

            if target is None:
                for device in devices:
                    name = str(device.get("name", "")).lower()
                    if needle in name:
                        target = device
                        break

            if target is None:
                return f"Device '{device_name}' not found, sir."

            self.sp.transfer_playback(device_id=target["id"], force_play=True)
            logger.info("Spotify transferred to %s", target.get("name"))
            return f"Transferred playback to {target.get('name', device_name)}, sir."
        except Exception as e:
            logger.exception("Spotify transfer error: %s", e)
            return f"Failed to transfer: {e}"

    def liked(self, refresh: bool = False) -> str:
        """Play liked songs."""
        if not self.sp:
            return "Spotify not available, sir."

        try:
            tracks = self._get_liked_tracks(refresh=refresh)
            if not tracks:
                return "No liked songs found, sir."

            uris = [track["uri"] for track in tracks if track.get("uri")]
            if not uris:
                return "No playable liked songs found, sir."

            self.sp.start_playback(uris=uris[:50])
            logger.info("Spotify playing liked songs (%s tracks)", len(uris[:50]))
            return f"Playing your liked songs ({min(len(uris), 50)} tracks), sir."
        except Exception as e:
            logger.exception("Spotify liked songs error: %s", e)
            return f"Failed to play liked songs: {e}"


# Global instance
_spotify_controller: Optional[SpotifyController] = None


def get_spotify_controller() -> SpotifyController:
    """Get the global Spotify controller instance."""
    global _spotify_controller
    if _spotify_controller is None:
        _spotify_controller = SpotifyController()
    return _spotify_controller


def spotify_controller(
    parameters: dict, response=None, player=None, speak: Callable = None, session_memory=None
) -> str:
    """
    Spotify control tool for JARVIS.

    Actions:
    - play: Play a song, album, playlist, artist, or direct Spotify URL/URI
    - pause: Pause playback
    - resume: Resume playback
    - next: Skip to next track
    - previous: Skip to previous track
    - current: Show currently playing track
    - volume: Set volume (0-100)
    - search: Search for music
    - queue: Add a track to the queue
    - playlists: List user playlists
    - shuffle: Toggle shuffle (on/off)
    - repeat: Set repeat mode (off/track/context)
    - devices: List available devices
    - transfer: Transfer playback to another device
    - liked: Play liked songs
    """
    action = str(parameters.get("action", "current") or "current").strip().lower()
    refresh = _coerce_bool(parameters.get("refresh"), default=False)

    spotify = get_spotify_controller()

    if action == "play":
        query = parameters.get("query")
        kind = parameters.get("kind", parameters.get("type", "track"))
        result = spotify.play(query, kind=kind)
        if speak:
            speak(result)
        return result

    if action == "pause":
        result = spotify.pause()
        if speak:
            speak(result)
        return result

    if action == "resume":
        result = spotify.resume()
        if speak:
            speak(result)
        return result

    if action == "next":
        result = spotify.next()
        if speak:
            speak(result)
        return result

    if action == "previous":
        result = spotify.previous()
        if speak:
            speak(result)
        return result

    if action == "current":
        result = spotify.current(refresh=refresh)
        if speak:
            speak(result)
        return result

    if action == "volume":
        value = parameters.get("value")
        if value is None:
            return "Please provide a volume level (0-100), sir."
        result = spotify.volume(value)
        if speak:
            speak(result)
        return result

    if action == "search":
        query = parameters.get("query")
        search_type = parameters.get("type", "track")
        limit = parameters.get("limit", 5)
        if not query:
            return "Please provide a search query, sir."
        result = spotify.search(query, search_type, limit=limit, refresh=refresh)
        if speak:
            speak(result if result.startswith("No ") else f"Found results for {query}, sir.")
        return result

    if action == "queue":
        query = parameters.get("query")
        if not query:
            return "Please provide a song to queue, sir."
        result = spotify.queue(query)
        if speak:
            speak(result)
        return result

    if action == "playlists":
        result = spotify.playlists(refresh=refresh)
        if speak:
            speak("Found your playlists, sir.")
        return result

    if action == "shuffle":
        state = parameters.get("state", "on")
        result = spotify.shuffle(state)
        if speak:
            speak(result)
        return result

    if action == "repeat":
        state = parameters.get("state", "off")
        result = spotify.repeat(state)
        if speak:
            speak(result)
        return result

    if action == "devices":
        result = spotify.devices(refresh=refresh)
        if speak:
            speak("Found your available devices, sir.")
        return result

    if action == "transfer":
        device_name = parameters.get("device_name")
        if not device_name:
            return "Please provide a device name, sir."
        result = spotify.transfer(device_name)
        if speak:
            speak(result)
        return result

    if action == "liked":
        result = spotify.liked(refresh=refresh)
        if speak:
            speak(result)
        return result

    return (
        "Unknown action: "
        f"{action}. Available: play, pause, resume, next, previous, current, volume, "
        "search, queue, playlists, shuffle, repeat, devices, transfer, liked"
    )
