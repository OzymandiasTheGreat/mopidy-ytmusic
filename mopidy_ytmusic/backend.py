from urllib.parse import urlparse, parse_qs
import pykka
from mopidy import backend, httpclient
from mopidy.models import Ref, Track, Artist, Album, SearchResult, Playlist
from mopidy_ytmusic import logger


YDL = None
API = None
TRACKS = {}


def get_video(id_):
    uri = f"https://music.youtube.com/watch?v={id_}"
    vid = YDL.extract_info(
        url=uri,
        download=False,
        ie_key=None,
        extra_info={},
        process=True,
        force_generic_extractor=False,
    )
    for fmt in vid["formats"]:
        if fmt["ext"] == "m4a":
            logger.debug("YTMusic Stream URI %s", fmt["url"])
            return fmt["url"]
    return None


def parse_uri(uri):
    query = parse_qs(urlparse(uri).query)
    id_ = query["id"][0]
    upload = ("upload" in query and query["upload"] and query["upload"][0] == "true") or False
    return id_, upload


def playlistToTracks(pls):
    if ("tracks" in pls):
        for track in pls["tracks"]:
            artists = [Artist(
                uri=f"ytm:artist?id={a['id']}",
                name=a["name"],
                sortname=a["name"],
                musicbrainz_id="",
            ) for a in track["artists"]]
            TRACKS[track["videoId"]] = Track(
                uri=f"ytm:video?id={track['videoId']}",
                name=track["title"],
                artists=artists,
                album=track["album"] and Album(
                    uri=f"ytm:album?id={track['album']['id']}",
                    name=track["album"]["name"],
                    artists=artists,
                    num_tracks=None,
                    num_discs=None,
                    date="1999",
                    musicbrainz_id="",
                ),
                composers=[],
                performers=[],
                genre="",
                track_no=None,
                disc_no=None,
                date="1999",
                length=None,
                bitrate=0,
                comment="0",
                musicbrainz_id="",
                last_modified=None,
            )


def uploadArtistToTracks(artist):
    for track in artist:
        TRACKS[track["videoId"]] = Track(
            uri=f"ytm:video?id={track['videoId']}",
            name=track["title"],
            artists=[Artist(
                uri=f"ytm:artist?id={a['id']}&upload=true",
                name=a["name"],
                sortname=a["name"],
                musicbrainz_id="",
            ) for a in track["artist"]],
            album=Album(
                uri=f"ytm:album?id={track['album']['id']}&upload=true",
                name=track["album"]["name"],
                artists=[Artist(
                    uri=f"ytm:artist?id={a['id']}&upload=true",
                    name=a["name"],
                    sortname=a["name"],
                    musicbrainz_id="",
                ) for a in track["artist"]],
                num_tracks=None,
                num_discs=None,
                date="1999",
                musicbrainz_id="",
            ),
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


def artistToTracks(artist):
    tracks = ("songs" in artist and "results" in artist["songs"] and artist["songs"]["results"]) or []
    for track in tracks:
        TRACKS[track["videoId"]] = Track(
            uri=f"ytm:video?id={track['videoId']}",
            name=track["title"],
            artists=[Artist(
                uri=f"ytm:artist?id={a['id']}&upload=false",
                name=a["name"],
                sortname=a["name"],
                musicbrainz_id="",
            ) for a in track["artists"]],
            album=Album(
                uri=f"ytm:album?id={track['album']['id']}",
                name=track["album"]["name"],
                artists=[Artist(
                    uri=f"ytm:artist?id={a['id']}&upload=false",
                    name=a["name"],
                    sortname=a["name"],
                    musicbrainz_id="",
                ) for a in track["artists"]],
                num_tracks=None,
                num_discs=None,
                date="1999",
                musicbrainz_id="",
            ),
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


def uploadAlbumToTracks(album, id_):
    artists = [Artist(
        uri=f"ytm:artist?id={album['artist']['id']}&upload=true",
        name=album["artist"]["name"],
        sortname=album["artist"]["name"],
        musicbrainz_id="",
    )]
    albumRef = Album(
        uri=f"ytm:album?id={id_}&upload=true",
        name=album["title"],
        artists=artists,
        num_tracks=int(album["trackCount"]) if str(album["trackCount"]).isnumeric() else None,
        num_discs=None,
        date=album["year"],
        musicbrainz_id="",
    )
    if "tracks" in album:
        for track in album["tracks"]:
            TRACKS[track["videoId"]] = Track(
                uri=f"ytm:video?id={track['videoId']}",
                name=track["title"],
                artists=artists,
                album=albumRef,
                composers=[],
                performers=[],
                genre="",
                track_no=None,
                disc_no=None,
                date=album["year"],
                length=None,
                bitrate=0,
                comment="",
                musicbrainz_id="",
                last_modified=None,
            )


def albumToTracks(album, id_):
    date = f"{album['releaseDate']['year']}-{album['releaseDate']['month']}-{album['releaseDate']['day']}"
    artists = [Artist(
        uri=f"ytm:artist?id={artist['id']}&upload=false",
        name=artist["name"],
        sortname=artist["name"],
        musicbrainz_id="",
    ) for artist in album["artist"]]
    albumObj = Album(
        uri=f"ytm:album?id={id_}&upload=false",
        name=album["title"],
        artists=artists,
        num_tracks=int(album["trackCount"]) if str(album["trackCount"]).isnumeric() else None,
        num_discs=None,
        date=date,
        musicbrainz_id="",
    )
    for song in album["tracks"]:
        track = Track(
            uri=f"ytm:video?id={song['videoId']}",
            name=song["title"],
            artists=artists,
            album=albumObj,
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
        TRACKS[song["videoId"]] = track


def parseSearch(results, field=None, queries=[]):
    tracks = set()
    for result in results:
        if result["resultType"] == "song":
            if field == "track" and not any(q.casefold() == result["title"].casefold() for q in queries):
                continue
            try:
                length = [int(i) for i in result["duration"].split(":")]
            except ValueError:
                length = [0, 0]
            track = Track(
                uri=f"ytm:video?id={result['videoId']}",
                name=result["title"],
                artists=[Artist(
                    uri=f"ytm:artist?id={a['id']}&upload=false",
                    name=a["name"],
                    sortname=a["name"],
                    musicbrainz_id="",
                ) for a in result["artists"]],
                album=Album(
                    uri=f"ytm:album?id={result['album']['id']}&upload=false",
                    name=result["album"]["name"],
                    artists=[Artist(
                        uri=f"ytm:artist?id={a['id']}&upload=false",
                        name=a["name"],
                        sortname=a["name"],
                        musicbrainz_id="",
                    ) for a in result["artists"]],
                    num_tracks=None,
                    num_discs=None,
                    date="1999",
                    musicbrainz_id="",
                ) if "album" in result else None,
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
            tracks.add(track)
        elif result["resultType"] == "album":
            if field == "album" and not any(q.casefold() == result["title"].casefold() for q in queries):
                continue
            try:
                album = API.get_album(result["browseId"])
                artists = [Artist(
                    uri="",
                    name=result["artist"],
                    sortname=result["artist"],
                    musicbrainz_id="",
                )]
                albumObj = Album(
                    uri=f"ytm:album?id={result['browseId']}&upload=false",
                    name=album["title"],
                    artists=artists,
                    num_tracks=int(album["trackCount"]) if str(album["trackCount"]).isnumeric() else None,
                    num_discs=None,
                    date=f"{album['releaseDate']['year']}-{album['releaseDate']['month']}-{album['releaseDate']['day']}",
                    musicbrainz_id="",
                )
                if "tracks" in album:
                    for song in album["tracks"]:
                        track = Track(
                            uri=f"ytm:video?id={song['videoId']}",
                            name=song["title"],
                            artists=artists,
                            album=albumObj,
                            composers=[],
                            performers=[],
                            genre="",
                            track_no=int(song["index"]) if str(song["index"]).isnumeric() else None,
                            disc_no=None,
                            date=albumObj.date,
                            length=int(song["lengthMs"]) if str(song["lengthMs"]).isnumeric() else None,
                            bitrate=0,
                            comment="",
                            musicbrainz_id="",
                            last_modified=None,
                        )
                        tracks.add(track)
            except Exception:
                logger.exception("YTMusic failed parsing album %s", result["title"])
        elif result["resultType"] == "artist":
            if field == "artist" and not any(q.casefold() == result["artist"].casefold() for q in queries):
                continue
            try:
                artist = API.get_artist(result["browseId"])
                artists = [Artist(
                    uri=f"ytm:artist?id={result['browseId']}&upload=false",
                    name=artist["name"],
                    sortname=artist["name"],
                    musicbrainz_id="",
                )]
                albums = API.get_artist_albums(result["browseId"], artist["albums"]["params"])
                for album in albums:
                    if field == "album" and not any(q.casefold() == album["title"].casefold() for q in queries):
                        continue
                    songs = API.get_album(album["browseId"])
                    albumObj = Album(
                        uri=f"ytm:album?id={album['browseId']}&upload=false",
                        name=album["title"],
                        artists=artists,
                        num_tracks=int(songs["trackCount"]) if str(songs["trackCount"]).isnumeric() else None,
                        num_discs=None,
                        date=f"{songs['releaseDate']['year']}-{songs['releaseDate']['month']}-{songs['releaseDate']['day']}",
                        musicbrainz_id="",
                    )
                    if "tracks" in songs:
                        for song in songs["tracks"]:
                            track = Track(
                                uri=f"ytm:video?id={song['videoId']}",
                                name=song["title"],
                                artists=artists,
                                album=albumObj,
                                composers=[],
                                performers=[],
                                genre="",
                                track_no=int(song["index"]) if str(song["index"]).isnumeric() else None,
                                disc_no=None,
                                date=albumObj.date,
                                length=int(song["lengthMs"]) if str(song["lengthMs"]).isnumeric() else None,
                                bitrate=0,
                                comment="",
                                musicbrainz_id="",
                                last_modified=None,
                            )
                            tracks.add(track)
            except Exception:
                logger.exception("YTMusic failed parsing artist %s", result["artist"])
    tracks = list(tracks)
    for track in tracks:
        id_, upload = parse_uri(track.uri)
        TRACKS[id_] = track
    return tracks


class YTMusicBackend(pykka.ThreadingActor, backend.Backend):
    def __init__(self, config, audio):
        super().__init__()
        self.config = config
        self.audio = audio
        self.uri_schemes = ["ytm"]

        from youtube_dl import YoutubeDL
        from ytmusicapi.ytmusic import YTMusic

        global YDL
        YDL = YoutubeDL({
            "format": "bestaudio/m4a/mp3/ogg/best",
            "proxy": httpclient.format_proxy(self.config["proxy"]),
            "nocheckcertificate": True,
            "cachedir": False,
        })
        global API
        API = YTMusic(config["ytmusic"]["auth_json"])

        self.playback = YouTubePlaybackProvider(audio=audio, backend=self)
        self.library = YouTubeLibraryProvider(backend=self)
        self.playlists = YouTubePlaylistsProvider(backend=self)


class YouTubePlaybackProvider(backend.PlaybackProvider):
    def translate_uri(self, uri):
        logger.info('YTMusic PlaybackProvider.translate_uri "%s"', uri)

        if "ytm:video?" not in uri:
            return None

        try:
            id_ = parse_qs(urlparse(uri).query)["id"][0]
            return get_video(id_)
        except Exception as e:
            logger.error('translate_uri error "%s"', e)
            return None


class YouTubeLibraryProvider(backend.LibraryProvider):
    root_directory = Ref.directory(uri="ytm:root", name="YouTube Music")

    def browse(self, uri):
        logger.info("YTMusic browsing uri \"%s\"", uri)
        if uri == "ytm:root":
            return [
                Ref.directory(uri="ytm:artist", name="Artists"),
                Ref.directory(uri="ytm:album", name="Albums"),
                Ref.directory(uri="ytm:liked", name="Liked Songs"),
            ]
        elif uri == "ytm:artist":
            try:
                library_artists = [
                    Ref.artist(uri=f"ytm:artist?id={a['browseId']}&upload=false", name=a["artist"])
                    for a in API.get_library_artists(limit=100)
                ]
                logger.info("YTMusic found %d artists in library", len(library_artists))
            except Exception:
                logger.exception("YTMusic failed getting artists from library")
                library_artists = []
            # try:
            #     upload_artists = [
            #         Ref.artist(uri=f"ytm:artist?id={a['browseId']}&upload=true", name=a["artist"])
            #         for a in API.get_library_upload_artists(limit=100)
            #     ]
            #     logger.info("YTMusic found %d uploaded artists", len(upload_artists))
            # except Exception:
            #     logger.exception("YTMusic failed getting uploaded artists")
            #     upload_artists = []
            return library_artists  # + upload_artists
        elif uri == "ytm:album":
            try:
                library_albums = [
                    Ref.album(uri=f"ytm:album?id={a['browseId']}&upload=false", name=a["title"])
                    for a in API.get_library_albums(limit=100)
                ]
                logger.info("YTMusic found %d albums in library", len(library_albums))
            except Exception:
                logger.exception("YTMusic failed getting albums from library")
                library_albums = []
            # try:
            #     upload_albums = [
            #         Ref.album(uri=f"ytm:album?id={a['browseId']}&upload=true", name=a["title"])
            #         for a in API.get_library_upload_albums(limit=100)
            #     ]
            #     logger.info("YTMusic found %d uploaded albums", len(upload_albums))
            # except Exception:
            #     logger.exception("YTMusic failed getting uploaded albums")
            #     upload_albums = []
            return library_albums  # + upload_albums
        elif uri == "ytm:liked":
            try:
                res = API.get_liked_songs(limit=100)
                playlistToTracks(res)
                return [
                    Ref.track(uri=f"ytm:video?id={t['videoId']}", name=t["title"])
                    for t in ("tracks" in res and res["tracks"]) or []
                ]
                logger.info("YTMusic found %d liked songs", len(res["tracks"]))
            except Exception:
                logger.exception("YTMusic failed getting liked songs")
        elif uri.startswith("ytm:artist?"):
            id_, upload = parse_uri(uri)
            # if upload:
            #     try:
            #         res = API.get_library_upload_artist(id_)
            #         uploadArtistToTracks(res)
            #         return [
            #             Ref.track(uri=f"ytm:album?id={t['videoId']}", name=t["title"])
            #             for t in res
            #         ]
            #         logger.info("YTMusic found %d songs for uploaded artist \"%s\"", len(res), res[0]["artist"]["name"])
            #     except Exception:
            #         logger.exception("YTMusic failed getting tracks for uploaded artist \"%s\"", id_)
            # else:
            try:
                res = API.get_artist(id_)
                artistToTracks(res)
                return [
                    Ref.track(uri=f"ytm:video?id={t['videoId']}", name=t["title"])
                    for t in ("songs" in res and "results" in res["songs"] and res["songs"]["results"]) or []
                ]
                logger.info("YTMusic found %d songs for artist \"%s\" in library", len(res["songs"]), res["name"])
            except Exception:
                logger.exception("YTMusic failed getting tracks for artist \"%s\"", id_)
        elif uri.startswith("ytm:album?"):
            id_, upload = parse_uri(uri)
            # if upload:
            #     try:
            #         res = API.get_library_upload_album(id_)
            #         uploadAlbumToTracks(res, id_)
            #         return [
            #             Ref.track(uri=f"ytm:video?id={t['videoId']}", name=t["title"])
            #             for t in ("tracks" in res and res["tracks"]) or []
            #         ]
            #         logger.info("YTMusic found %d songs for uploaded album \"%s\"", len(res["tracks"]), res["title"])
            #     except Exception:
            #         logger.exception("YTMusic failed getting tracks for uploaded album \"%s\"", id_)
            # else:
            try:
                res = API.get_album(id_)
                albumToTracks(res, id_)
                return [
                    Ref.track(uri=f"ytm:video?id={t['videoId']}", name=t["title"])
                    for t in ("tracks" in res and res["tracks"]) or []
                ]
                logger.info("YTMusic found %d songs for album \"%s\" in library", len(res["tracks"]), res["title"])
            except Exception:
                logger.exception("YTMusic failed getting tracks for album \"%s\"", id_)
        return []

    def lookup(self, uri):
        id_, upload = parse_uri(uri)
        if (id_) in TRACKS:
            return [TRACKS[id_]]
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
        logger.info("YTMusic searching for %s", query)
        tracks = []
        if "any" in query:
            try:
                res = API.search(" ".join(query["any"]), filter=None)
                tracks.extend(parseSearch(res))
                if (exact):
                    for track in tracks:
                        for q in query["any"]:
                            q = q.casefold()
                            if q != track.name.casefold():
                                tracks.remove(track)
                            if q == track.album.name.casefold():
                                tracks.remove(track)
                            for artist in track.artists:
                                if q == artist.name.casefold():
                                    tracks.remove(track)
            except Exception:
                logger.exception("YTMusic search failed for query \"%s\"", " ".join(query["any"]))
        elif "track_name" in query:
            try:
                res = API.search(" ".join(query["track_name"]), filter="songs")
                if exact:
                    tracks.extend(parseSearch(res, "track", query["track_name"]))
                else:
                    tracks.extend(parseSearch(res))
            except Exception:
                logger.exception("YTMusic search failed for query \"title\"=\"%s\"", " ".join(query["track_name"]))
        elif "albumartist" in query or "artist" in query:
            q1 = ("albumartist" in query and query["albumartist"]) or []
            q2 = ("artist" in query and query["artist"]) or []
            try:
                res = API.search(" ".join(q1 + q2), filter="artists")
                if exact:
                    tracks.extend(parseSearch(res, "artist", q1 + q2))
                else:
                    tracks.extend(parseSearch(res))
            except Exception:
                logger.exception("YTMusic search failed for query \"artist\"=\"%s\"", " ".join(q1 + q2))
        elif "album" in query:
            try:
                res = API.search(" ".join(query["album"]), filter="albums")
                if exact:
                    tracks.extend(parseSearch(res, "album", query["album"]))
                else:
                    tracks.extend(parseSearch(res))
            except Exception:
                logger.exception("YTMusic search failed for query \"album\"=\"%s\"", " ".join(query["album"]))
        else:
            logger.info("YTMusic skipping search, unsupported field types \"%s\"", " ".join(query.keys()))
            return None
        logger.info("YTMusic search returned %d results", len(tracks))
        return SearchResult(
            uri="",
            tracks=tracks,
            artists=None,
            albums=None,
        )


class YouTubePlaylistsProvider(backend.PlaylistsProvider):
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
                uri=f"ytm:playlist?id={pls['playlistId']}", name=pls["title"],
            ))
        return refs

    def lookup(self, uri):
        id_, upload = parse_uri(uri)
        logger.info("YTMusic looking up playlist \"%s\"", id_)
        try:
            pls = API.get_playlist(id_, limit=100)
        except Exception:
            logger.exception("YTMusic playlist lookup failed")
            pls = None
        if pls:
            tracks = []
            if "tracks" in pls:
                for track in pls["tracks"]:
                    duration = track["duration"].split(":")
                    artists = [Artist(
                        uri=f"ytm:artist?id={a['id']}&upload=false",
                        name=a["name"],
                        sortname=a["name"],
                        musicbrainz_id="",
                    ) for a in track["artists"]]
                    if track["album"]:
                        album = Album(
                            uri=f"ytm:album?id={track['album']['id']}&upload=false",
                            name=track["album"]["name"],
                            artists=artists,
                            num_tracks=None,
                            num_discs=None,
                            date="1999",
                            musicbrainz_id="",
                        )
                    else:
                        album = None
                    tracks.append(Track(
                        uri=f"ytm:video?id={track['videoId']}",
                        name=track["title"],
                        artists=artists,
                        album=album,
                        composers=[],
                        performers=[],
                        genre="",
                        track_no=None,
                        disc_no=None,
                        date="1999",
                        length=(int(duration[0]) * 60 * 1000) + (int(duration[1]) * 1000),
                        bitrate=0,
                        comment="",
                        musicbrainz_id="",
                        last_modified=None,
                    ))
            for track in tracks:
                tid, tupload = parse_uri(track.uri)
                TRACKS[tid] = track
            return Playlist(
                uri=f"ytm:playlist?id={pls['id']}",
                name=pls["title"],
                tracks=tracks,
                last_modified=None,
            )

    def get_items(self, uri):
        id_, upload = parse_uri(uri)
        logger.info("YTMusic getting playlist items for \"%s\"", id_)
        try:
            pls = API.get_playlist(id_, limit=100)
        except Exception:
            logger.exception("YTMusic failed getting playlist items")
            pls = None
        if pls:
            refs = []
            if "tracks" in pls:
                for track in pls["tracks"]:
                    refs.append(Ref.track(uri=f"ytm:video?id={track['videoId']}", name=track["title"]))
                    duration = track["duration"].split(":")
                    artists = [Artist(
                        uri=f"ytm:artist?id={a['id']}&upload=false",
                        name=a["name"],
                        sortname=a["name"],
                        musicbrainz_id="",
                    ) for a in track["artists"]]
                    if track["album"]:
                        album = Album(
                            uri=f"ytm:album?id={track['album']['id']}&upload=false",
                            name=track["album"]["name"],
                            artists=artists,
                            num_tracks=None,
                            num_discs=None,
                            date="1999",
                            musicbrainz_id="",
                        )
                    else:
                        album = None
                    TRACKS[track["videoId"]] = Track(
                        uri=f"ytm:video?id={track['videoId']}",
                        name=track["title"],
                        artists=artists,
                        album=album,
                        composers=[],
                        performers=[],
                        genre="",
                        track_no=None,
                        disc_no=None,
                        date="1999",
                        length=(int(duration[0]) * 60 * 1000) + (int(duration[1]) * 1000),
                        bitrate=0,
                        comment="",
                        musicbrainz_id="",
                        last_modified=None,
                    )
            return refs
        return None

    def create(self, name):
        logger.info("YTMusic creating playlist \"%s\"", name)
        try:
            id_ = API.create_playlist(name, "")
        except Exception:
            logger.exception("YTMusic playlist creation failed")
            id_ = None
        if id_:
            uri = f"ytm:playlist?id={id_}"
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
        id_, upload = parse_uri(uri)
        try:
            API.delete_playlist(id_)
            return True
        except Exception:
            logger.exception("YTMusic failed to delete playlist")
            return False

    def refresh(self):
        pass

    def save(self, playlist):
        id_, upload = parse_uri(playlist.uri)
        logger.info("YTMusic saving playlist \"%s\" \"%s\"", playlist.name, id_)
        try:
            pls = API.get_playlist(id_, limit=100)
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
                API.remove_playlist_items(id_, videos)
            except Exception:
                logger.exception("YTMusic failed removing items from playlist")
        if len(add):
            logger.debug("YTMusic adding items \"%s\" to playlist", add)
            try:
                API.add_playlist_items(id_, list(add))
            except Exception:
                logger.exception("YTMusic failed adding items to playlist")
        if pls["title"] != playlist.name:
            logger.debug("Renaming playlist to \"%s\"", playlist.name)
            try:
                API.edit_playlist(id_, title=playlist.name)
            except Exception:
                logger.exception("YTMusic failed renaming playlist")
        return playlist
