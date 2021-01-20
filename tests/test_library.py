import unittest

from mopidy_ytmusic import backend as backend_lib

from tests.test_extension import ExtensionTest


class LibraryTest(unittest.TestCase):
    def setUp(self):
        cfg = ExtensionTest.get_config()
        self.backend = backend_lib.YTMusicBackend(config=cfg, audio=None)

    def test_browse_none(self):
        refs = self.backend.library.browse(None)
        assert refs == []

    def test_browse_root(self):
        refs = self.backend.library.browse("ytmusic:root")
        found = False
        for ref in refs:
            if ref.uri == "ytmusic:watch":
                found = True
                break
        assert found, "ref 'ytmusic:watch' not found"
        found = False
        for ref in refs:
            if ref.uri == "ytmusic:mood":
                found = True
                break
        assert found, "ref 'ytmusic:mood' not found"
        found = False
        for ref in refs:
            if ref.uri == "ytmusic:auto":
                found = True
                break
        assert found, "ref 'ytmusic:auto' not found"

    def test_browse_moods(self):
        refs = self.backend.library.browse("ytmusic:mood")
        assert refs is not None
