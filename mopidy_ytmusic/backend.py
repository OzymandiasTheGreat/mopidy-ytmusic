import pykka
import requests
import json
import re
import random
import time
import hashlib

from urllib.parse import urlparse, parse_qs
from mopidy import backend, httpclient
from mopidy.models import Ref, Track, Artist, Album, SearchResult, Playlist
from mopidy_ytmusic import logger
from youtube_dl import YoutubeDL
from ytmusicapi.ytmusic import YTMusic
from ytmusicapi.parsers.utils import nav, get_continuations, CAROUSEL_TITLE, TITLE, TITLE_TEXT, NAVIGATION_BROWSE_ID, SINGLE_COLUMN_TAB, SECTION_LIST

from .repeating_timer import RepeatingTimer
from .scrobble_fe import YTMusicScrobbleListener

# Youtube-DL instance
YDL = None
# YoutubeIE instance
YIE = None
# Youtube js player info
YTP = {'url':None,'expire':0}
# YTMusicAPI instance
API = None
# API authentication boolean
AUTH = False
# Tracks dict
TRACKS = {}
# Albums dict
ALBUMS = {'PLAYLISTS':Album(uri="ytmusic:album:PLAYLISTS",name="Playlists",artists=None,date=time.strftime('%Y'),musicbrainz_id="",num_tracks=None,num_discs=None)}
# Artists dict
ARTISTS = {}
# Auto Playlist browser info
YTBROWSE = { 'expire': 0, 'sections': [] }


def get_track(bId):
    streams = API.get_streaming_data(bId)
    # Try to find the highest quality stream.  We want "AUDIO_QUALITY_HIGH", barring
    # that we find the highest bitrate audio/mp4 stream, after that we sort through the
    # garbage.
    playstr = None
    url = None
    if 'adaptiveFormats' in streams:
        bitrate = 0
        crap = {}
        worse = {}
        for stream in streams['adaptiveFormats']:
            if 'audioQuality' in stream and stream['audioQuality'] == 'AUDIO_QUALITY_HIGH':
                playstr = stream
                break
            if stream['mimeType'].startswith('audio/mp4') and stream['averageBitrate'] > bitrate:
                bitrate = stream['averageBitrate']
                playstr = stream
            elif stream['mimeType'].startswith('audio'):
                crap[stream['averageBitrate']] = stream
            else:
                worse[stream['averageBitrate']] = stream
        if playstr is None:
            # sigh.
            if len(crap):
                playstr=crap[sorted(list(crap.keys()))[-1]]
                if 'audioQuality' not in playstr:
                    playstr['audioQuality'] = 'AUDIO_QUALITY_GARBAGE'
            elif len(worse):
                playstr=worse[sorted(list(worse.keys()))[-1]]
                if 'audioQuality' not in playstr:
                    playstr['audioQuality'] = 'AUDIO_QUALITY_FECES'
    elif 'formats' in streams:
        # Great, we're really left with the dregs of quality.
        playstr = streams['formats'][0]
        if 'audioQuality' not in playstr:
            playstr['audioQuality'] = 'AUDIO_QUALITY_404'
        if 'url' in playstr:
            logger.info('Found %s stream with %d ABR for %s',playstr['audioQuality'],playstr['averageBitrate'],bId)
            url = playstr['url']
        else:
            logger.error('No url for %s.',bId)
    else:
        logger.error('No streams found for %s. Falling back to youtube-dl.',bId)
    if playstr is not None:
        # Use Youtube-DL's Info Extractor to decode the signature.
        if 'signatureCipher' in playstr:
            sc = parse_qs(playstr['signatureCipher'])
            sig = YIE._decrypt_signature(sc['s'][0],bId,YTP['url'])
            url = sc['url'][0] + '&sig=' + sig + '&ratebypass=yes'
        elif 'url' in playstr:
            url = playstr['url']
        else:
            logger.error("Unable to get URL from stream for %s",bId)
            return(None)
        logger.info('Found %s stream with %d ABR for %s',playstr['audioQuality'],playstr['averageBitrate'],bId)
    if url is not None:
        # Return the decoded youtube url to mopidy for playback.
        return(url)
    return None

def scrobble(bId):
    # Let YTMusic know we're playing this track so it will be added to our history.
    endpoint = "https://www.youtube.com/get_video_info"
    params = {"video_id": bId, "hl": API.language, "el": "detailpage", "c": "WEB_REMIX", "cver": "0.1"}
    response = requests.get(endpoint,params,headers=API.headers,proxies=API.proxies)
    text = parse_qs(response.text)
    player_response = json.loads(text['player_response'][0])
    trackurl = re.sub(r'plid=','list=',player_response['playbackTracking']['videostatsPlaybackUrl']['baseUrl'])
    CPN_ALPHABET = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
    params = {
        'cpn': ''.join((CPN_ALPHABET[random.randint(0, 256) & 63] for _ in range(0, 16))),
        'referrer': "https://music.youtube.com",
        'cbr': text['cbr'][0],
        'cbrver': text['cbrver'][0],
        'c': text['c'][0],
        'cver': text['cver'][0],
        'cos': text['cos'][0],
        'cosver': text['cosver'][0],
        'cr': text['cr'][0],
#       'afmt': playstr['itag'],
        'ver': 2,
    }
    tr = requests.get(trackurl,params=params,headers=API.headers,proxies=API.proxies)
    logger.debug("%d code from '%s'",tr.status_code,tr.url)

def parse_uri(uri):
    components = uri.split(':')
    bId = components[2]
    upload = (len(components) > 3 and components[3] == 'upload') or False
    return bId, upload

def playlistToTracks(pls):
    ret = []
    if "tracks" in pls:
        for track in pls["tracks"]:
            duration = (track['duration'] if 'duration' in track else track['length']).split(":")
            artists = []
            if 'artists' in track:
                for a in track['artists']:
                    if a['id'] not in ARTISTS:
                        ARTISTS[a['id']] = Artist(
                            uri=f"ytmusic:artist:{a['id']}",
                            name=a["name"],
                            sortname=a["name"],
                            musicbrainz_id="",
                        )
                    artists.append(ARTISTS[a['id']])
            elif 'byline' in track:
                artists = [Artist(
                    name=track["byline"],
                    sortname=track["byline"],
                    musicbrainz_id="",
                )]
            else:
                artists = None

            if 'album' in track and track['album'] is not None:
                if track['album']['id'] not in ALBUMS:
                    ALBUMS[track['album']['id']] = Album(
                        uri=f"ytmusic:album:{track['album']['id']}",
                        name=track["album"]["name"],
                        artists=artists,
                        num_tracks=None,
                        num_discs=None,
                        date="1999",
                        musicbrainz_id="",
                    )
                album = ALBUMS[track['album']['id']]
            else:
                album = None

            if track["videoId"] not in TRACKS:
                TRACKS[track["videoId"]] = Track(
                    uri=f"ytmusic:track:{track['videoId']}",
                    name=track["title"],
                    artists=artists,
                    album=album,
                    composers=[],
                    performers=[],
                    genre="",
                    track_no=None,
                    disc_no=None,
                    date="1999",
                    length=(int(duration[0]) * 60000 + int(duration[1]) * 1000),
                    bitrate=0,
                    comment="",
                    musicbrainz_id="",
                    last_modified=None,
                )
            ret.append(TRACKS[track["videoId"]])
    return(ret)


def uploadArtistToTracks(artist):
    ret = []
    for track in artist:
        artists = []
        for a in track["artist"]:
            if a['id'] not in ARTISTS:
                ARTISTS[a['id']] = Artist(
                    uri=f"ytmusic:artist:{a['id']}:upload",
                    name=a["name"],
                    sortname=a["name"],
                    musicbrainz_id="",
                )
            artists.append(ARTISTS[a['id']])   
        if track['album']['id'] not in ALBUMS:
            ALBUMS[track['album']['id']] = Album(
                uri=f"ytmusic:album:{track['album']['id']}:upload",
                name=track["album"]["name"],
                artists=artists,
                num_tracks=None,
                num_discs=None,
                date="1999",
                musicbrainz_id="",
            )
        TRACKS[track["videoId"]] = Track(
            uri=f"ytmusic:track:{track['videoId']}",
            name=track["title"],
            artists=artists,
            album=ALBUMS[track['album']['id']],
            composers=[],
            performers=[],
            genre="",
            track_no=None,
            disc_no=None,
            date="1999",
            length=None,
            bitrate=0,
            comment="",
            musicbrainz_id="",
            last_modified=None,
        )
        ret.append(TRACKS[track["videoId"]])
    return(ret)


def artistToTracks(artist):
    if "songs" in artist and "browseId" in artist["songs"] and artist["songs"]["browseId"] is not None:
        res = API.get_playlist(artist["songs"]["browseId"])
        tracks = playlistToTracks(res)
        logger.info('YTMusic found %d tracks for %s',len(tracks),artist['name'])
        return tracks
    return None


def uploadAlbumToTracks(album, bId):
    ret = []
    if album['artist']['id'] not in ARTISTS:
        ARTISTS[album['artist']['id']] = Artist(
            uri=f"ytmusic:artist:{album['artist']['id']}:upload",
            name=album["artist"]["name"],
            sortname=album["artist"]["name"],
            musicbrainz_id="",
        )
    artists = [ ARTISTS[album['artist']['id']] ]
    if bId not in ALBUMS:
        ALBUMS[bId] = Album(
            uri=f"ytmusic:album:{bId}:upload",
            name=album["title"],
            artists=artists,
            num_tracks=int(album["trackCount"]) if str(album["trackCount"]).isnumeric() else None,
            num_discs=None,
            date=f"{album['year']}",
            musicbrainz_id="",
        )
    if "tracks" in album:
        for track in album["tracks"]:
            if track["videoId"] not in TRACKS:
                TRACKS[track["videoId"]] = Track(
                    uri=f"ytmusic:track:{track['videoId']}",
                    name=track["title"],
                    artists=artists,
                    album=ALBUMS[bId],
                    composers=[],
                    performers=[],
                    genre="",
                    track_no=None,
                    disc_no=None,
                    date=f"{album['year']}",
                    length=None,
                    bitrate=0,
                    comment="",
                    musicbrainz_id="",
                    last_modified=None,
                )
            ret.append(TRACKS[track["videoId"]])
    return(ret)


def albumToTracks(album, bId):
    ret = []
    date = f"{album['releaseDate']['year']}"
    artists = []
    for artist in album['artist']:
        if artist['id'] not in ARTISTS:
            ARTISTS[artist['id']] = Artist(
                uri=f"ytmusic:artist:{artist['id']}",
                name=artist["name"],
                sortname=artist["name"],
                musicbrainz_id="",
            ) 
        artists.append(ARTISTS[artist['id']])
    if bId not in ALBUMS:
        ALBUMS[bId] = Album(
            uri=f"ytmusic:album:{bId}",
            name=album["title"],
            artists=artists,
            num_tracks=int(album["trackCount"]) if str(album["trackCount"]).isnumeric() else None,
            num_discs=None,
            date=date,
            musicbrainz_id="",
        )
    for song in album["tracks"]:
        if song['videoId'] not in TRACKS:
            TRACKS[song["videoId"]] = Track(
                uri=f"ytmusic:track:{song['videoId']}",
                name=song["title"],
                artists=artists,
                album=ALBUMS[bId],
                composers=[],
                performers=[],
                genre="",
                track_no=int(song["index"]) if str(song["index"]).isnumeric() else None,
                disc_no=None,
                date=date,
                length=int(song["lengthMs"]) if str(song["lengthMs"]).isnumeric() else None,
                bitrate=0,
                comment="",
                musicbrainz_id="",
                last_modified=None,
            )
        ret.append(TRACKS[song['videoId']])
    return(ret)


def parseSearch(results, field=None, queries=[]):
    tracks = set()
    salbums = set()
    sartists = set()
    for result in results:
        if result["resultType"] == "song":
            if field == "track" and not any(q.casefold() == result["title"].casefold() for q in queries):
                continue
            if result['videoId'] in TRACKS:
                tracks.add(TRACKS[result['videoId']])
            else:
                try:
                    length = [int(i) for i in result["duration"].split(":")]
                except ValueError:
                    length = [0, 0]
                if result['videoId'] == None:
                    continue
                if result['videoId'] not in TRACKS:
                    artists = []
                    for a in result['artists']:
                        if a['id'] not in ARTISTS:
                            ARTISTS[a['id']] = Artist(
                                uri=f"ytmusic:artist:{a['id']}",
                                name=a["name"],
                                sortname=a["name"],
                                musicbrainz_id="",
                            )
                        artists.append(ARTISTS[a['id']])
                    album = None
                    if 'album' in result:
                        if result['album']['id'] not in ALBUMS:
                            ALBUMS[result['album']['id']] = Album(
                                uri=f"ytmusic:album:{result['album']['id']}",
                                name=result["album"]["name"],
                                artists=artists,
                                num_tracks=None,
                                num_discs=None,
                                date="1999",
                                musicbrainz_id="",
                            )
                            album = ALBUMS[result['album']['id']]
                    TRACKS[result['videoId']] = Track(
                        uri=f"ytmusic:track:{result['videoId']}",
                        name=result["title"],
                        artists=artists,
                        album=album,
                        composers=[],
                        performers=[],
                        genre="",
                        track_no=None,
                        disc_no=None,
                        date="1999",
                        length=(length[0] * 60 * 1000) + (length[1] * 1000),
                        bitrate=0,
                        comment="",
                        musicbrainz_id="",
                        last_modified=None,
                    )
                tracks.add(TRACKS[result['videoId']])
        elif result["resultType"] == "album":
            if field == "album" and not any(q.casefold() == result["title"].casefold() for q in queries):
                continue
            try:
                album = API.get_album(result["browseId"])
                if result["browseId"] not in ALBUMS:
                    date = result['year']
                    ALBUMS[result['browseId']] = Album(
                        uri=f"ytmusic:album:{result['browseId']}",
                        name=album["title"],
                        artists=[Artist(
                            uri="",
                            name=result["artist"],
                            sortname=result["artist"],
                            musicbrainz_id="",
                        )],
                        num_tracks=int(album["trackCount"]) if str(album["trackCount"]).isnumeric() else None,
                        num_discs=None,
                        date=date,
                        musicbrainz_id="",
                    )
                salbums.add(ALBUMS[result['browseId']])
            except Exception:
                logger.exception("YTMusic failed parsing album %s", result["title"])
        elif result["resultType"] == "artist":
            if field == "artist" and not any(q.casefold() == result["artist"].casefold() for q in queries):
                continue
            try:
                artistq = API.get_artist(result["browseId"])
                if result['browseId'] not in ARTISTS:
                    ARTISTS[result['browseId']] = Artist(
                        uri=f"ytmusic:artist:{result['browseId']}",
                        name=artistq["name"],
                        sortname=artistq["name"],
                        musicbrainz_id="",
                    )
                sartists.add(ARTISTS[result['browseId']])
                if 'albums' in artistq:
                    if 'params' in artistq['albums']:
                        albums = API.get_artist_albums(artistq["channelId"],artistq["albums"]["params"])
                        for album in albums:
                            if album['browseId'] not in ALBUMS:
                                ALBUMS[album['browseId']] = Album(
                                    uri=f"ytmusic:album:{album['browseId']}",
                                    name=album["title"],
                                    artists=[ARTISTS[result['browseId']]],
                                    date=album['year'],
                                    musicbrainz_id="",
                                )
                            salbums.add(ALBUMS[album['browseId']])
                    elif 'results' in artistq['albums']:
                        for album in artistq["albums"]["results"]:
                            if album['browseId'] not in ALBUMS:
                                ALBUMS[album['browseId']] = Album(
                                    uri=f"ytmusic:album:{album['browseId']}",
                                    name=album["title"],
                                    artists=[ARTISTS[result['browseId']]],
                                    date=album['year'],
                                    musicbrainz_id="",
                                )
                            salbums.add(ALBUMS[album['browseId']])
                if 'singles' in artistq and 'results' in artistq['singles']:
                    for single in artistq['singles']['results']:
                        if single['browseId'] not in ALBUMS:
                            ALBUMS[single['browseId']] = Album(
                                uri=f"ytmusic:album:{single['browseId']}",
                                name=single['title'],
                                artists=[ARTISTS[result['browseId']]],
                                date=single['year'],
                                musicbrainz_id="",
                            )
                        salbums.add(ALBUMS[single['browseId']])
                if 'songs' in artistq:
                    if 'results' in artistq['songs']:
                        for song in artistq['songs']['results']:
                            if song['videoId'] in TRACKS:
                                tracks.add(TRACKS[song['videoId']])
                            else:
                                album = None
                                if 'album' in song:
                                    if song['album']['id'] not in ALBUMS:
                                        ALBUMS[song['album']['id']] = Album(
                                            uri=f"ytmusic:album:{song['album']['id']}",
                                            name=song['album']['name'],
                                            artists=[ARTISTS[result['browseId']]],
                                            date='1999',
                                            musicbrainz_id="",
                                        )
                                    album = ALBUMS[song['album']['id']]
                                if song['videoId'] not in TRACKS:
                                    TRACKS[song['videoId']] = Track (
                                        uri=f"ytmusic:track:{song['videoId']}",
                                        name=song['title'],
                                        artists=[ARTISTS[result['browseId']]],
                                        album=album,
                                        composers=[],
                                        performers=[],
                                        genre="",
                                        track_no=None,
                                        disc_no=None,
                                        date="1999",
                                        length=None,
                                        bitrate=0,
                                        comment="",
                                        musicbrainz_id="",
                                        last_modified=None,
                                    )
                                tracks.add(TRACKS[song['videoId']])
            except Exception:
                logger.exception("YTMusic failed parsing artist %s", result["artist"])
    tracks = list(tracks)
    for track in tracks:
        bId, _ = parse_uri(track.uri)
        TRACKS[bId] = track
    logger.info("YTMusic search returned %d results", len(tracks) + len(sartists) + len(salbums))
    return SearchResult(
        uri="ytmusic:search",
        tracks=tracks,
        artists=list(sartists),
        albums=list(salbums),
    )

def parse_auto_playlists(res):
    browse = []
    for sect in res:
        car = []
        if 'musicImmersiveCarouselShelfRenderer' in sect:
            car = nav(sect, ['musicImmersiveCarouselShelfRenderer'])
        elif 'musicCarouselShelfRenderer' in sect:
            car = nav(sect, ['musicCarouselShelfRenderer'])
        else:
            continue
        stitle = nav(car, CAROUSEL_TITLE + ['text']).strip()
        browse.append({'name':stitle,'uri':'ytmusic:auto:'+hashlib.md5(stitle.encode('utf-8')).hexdigest(),'items':[]})
        for item in nav(car,['contents']):
            brId = nav(item,['musicTwoRowItemRenderer'] + TITLE + NAVIGATION_BROWSE_ID, True)
            if brId is None or brId == 'VLLM':
                continue
            pagetype = nav(item,['musicTwoRowItemRenderer','navigationEndpoint','browseEndpoint','browseEndpointContextSupportedConfigs','browseEndpointContextMusicConfig','pageType'],True)
            ititle = nav(item,['musicTwoRowItemRenderer'] + TITLE_TEXT).strip()
            if pagetype == 'MUSIC_PAGE_TYPE_PLAYLIST':
                browse[-1]['items'].append({'type':'playlist','uri':f"ytmusic:playlist:{brId}",'name':ititle})
            elif pagetype == 'MUSIC_PAGE_TYPE_ARTIST':
                browse[-1]['items'].append({'type':'artist','uri':f"ytmusic:artist:{brId}",'name':ititle+' (Artist)'})
            elif pagetype == 'MUSIC_PAGE_TYPE_ALBUM':
                artist = nav(item,['musicTwoRowItemRenderer','subtitle','runs',-1,'text'],True)
                ctype  = nav(item,['musicTwoRowItemRenderer','subtitle','runs',0,'text'],True)
                if artist is not None:
                    browse[-1]['items'].append({'type':'album','uri':f"ytmusic:album:{brId}",'name':artist+' - '+ititle+' ('+ctype+')'})
                else:
                    browse[-1]['items'].append({'type':'album','uri':f"ytmusic:album:{brId}",'name':ititle+' ('+ctype+')'})
    return(browse)

def get_auto_playlists():
    global YTBROWSE
    if (time.time() < YTBROWSE['expire']):
        return(0)
    try:
        logger.info('YTMusic loading auto playlists')
        response = API._send_request('browse',{})
        exp = response['maxAgeStoreSeconds']+time.time()
        tab = nav(response, SINGLE_COLUMN_TAB)
        browse = parse_auto_playlists(nav(tab, SECTION_LIST))
        if 'continuations' in tab['sectionListRenderer']:
            request_func = lambda additionalParams: API._send_request('browse',{},additionalParams)
            parse_func = lambda contents: parse_auto_playlists(contents)
            browse.extend(get_continuations(tab['sectionListRenderer'],'sectionListContinuation',100,request_func,parse_func))
        # Delete empty sections
        for i in range(len(browse)-1,0,-1):
            if len(browse[i]['items']) == 0:
                browse.pop(i)
        logger.info('YTMusic loaded %d auto playlists sections',len(browse))
        YTBROWSE = { 'expire':exp, 'sections': browse }
    except Exception:
        logger.exception('YTMusic failed to load auto playlists')
    return(0)

def get_youtube_player():
    # Refresh our js player URL so YDL can decode the signature correctly.
    global YTP
    response = requests.get('https://music.youtube.com',headers=API.headers,proxies=API.proxies)
    m = re.search(r'jsUrl"\s*:\s*"([^"]+)"',response.text)
    if m:
        YTP['url'] = m.group(1)
        YTP['expire'] = time.time() + 3600
        logger.info('YTMusic updated player URL to %s',YTP['url'])
    else:
        logger.error('YTMusic unable to extract player URL.')

class YTMusicBackend(pykka.ThreadingActor, backend.Backend, YTMusicScrobbleListener):
    def __init__(self, config, audio):
        super().__init__()
        self.config = config
        self.audio = audio
        self.uri_schemes = ["ytmusic"]

        self._auto_playlist_refresh_rate = 20 * 60
        self._auto_playlist_refresh_timer = None

        self._youtube_player_refresh_rate = 10 * 60
        self._youtube_player_refresh_timer = None

        if config["ytmusic"]["auth_json"]:
            self._ytmusicapi_auth_json = config["ytmusic"]["auth_json"]
            global AUTH
            AUTH = True

        self.playback = YTMusicPlaybackProvider(audio=audio, backend=self)
        self.library = YTMusicLibraryProvider(backend=self)
        if AUTH:
            self.playlists = YTMusicPlaylistsProvider(backend=self)

    def on_start(self):
        global YDL
        YDL = YoutubeDL({
            "format": "bestaudio/m4a/mp3/ogg/best",
            "proxy": httpclient.format_proxy(self.config["proxy"]),
            "nocheckcertificate": True,
        })
        global YIE
        YIE = YDL.get_info_extractor('Youtube')
        global API
        if AUTH:
            API = YTMusic(self._ytmusicapi_auth_json)
        else:
            API = YTMusic()
        self._auto_playlist_refresh_timer = RepeatingTimer(
            self._refresh_auto_playlists, self._auto_playlist_refresh_rate
        )
        self._auto_playlist_refresh_timer.start()
        self._youtube_player_refresh_timer = RepeatingTimer(
            self._refresh_youtube_player, self._youtube_player_refresh_rate
        )
        self._youtube_player_refresh_timer.start()
    
    def on_stop(self):
        if self._auto_playlist_refresh_timer:
            self._auto_playlist_refresh_timer.cancel()
            self._auto_playlist_refresh_timer = None
        if self._youtube_player_refresh_timer:
            self._youtube_player_refresh_timer.cancel()
            self._youtube_player_refresh_timer = None

    def _refresh_auto_playlists(self):
        t0 = time.time()
        get_auto_playlists()
        t = time.time() - t0
        logger.info("Auto Playlists refreshed in %.2f",t)

    def _refresh_youtube_player(self):
        t0 = time.time()
        get_youtube_player()
        t = time.time() - t0
        logger.info("Youtube Player URL refreshed in %.2f",t)
    
    def scrobble_track(self,bId):
        # Called through YTMusicScrobbleListener
        scrobble(bId)


class YTMusicPlaybackProvider(backend.PlaybackProvider):
    def __init__(self, audio, backend):
        super().__init__(audio, backend)
        self.last_id = None

    def translate_uri(self, uri):
        logger.info('YTMusic PlaybackProvider.translate_uri "%s"', uri)

        if "ytmusic:track:" not in uri:
            return None

        try:
            bId, _ = parse_uri(uri)
            self.last_id = bId
            return get_track(bId)
        except Exception as e:
            logger.error('translate_uri error "%s"', str(e))
            return None


class YTMusicLibraryProvider(backend.LibraryProvider):
    root_directory = Ref.directory(uri="ytmusic:root", name="YouTube Music")

    def browse(self, uri):
        logger.info("YTMusic browsing uri \"%s\"", uri)
        if uri == "ytmusic:root":
            dirs = []
            if AUTH:
                dirs += [
                    Ref.directory(uri="ytmusic:artist", name="Artists"),
                    Ref.directory(uri="ytmusic:album", name="Albums"),
                    Ref.directory(uri="ytmusic:liked", name="Liked Songs"),
                    Ref.directory(uri="ytmusic:history", name="Recently Played"),
                ]
            dirs += [
                Ref.directory(uri="ytmusic:watch", name="Similar to last played"),
                Ref.directory(uri="ytmusic:auto", name="Auto Playlists"),
            ]
            return(dirs)
        elif uri == "ytmusic:artist":
            try:
                library_artists = [
                    Ref.artist(uri=f"ytmusic:artist:{a['browseId']}", name=a["artist"])
                    for a in API.get_library_artists(limit=100)
                ]
                logger.info("YTMusic found %d artists in library", len(library_artists))
            except Exception:
                logger.exception("YTMusic failed getting artists from library")
                library_artists = []
            if AUTH:
                try:
                    upload_artists = [
                        Ref.artist(uri=f"ytmusic:artist:{a['browseId']}:upload", name=a["artist"])
                        for a in API.get_library_upload_artists(limit=100)
                    ]
                    logger.info("YTMusic found %d uploaded artists", len(upload_artists))
                except Exception:
                    logger.exception("YTMusic failed getting uploaded artists")
                    upload_artists = []
            else:
                upload_artists = []
            return library_artists  + upload_artists
        elif uri == "ytmusic:album":
            try:
                library_albums = [
                    Ref.album(uri=f"ytmusic:album:{a['browseId']}", name=a["title"])
                    for a in API.get_library_albums(limit=100)
                ]
                logger.info("YTMusic found %d albums in library", len(library_albums))
            except Exception:
                logger.exception("YTMusic failed getting albums from library")
                library_albums = []
            if AUTH:
                try:
                    upload_albums = [
                        Ref.album(uri=f"ytmusic:album:{a['browseId']}:upload", name=a["title"])
                        for a in API.get_library_upload_albums(limit=100)
                    ]
                    logger.info("YTMusic found %d uploaded albums", len(upload_albums))
                except Exception:
                    logger.exception("YTMusic failed getting uploaded albums")
                    upload_albums = []
            else:
                upload_albums = []
            return library_albums  + upload_albums
        elif uri == "ytmusic:liked":
            try:
                res = API.get_liked_songs(limit=100)
                tracks = playlistToTracks(res)
                logger.info("YTMusic found %d liked songs", len(res["tracks"]))
                return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
            except Exception:
                logger.exception("YTMusic failed getting liked songs")
        elif uri == "ytmusic:history":
            try:
                res = API.get_history()
                tracks = playlistToTracks({'tracks': res})
                logger.info("YTMusic found %d songs from recent history",len(res))
                return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
            except Exception:
                logger.exception("YTMusic failed getting listening history")
        elif uri == "ytmusic:watch":
            try:
                playback = self.backend.playback
                if playback.last_id is not None:
                    track_id = playback.last_id
                elif AUTH:
                    hist = API.get_history()
                    track_id = hist[0]['videoId']
                if track_id:
                    res = API.get_watch_playlist(track_id, limit=100)
                    if 'tracks' in res:
                        logger.info("YTMusic found %d watch songs for \"%s\"", len(res["tracks"]), track_id)
                        res['tracks'].pop(0)
                        tracks = playlistToTracks(res)
                        return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
            except Exception:
                logger.exception("YTMusic failed getting watch songs")
        elif uri == "ytmusic:auto":
            try:
                get_auto_playlists()
                return [
                    Ref.directory(uri=a['uri'], name=a['name'])
                    for a in YTBROWSE['sections']
                ]
            except Exception:
                logger.exception('YTMusic failed getting auto playlists')
        elif uri.startswith("ytmusic:auto:"):
            try:
                for a in YTBROWSE['sections']:
                    if a['uri'] == uri:
                        ret = []
                        for i in a['items']:
                            if i['type'] == 'playlist':
                                ret.append(Ref.playlist(uri=i['uri'],name=i['name']))
                                logger.info("playlist: %s - %s",i['name'],i['uri'])
                            elif i['type'] == 'artist':
                                ret.append(Ref.artist(uri=i['uri'],name=i['name']))
                                logger.info("artist: %s - %s",i['name'],i['uri'])
                            elif i['type'] == 'album':
                                ret.append(Ref.album(uri=i['uri'],name=i['name']))
                                logger.info("album: %s - %s",i['name'],i['uri'])
                        return(ret)
            except Exception:
                logger.exception('YTMusic failed getting auto playlist "%s"',uri)
        elif uri.startswith("ytmusic:artist:"):
            bId, upload = parse_uri(uri)
            if upload:
                try:
                    res = API.get_library_upload_artist(bId)
                    tracks = uploadArtistToTracks(res)
                    logger.info("YTMusic found %d songs for uploaded artist \"%s\"", len(res), res[0]["artist"]["name"])
                    return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
                except Exception:
                    logger.exception("YTMusic failed getting tracks for uploaded artist \"%s\"", bId)
            else:
                try:
                    res = API.get_artist(bId)
                    tracks = artistToTracks(res)
                    logger.info("YTMusic found %d songs for artist \"%s\" in library", len(res["songs"]), res["name"])
                    return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
                except Exception:
                    logger.exception("YTMusic failed getting tracks for artist \"%s\"", bId)
        elif uri.startswith("ytmusic:album:"):
            bId, upload = parse_uri(uri)
            if upload:
                try:
                    res = API.get_library_upload_album(bId)
                    tracks = uploadAlbumToTracks(res, bId)
                    logger.info("YTMusic found %d songs for uploaded album \"%s\"", len(res["tracks"]), res["title"])
                    return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
                except Exception:
                    logger.exception("YTMusic failed getting tracks for uploaded album \"%s\"", bId)
            else:
                try:
                    res = API.get_album(bId)
                    tracks = albumToTracks(res, bId)
                    logger.info("YTMusic found %d songs for album \"%s\" in library", len(res["tracks"]), res["title"])
                    return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
                except Exception:
                    logger.exception("YTMusic failed getting tracks for album \"%s\"", bId)
        elif uri.startswith("ytmusic:playlist:"):
            bId, upload = parse_uri(uri)
            try:
                res = API.get_playlist(bId)
                tracks = playlistToTracks(res)
                return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
            except Exception:
                logger.exception("YTMusic failed to get tracks from playlist '%s'",bId)
        return []

    def lookup(self, uri):
        bId, _ = parse_uri(uri)
        if (uri.startswith("ytmusic:album:")):
            try:
                res = API.get_album(bId)
                tracks = albumToTracks(res, bId)
                return(tracks)
            except Exception:
                logger.exception("YTMusic failed getting tracks for album \"%s\"", bId)
        elif (uri.startswith("ytmusic:artist:")):
            try:
                res = API.get_artist(bId)
                tracks = artistToTracks(res)
                return(tracks)
            except Exception:
                logger.exception("YTMusic failed getting tracks for artist \"%s\"", bId)
        elif (uri.startswith("ytmusic:playlist:")):
            try:
                res = API.get_playlist(bId)
                tracks = playlistToTracks(res)
                return(tracks)
            except Exception:
                logger.exception("YTMusic failed getting tracks for playlist \"%s\"", bId)
        elif (bId) in TRACKS:
            return [TRACKS[bId]]
        return []

    def get_distinct(self, field, query=None):
        ret = set()
        if field == "artist" or field == "albumartist":
            # try:
            #     uploads = API.get_library_upload_artists(limit=100)
            # except Exception:
            #     logger.exception("YTMusic failed getting uploaded artists")
            #     uploads = []
            #     pass
            try:
                library = API.get_library_artists(limit=100)
            except Exception:
                logger.exception("YTMusic failed getting artists from library")
                library = []
                pass
            # for a in uploads:
            #     ret.add(a["artist"])
            for a in library:
                ret.add(a["artist"])
        # elif field == "album":
        #     try:
        #         uploads = API.get_library_upload_albums(limit=100)
        #     except Exception:
        #         logger.exception("YTMusic failed getting uploaded albums")
        #         uploads = []
        #         pass
        #     try:
        #         library = API.get_library_albums(limit=100)
        #     except Exception:
        #         logger.exception("YTMusic failed getting albums from library")
        #         library = []
        #         pass
        #     for a in uploads:
        #         ret.add(a["title"])
        #     for a in library:
        #         ret.add(a["title"])
        return ret

    def search(self, query=None, uris=None, exact=False):
        results = []
        logger.info("YTMusic searching for %s", query)
        if "any" in query:
            try:
                res = API.search(" ".join(query["any"]), filter=None)
                results = parseSearch(res)
            except Exception:
                logger.exception("YTMusic search failed for query \"any\"=\"%s\"", " ".join(query["any"]))
        elif "track_name" in query:
            try:
                res = API.search(" ".join(query["track_name"]), filter="songs")
                if exact:
                    results = parseSearch(res, "track", query["track_name"])
                else:
                    results = parseSearch(res)
            except Exception:
                logger.exception("YTMusic search failed for query \"title\"=\"%s\"", " ".join(query["track_name"]))
        elif "albumartist" in query or "artist" in query:
            q1 = ("albumartist" in query and query["albumartist"]) or []
            q2 = ("artist" in query and query["artist"]) or []
            try:
                res = API.search(" ".join(q1 + q2), filter="artists")
                if exact:
                    results = parseSearch(res, "artist", q1 + q2)
                else:
                    results = parseSearch(res)
            except Exception:
                logger.exception("YTMusic search failed for query \"artist\"=\"%s\"", " ".join(q1 + q2))
        elif "album" in query:
            try:
                res = API.search(" ".join(query["album"]), filter="albums")
                if exact:
                    results = parseSearch(res, "album", query["album"])
                else:
                    results = parseSearch(res)
            except Exception:
                logger.exception("YTMusic search failed for query \"album\"=\"%s\"", " ".join(query["album"]))
        else:
            logger.info("YTMusic skipping search, unsupported field types \"%s\"", " ".join(query.keys()))
            return None
        return results


class YTMusicPlaylistsProvider(backend.PlaylistsProvider):
    def as_list(self):
        logger.info("YTMusic getting user playlists")
        refs = []
        try:
            playlists = API.get_library_playlists(limit=100)
        except Exception:
            logger.exception("YTMusic failed getting a list of playlists")
            playlists = []
        for pls in playlists:
            refs.append(Ref.playlist(
                uri=f"ytmusic:playlist:{pls['playlistId']}", name=pls["title"],
            ))
        return refs

    def lookup(self, uri):
        bId, _ = parse_uri(uri)
        logger.info("YTMusic looking up playlist \"%s\"", bId)
        try:
            pls = API.get_playlist(bId, limit=100)
        except Exception:
            logger.exception("YTMusic playlist lookup failed")
            pls = None
        if pls:
            tracks = playlistToTracks(pls)
            return Playlist(
                uri=f"ytmusic:playlist:{pls['id']}",
                name=pls["title"],
                tracks=tracks,
                last_modified=None,
            )

    def get_items(self, uri):
        bId, _ = parse_uri(uri)
        logger.info("YTMusic getting playlist items for \"%s\"", bId)
        try:
            pls = API.get_playlist(bId, limit=100)
        except Exception:
            logger.exception("YTMusic failed getting playlist items")
            pls = None
        if pls:
            tracks = playlistToTracks(pls)
            return [ Ref.track(uri=t.uri, name=t.name) for t in tracks ]
        return None

    def create(self, name):
        logger.info("YTMusic creating playlist \"%s\"", name)
        try:
            bId = API.create_playlist(name, "")
        except Exception:
            logger.exception("YTMusic playlist creation failed")
            bId = None
        if bId:
            uri = f"ytmusic:playlist:{bId}"
            logger.info("YTMusic created playlist \"%s\"", uri)
            return Playlist(
                uri=uri,
                name=name,
                tracks=[],
                last_modified=None,
            )
        return None

    def delete(self, uri):
        logger.info("YTMusic deleting playlist \"%s\"", uri)
        bId, _ = parse_uri(uri)
        try:
            API.delete_playlist(bId)
            return True
        except Exception:
            logger.exception("YTMusic failed to delete playlist")
            return False

    def refresh(self):
        pass

    def save(self, playlist):
        bId, _ = parse_uri(playlist.uri)
        logger.info("YTMusic saving playlist \"%s\" \"%s\"", playlist.name, bId)
        try:
            pls = API.get_playlist(bId, limit=100)
        except Exception:
            logger.exception("YTMusic saving playlist failed")
            return None
        oldIds = set([t["videoId"] for t in pls["tracks"]])
        newIds = set([parse_uri(p.uri)[0] for p in playlist.tracks])
        common = oldIds & newIds
        remove = oldIds ^ common
        add = newIds ^ common
        if len(remove):
            logger.debug("YTMusic removing items \"%s\" from playlist", remove)
            try:
                videos = [t for t in pls["tracks"] if t["videoId"] in remove]
                API.remove_playlist_items(bId, videos)
            except Exception:
                logger.exception("YTMusic failed removing items from playlist")
        if len(add):
            logger.debug("YTMusic adding items \"%s\" to playlist", add)
            try:
                API.add_playlist_items(bId, list(add))
            except Exception:
                logger.exception("YTMusic failed adding items to playlist")
        if pls["title"] != playlist.name:
            logger.debug("Renaming playlist to \"%s\"", playlist.name)
            try:
                API.edit_playlist(bId, title=playlist.name)
            except Exception:
                logger.exception("YTMusic failed renaming playlist")
        return playlist