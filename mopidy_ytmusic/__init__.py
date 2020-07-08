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
        schema["auth_json"] = config.String()
        return schema

    def get_command(self):
        from .command import YTMusicCommand

        return YTMusicCommand()

    def setup(self, registry):
        from .backend import YTMusicBackend
        registry.add("backend", YTMusicBackend)
