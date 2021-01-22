import logging
import pathlib

import pkg_resources

from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-YTMusic").version

logger = logging.getLogger(__name__)


class Extension(ext.Extension):

    dist_name = "Mopidy-YTMusic"
    ext_name = "ytmusic"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["auth_json"] = config.String(optional=True)
        schema["auto_playlist_refresh"] = config.Integer(
            minimum=0, optional=True
        )
        schema["youtube_player_refresh"] = config.Integer(
            minimum=1, optional=True
        )
        schema["playlist_item_limit"] = config.Integer(minimum=1, optional=True)
        schema["subscribed_artist_limit"] = config.Integer(
            minimum=0, optional=True
        )
        schema["enable_history"] = config.Boolean(optional=True)
        schema["enable_liked_songs"] = config.Boolean(optional=True)
        schema["enable_mood_genre"] = config.Boolean(optional=True)
        schema["enable_scrobbling"] = config.Boolean(optional=True)
        schema["stream_preference"] = config.List(optional=True)
        schema["verify_track_url"] = config.Boolean(optional=True)
        return schema

    def get_command(self):
        from .command import YTMusicCommand

        return YTMusicCommand()

    def setup(self, registry):
        from .backend import YTMusicBackend
        from .scrobble_fe import YTMusicScrobbleFE

        registry.add("backend", YTMusicBackend)
        registry.add("frontend", YTMusicScrobbleFE)
