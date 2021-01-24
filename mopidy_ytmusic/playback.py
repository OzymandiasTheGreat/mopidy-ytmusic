import requests
import re
from urllib.parse import parse_qs
from mopidy import backend, httpclient
from mopidy_ytmusic import logger
from youtube_dl import YoutubeDL


class YTMusicPlaybackProvider(backend.PlaybackProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_id = None
        self.Youtube_Player_URL = None
        self.YoutubeDL = YoutubeDL(
            {
                "proxy": httpclient.format_proxy(self.backend.config["proxy"]),
                "nocheckcertificate": True,
            }
        )
        self.YoutubeIE = self.YoutubeDL.get_info_extractor("Youtube")

    def translate_uri(self, uri):
        logger.debug('YTMusic PlaybackProvider.translate_uri "%s"', uri)

        if "ytmusic:track:" not in uri:
            return None

        try:
            bId = uri.split(":")[2]
            self.last_id = bId
            return self._get_track(bId)
        except Exception as e:
            logger.error('translate_uri error "%s"', str(e))
            return None

    def _get_track(self, bId):
        streams = self.backend.api.get_streaming_data(bId)
        playstr = None
        url = None
        if self.backend.stream_preference:
            # Try to find stream by our preference order.
            tags = {}
            if "adaptiveFormats" in streams:
                for stream in streams["adaptiveFormats"]:
                    tags[str(stream["itag"])] = stream
            elif "dashManifestUrl" in streams:
                # Grab the dashmanifest XML and parse out the streams from it
                dash = requests.get(streams["dashManifestUrl"])
                formats = re.findall(
                    r'<Representation id="(\d+)" .*? bandwidth="(\d+)".*?BaseURL>(.*?)</BaseURL',
                    dash.text,
                )
                for stream in formats:
                    tags[stream[0]] = {
                        "url": stream[2],
                        "audioQuality": "ITAG_" + stream[0],
                        "bitrate": int(stream[1]),
                    }
            for i, p in enumerate(self.backend.stream_preference, start=1):
                if str(p) in tags:
                    playstr = tags[str(p)]
                    logger.debug("Found #%d preference stream %s", i, str(p))
                    break
        if playstr is None:
            # Couldn't find our preference, let's try something else:
            if "adaptiveFormats" in streams:
                # Try to find the highest quality stream.  We want "AUDIO_QUALITY_HIGH", barring
                # that we find the highest bitrate audio/mp4 stream, after that we sort through the
                # garbage.
                bitrate = 0
                crap = {}
                worse = {}
                for stream in streams["adaptiveFormats"]:
                    if (
                        "audioQuality" in stream
                        and stream["audioQuality"] == "AUDIO_QUALITY_HIGH"
                    ):
                        playstr = stream
                        break
                    if (
                        stream["mimeType"].startswith("audio/mp4")
                        and stream["bitrate"] > bitrate
                    ):
                        bitrate = stream["bitrate"]
                        playstr = stream
                    elif stream["mimeType"].startswith("audio"):
                        crap[stream["bitrate"]] = stream
                    else:
                        worse[stream["bitrate"]] = stream
                if playstr is None:
                    # sigh.
                    if len(crap):
                        playstr = crap[sorted(list(crap.keys()))[-1]]
                        if "audioQuality" not in playstr:
                            playstr["audioQuality"] = "AUDIO_QUALITY_GARBAGE"
                    elif len(worse):
                        playstr = worse[sorted(list(worse.keys()))[-1]]
                        if "audioQuality" not in playstr:
                            playstr["audioQuality"] = "AUDIO_QUALITY_FECES"
            elif "formats" in streams:
                # Great, we're really left with the dregs of quality.
                playstr = streams["formats"][0]
                if "audioQuality" not in playstr:
                    playstr["audioQuality"] = "AUDIO_QUALITY_404"
            else:
                logger.error(
                    "No streams found for %s. Falling back to youtube-dl.", bId
                )
        if playstr is not None:
            # Use Youtube-DL's Info Extractor to decode the signature.
            if "signatureCipher" in playstr:
                sc = parse_qs(playstr["signatureCipher"])
                sig = self.YoutubeIE._decrypt_signature(
                    sc["s"][0],
                    bId,
                    self.Youtube_Player_URL,
                )
                url = sc["url"][0] + "&sig=" + sig + "&ratebypass=yes"
            elif "url" in playstr:
                url = playstr["url"]
            else:
                logger.error("Unable to get URL from stream for %s", bId)
                return None
            logger.info(
                "YTMusic Found %s stream with %d bitrate for %s",
                playstr["audioQuality"],
                playstr["bitrate"],
                bId,
            )
        if url is not None:
            if (
                self.backend.verify_track_url
                and requests.head(url).status_code == 403
            ):
                # It's forbidden. Likely because the player url changed and we
                # decoded the signature incorrectly.
                # Refresh the player, log an error, and send back none.
                logger.error(
                    "YTMusic found forbidden URL. Updating player URL now."
                )
                self.backend._youtube_player_refresh_timer.now()
            else:
                # Return the decoded youtube url to mopidy for playback.
                logger.debug("YTMusic found %s", url)
                return url
        return None
