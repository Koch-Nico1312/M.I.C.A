from actions.spotify_controller import SpotifyController


class FakeSpotifyClient:
    def __init__(self):
        self.calls = []
        self.search_calls = 0
        self.current_playback_calls = 0
        self.devices_calls = 0
        self.saved_tracks_calls = 0

        self.track = {
            "uri": "spotify:track:track123",
            "name": "Solar Wind",
            "artists": [{"name": "Aurora"}],
            "album": {"name": "Skyline"},
            "duration_ms": 180000,
        }
        self.album = {
            "uri": "spotify:album:album123",
            "name": "Night Drive",
            "artists": [{"name": "Aurora"}],
        }
        self.playlist = {
            "uri": "spotify:playlist:playlist123",
            "name": "Focus Mix",
            "owner": {"display_name": "M.I.C.A"},
        }
        self.artist = {
            "uri": "spotify:artist:artist123",
            "name": "Aurora",
        }

    def search(self, q, type, limit):
        self.search_calls += 1
        self.calls.append(("search", q, type, limit))
        payload = {
            "tracks": {"items": [self.track]},
            "albums": {"items": [self.album]},
            "playlists": {"items": [self.playlist]},
            "artists": {"items": [self.artist]},
        }
        return {type + "s": payload[type + "s"]}

    def start_playback(self, **kwargs):
        self.calls.append(("start_playback", kwargs))

    def pause_playback(self):
        self.calls.append(("pause_playback", {}))

    def next_track(self):
        self.calls.append(("next_track", {}))

    def previous_track(self):
        self.calls.append(("previous_track", {}))

    def current_playback(self):
        self.current_playback_calls += 1
        self.calls.append(("current_playback", {}))
        return {
            "is_playing": True,
            "progress_ms": 60000,
            "device": {"name": "Living Room"},
            "item": self.track,
        }

    def current_user_playing_track(self):
        self.calls.append(("current_user_playing_track", {}))
        return {
            "is_playing": True,
            "item": self.track,
        }

    def volume(self, value):
        self.calls.append(("volume", {"value": value}))

    def devices(self):
        self.devices_calls += 1
        self.calls.append(("devices", {}))
        return {
            "devices": [
                {"id": "1", "name": "Living Room", "type": "Speaker", "is_active": True},
                {"id": "2", "name": "Laptop", "type": "Computer", "is_active": False},
            ]
        }

    def add_to_queue(self, uri):
        self.calls.append(("add_to_queue", {"uri": uri}))

    def current_user_playlists(self, limit=20):
        self.calls.append(("current_user_playlists", {"limit": limit}))
        return {"items": [self.playlist]}

    def current_user_saved_tracks(self, limit=50):
        self.saved_tracks_calls += 1
        self.calls.append(("current_user_saved_tracks", {"limit": limit}))
        return {
            "items": [
                {"track": self.track},
                {"track": {**self.track, "uri": "spotify:track:track456", "name": "Blue Hour"}},
            ]
        }

    def shuffle(self, state):
        self.calls.append(("shuffle", {"state": state}))

    def repeat(self, state):
        self.calls.append(("repeat", {"state": state}))

    def transfer_playback(self, device_id, force_play=True):
        self.calls.append(("transfer_playback", {"device_id": device_id, "force_play": force_play}))


def test_play_accepts_direct_spotify_uri():
    client = FakeSpotifyClient()
    controller = SpotifyController(sp_client=client)

    result = controller.play("spotify:track:track123")

    assert "requested Spotify track" in result
    assert ("start_playback", {"uris": ["spotify:track:track123"]}) in client.calls


def test_search_results_are_cached():
    client = FakeSpotifyClient()
    controller = SpotifyController(sp_client=client)

    first = controller.search("Aurora", "track")
    second = controller.search("Aurora", "track")

    assert "Found 1 tracks" in first
    assert first == second
    assert client.search_calls == 1


def test_liked_plays_saved_tracks():
    client = FakeSpotifyClient()
    controller = SpotifyController(sp_client=client)

    result = controller.liked()

    assert "Playing your liked songs" in result
    assert (
        "start_playback",
        {"uris": ["spotify:track:track123", "spotify:track:track456"]},
    ) in client.calls


def test_devices_use_short_lived_cache():
    client = FakeSpotifyClient()
    controller = SpotifyController(sp_client=client)

    first = controller.devices()
    second = controller.devices()

    assert "Found 2 devices" in first
    assert first == second
    assert client.devices_calls == 1
