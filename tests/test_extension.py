import unittest
from unittest import mock

from mopidy_ytmusic import Extension
from mopidy_ytmusic import backend as backend_lib
from mopidy_ytmusic import scrobble_fe


class ExtensionTest(unittest.TestCase):
    @staticmethod
    def get_config():
        config = {}
        config["enabled"] = True
        config["auth_json"] = ""
        config["auto_playlist_refresh"] = 60
        config["youtube_player_refresh"] = 15
        config["playlist_item_limit"] = 1
        config["subscribed_artist_limit"] = 1
        config["enable_history"] = False
        config["enable_liked_songs"] = False
        config["enable_mood_genre"] = True
        config["enable_scrobbling"] = False
        config["stream_preference"] = ["141", "251", "140", "250", "249"]
        config["verify_track_url"] = True
        return {"ytmusic": config, "proxy": {}}

    def test_get_default_config(self):
        ext = Extension()
        config = ext.get_default_config()

        assert "[ytmusic]" in config
        assert "enabled = true" in config
        assert "auth_json =" in config
        assert "auto_playlist_refresh = 60" in config
        assert "youtube_player_refresh = 15" in config
        assert "playlist_item_limit = 100" in config
        assert "subscribed_artist_limit = 100" in config
        assert "enable_history = yes" in config
        assert "enable_liked_songs = yes" in config
        assert "enable_mood_genre = yes" in config
        assert "enable_scrobbling = yes" in config
        assert "stream_preference = 141, 251, 140, 250, 249" in config
        assert "verify_track_url = yes" in config

    def test_get_config_schema(self):
        ext = Extension()
        schema = ext.get_config_schema()

        assert "enabled" in schema
        assert "auth_json" in schema
        assert "auto_playlist_refresh" in schema
        assert "youtube_player_refresh" in schema
        assert "playlist_item_limit" in schema
        assert "subscribed_artist_limit" in schema
        assert "enable_history" in schema
        assert "enable_liked_songs" in schema
        assert "enable_mood_genre" in schema
        assert "enable_scrobbling" in schema
        assert "stream_preference" in schema
        assert "verify_track_url" in schema

    def test_get_backend_classes(self):
        registry = mock.Mock()
        ext = Extension()
        ext.setup(registry)

        assert (
            mock.call("backend", backend_lib.YTMusicBackend)
            in registry.add.mock_calls
        )

        assert (
            mock.call("frontend", scrobble_fe.YTMusicScrobbleFE)
            in registry.add.mock_calls
        )

    def test_init_backend(self):
        backend = backend_lib.YTMusicBackend(ExtensionTest.get_config(), None)
        assert backend is not None
        backend.on_start()
        backend.on_stop()
