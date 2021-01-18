# Stolen almost directly from mopidy-gmusic
import pykka

from mopidy import core, listener
from mopidy_ytmusic import logger


class YTMusicScrobbleFE(pykka.ThreadingActor, core.CoreListener):
    def __init__(self, config, core):
        super().__init__()
        self.config = config
        self.scrobbling = config["ytmusic"]["enable_scrobbling"]

    def track_playback_ended(self, tl_track, time_position):
        if self.scrobbling:
            track = tl_track.track

            duration = track.length and track.length // 1000 or 0
            time_position = time_position // 1000

            if time_position < duration // 2 and time_position < 120:
                logger.debug(
                    "Track not played long enough too scrobble. (50% or 120s)"
                )
                return

            bId = track.uri.split(":")[2]
            logger.debug("Scrobbling: %s", bId)
            listener.send(
                YTMusicScrobbleListener,
                "scrobble_track",
                bId=bId,
            )


class YTMusicScrobbleListener(listener.Listener):
    def scrobble_track(self, bId):
        pass
