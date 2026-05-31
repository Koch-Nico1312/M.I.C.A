"""
Spotify Web API controller for JARVIS.
Controls playback, search, queues, playlists, devices, shuffle, repeat, and volume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIFY_AVAILABLE = True
except ImportError:
    SPOTIFY_AVAILABLE = False

from config.config_loader import get_config


class SpotifyController:
    """Manages Spotify Web API playback operations."""

    SCOPES = (
        "user-read-playback-state "
        "user-modify-playback-state "
        "user-read-currently-playing "
        "playlist-read-private "
        "user-library-read"
    )

    def __init__(self) -> None:
        self.config = get_config()
        self.client: Optional[Any] = None
        self._authenticate()

    def _authenticate(self) -> bool:
        """Authenticate with Spotify API."""
        if not SPOTIFY_AVAILABLE:
            print("[Spotify] ⚠️ spotipy is not installed")
            return False

        client_id = str(self.config.get("spotify.client_id", "") or "").strip()
        client_secret = str(self.config.get("spotify.client_secret", "") or "").strip()
        redirect_uri = str(
            self.config.get("spotify.redirect_uri", "http://localhost:8888/callback") or ""
        ).strip()
        base_dir = Path(self.config.get("paths.base_dir", "."))
        cache_path = base_dir / "config" / "spotify_token_cache"

        if not client_id or not client_secret:
            print("[Spotify] ⚠️ Spotify client credentials not configured")
            return False

        try:
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=self.SCOPES,
                cache_path=str(cache_path),
                open_browser=True,
            )
            self.client = spotipy.Spotify(auth_manager=auth_manager)
            print("[Spotify] ✅ Service initialized")
            return True
        except Exception as e:
            print(f"[Spotify] ❌ Authentication failed: {e}")
            self.client = None
            return False

    def _ensure_client(self) -> bool:
        if self.client:
            return True
        return self._authenticate()

    def _active_device_id(self) -> Optional[str]:
        if not self.client:
            return None
        try:
            playback = self.client.current_playback()
            if playback and playback.get("device"):
                return playback["device"].get("id")
            devices = self.client.devices().get("devices", [])
            return devices[0].get("id") if devices else None
        except Exception as e:
            print(f"[Spotify] ⚠️ Could not get active device: {e}")
            return None

    def _format_track(self, track: Dict[str, Any]) -> str:
        artists = ", ".join(artist.get("name", "") for artist in track.get("artists", []))
        return f"{track.get('name', 'Unknown')} by {artists}".strip()

    def _search_uri(self, query: str, search_type: str = "track") -> Optional[str]:
        if not self.client:
            return None
        try:
            results = self.client.search(q=query, type=search_type, limit=1)
            items = results.get(f"{search_type}s", {}).get("items", [])
            if not items:
                return None
            return items[0].get("uri")
        except Exception as e:
            print(f"[Spotify] ❌ Search URI error: {e}")
            return None

    def play(self, query: str = "") -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            device_id = self._active_device_id()
            if query:
                uri = self._search_uri(query, "track")
                if not uri:
                    return f"I couldn't find '{query}' on Spotify, sir."
                self.client.start_playback(device_id=device_id, uris=[uri])
                print(f"[Spotify] ✅ Playing: {query}")
                return f"Playing {query} on Spotify, sir."
            self.client.start_playback(device_id=device_id)
            print("[Spotify] ✅ Playback started")
            return "Spotify playback started, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Play error: {e}")
            return f"Could not start Spotify playback, sir: {e}"

    def pause(self) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            self.client.pause_playback()
            print("[Spotify] ✅ Playback paused")
            return "Spotify paused, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Pause error: {e}")
            return f"Could not pause Spotify, sir: {e}"

    def resume(self) -> str:
        return self.play()

    def skip_next(self) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            self.client.next_track()
            print("[Spotify] ✅ Skipped to next")
            return "Skipped to the next track, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Next error: {e}")
            return f"Could not skip track, sir: {e}"

    def skip_previous(self) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            self.client.previous_track()
            print("[Spotify] ✅ Skipped to previous")
            return "Returned to the previous track, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Previous error: {e}")
            return f"Could not go to previous track, sir: {e}"

    def current(self) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            current = self.client.current_user_playing_track()
            if not current or not current.get("item"):
                return "Nothing is currently playing on Spotify, sir."
            track = self._format_track(current["item"])
            state = "playing" if current.get("is_playing") else "paused"
            return f"Currently {state}: {track}, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Current error: {e}")
            return f"Could not get the current Spotify track, sir: {e}"

    def set_volume(self, value: int) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            volume = max(0, min(100, int(value)))
            self.client.volume(volume)
            print(f"[Spotify] ✅ Volume set: {volume}")
            return f"Spotify volume set to {volume} percent, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Volume error: {e}")
            return f"Could not set Spotify volume, sir: {e}"

    def search(self, query: str, search_type: str = "track") -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            normalized_type = search_type if search_type in {"track", "album", "playlist", "artist"} else "track"
            results = self.client.search(q=query, type=normalized_type, limit=5)
            items = results.get(f"{normalized_type}s", {}).get("items", [])
            if not items:
                return f"No Spotify results found for '{query}', sir."
            lines = [f"Spotify {normalized_type} results for '{query}', sir:"]
            for item in items:
                if normalized_type == "track":
                    lines.append(f"- {self._format_track(item)}")
                else:
                    lines.append(f"- {item.get('name', 'Unknown')}")
            return "\n".join(lines)
        except Exception as e:
            print(f"[Spotify] ❌ Search error: {e}")
            return f"Could not search Spotify, sir: {e}"

    def queue(self, query: str) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            uri = self._search_uri(query, "track")
            if not uri:
                return f"I couldn't find '{query}' on Spotify, sir."
            self.client.add_to_queue(uri)
            print(f"[Spotify] ✅ Queued: {query}")
            return f"Added {query} to the Spotify queue, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Queue error: {e}")
            return f"Could not add song to the queue, sir: {e}"

    def playlists(self) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            results = self.client.current_user_playlists(limit=20)
            items = results.get("items", [])
            if not items:
                return "No Spotify playlists found, sir."
            return "Your Spotify playlists, sir:\n" + "\n".join(
                f"- {item.get('name', 'Unknown')}" for item in items
            )
        except Exception as e:
            print(f"[Spotify] ❌ Playlists error: {e}")
            return f"Could not list Spotify playlists, sir: {e}"

    def shuffle(self, state: str) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            enabled = str(state).lower() == "on"
            self.client.shuffle(enabled)
            print(f"[Spotify] ✅ Shuffle: {state}")
            return f"Spotify shuffle turned {'on' if enabled else 'off'}, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Shuffle error: {e}")
            return f"Could not update shuffle, sir: {e}"

    def repeat(self, state: str) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            repeat_state = state if state in {"off", "track", "context"} else "off"
            self.client.repeat(repeat_state)
            print(f"[Spotify] ✅ Repeat: {repeat_state}")
            return f"Spotify repeat set to {repeat_state}, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Repeat error: {e}")
            return f"Could not update repeat, sir: {e}"

    def devices(self) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            devices = self.client.devices().get("devices", [])
            if not devices:
                return "No Spotify devices found, sir."
            lines = ["Available Spotify devices, sir:"]
            for device in devices:
                active = "active" if device.get("is_active") else "inactive"
                lines.append(f"- {device.get('name', 'Unknown')} ({active})")
            return "\n".join(lines)
        except Exception as e:
            print(f"[Spotify] ❌ Devices error: {e}")
            return f"Could not list Spotify devices, sir: {e}"

    def transfer(self, device_name: str) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            devices = self.client.devices().get("devices", [])
            for device in devices:
                if device_name.lower() in device.get("name", "").lower():
                    self.client.transfer_playback(device.get("id"), force_play=False)
                    print(f"[Spotify] ✅ Transferred to: {device.get('name')}")
                    return f"Transferred Spotify playback to {device.get('name')}, sir."
            return f"I couldn't find a Spotify device named {device_name}, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Transfer error: {e}")
            return f"Could not transfer Spotify playback, sir: {e}"

    def liked(self) -> str:
        if not self._ensure_client():
            return "Spotify is not available or configured, sir."
        try:
            results = self.client.current_user_saved_tracks(limit=20)
            uris = [item["track"]["uri"] for item in results.get("items", []) if item.get("track")]
            if not uris:
                return "No liked Spotify songs found, sir."
            self.client.start_playback(uris=uris)
            print("[Spotify] ✅ Playing liked songs")
            return "Playing your liked songs on Spotify, sir."
        except Exception as e:
            print(f"[Spotify] ❌ Liked error: {e}")
            return f"Could not play liked songs, sir: {e}"


_spotify_controller: Optional[SpotifyController] = None


def get_spotify_controller() -> SpotifyController:
    """Get the global Spotify controller instance."""
    global _spotify_controller
    if _spotify_controller is None:
        _spotify_controller = SpotifyController()
    return _spotify_controller


def spotify_controller(
    parameters: dict,
    response=None,
    player=None,
    speak: Callable[[str], None] = None,
    session_memory=None,
) -> str:
    """Spotify controller tool called by Gemini."""
    action = parameters.get("action", "current")
    controller = get_spotify_controller()

    try:
        if action == "play":
            result = controller.play(parameters.get("query", ""))
        elif action == "pause":
            result = controller.pause()
        elif action == "resume":
            result = controller.resume()
        elif action == "next":
            result = controller.skip_next()
        elif action == "previous":
            result = controller.skip_previous()
        elif action == "current":
            result = controller.current()
        elif action == "volume":
            result = controller.set_volume(int(parameters.get("value", 50)))
        elif action == "search":
            query = parameters.get("query", "")
            if not query:
                return "Please provide a Spotify search query, sir."
            result = controller.search(query, parameters.get("type", "track"))
        elif action == "queue":
            query = parameters.get("query", "")
            if not query:
                return "Please provide a song to queue, sir."
            result = controller.queue(query)
        elif action == "playlists":
            result = controller.playlists()
        elif action == "shuffle":
            result = controller.shuffle(parameters.get("state", "off"))
        elif action == "repeat":
            result = controller.repeat(parameters.get("state", "off"))
        elif action == "devices":
            result = controller.devices()
        elif action == "transfer":
            device_name = parameters.get("device_name", "")
            if not device_name:
                return "Please provide a Spotify device name, sir."
            result = controller.transfer(device_name)
        elif action == "liked":
            result = controller.liked()
        else:
            result = f"Unknown Spotify action: {action}"

        if speak and action in {"current", "devices", "playlists"}:
            speak(result)
        if player:
            try:
                player.write_log(f"JARVIS: {result}")
            except Exception:
                pass
        return result or "Done."
    except Exception as e:
        print(f"[Spotify] ❌ Tool error: {e}")
        return f"Spotify error, sir: {e}"
