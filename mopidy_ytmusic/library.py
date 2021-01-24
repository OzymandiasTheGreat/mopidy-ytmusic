from mopidy import backend
from mopidy.models import Ref, Track, Album, Artist, SearchResult, Image
from mopidy_ytmusic import logger
from ytmusicapi.parsers.utils import (
    nav,
    TITLE_TEXT,
    NAVIGATION_BROWSE_ID,
    SINGLE_COLUMN_TAB,
    SECTION_LIST,
)


class YTMusicLibraryProvider(backend.LibraryProvider):
    root_directory = Ref.directory(uri="ytmusic:root", name="YouTube Music")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ytbrowse = []
        self.TRACKS = {}
        self.ALBUMS = {}
        self.ARTISTS = {}
        self.IMAGES = {}

    def browse(self, uri):
        if not uri:
            return []
        logger.debug('YTMusic browsing uri "%s"', uri)
        if uri == "ytmusic:root":
            dirs = []
            if self.backend.auth:
                dirs += [
                    Ref.directory(uri="ytmusic:artist", name="Artists"),
                    Ref.directory(uri="ytmusic:album", name="Albums"),
                ]
                if self.backend.liked_songs:
                    dirs.append(
                        Ref.directory(uri="ytmusic:liked", name="Liked Songs")
                    )
                if self.backend.history:
                    dirs.append(
                        Ref.directory(
                            uri="ytmusic:history", name="Recently Played"
                        )
                    )
                if self.backend.subscribed_artist_limit:
                    dirs.append(
                        Ref.directory(
                            uri="ytmusic:subscriptions", name="Subscriptions"
                        )
                    )
            dirs.append(
                Ref.directory(
                    uri="ytmusic:watch", name="Similar to last played"
                )
            )
            if self.backend.mood_genre:
                dirs.append(
                    Ref.directory(
                        uri="ytmusic:mood", name="Mood and Genre Playlists"
                    )
                )
            if self.backend._auto_playlist_refresh_rate:
                dirs.append(
                    Ref.directory(uri="ytmusic:auto", name="Auto Playlists")
                )
            return dirs
        elif (
            uri == "ytmusic:subscriptions"
            and self.backend.subscribed_artist_limit
        ):
            try:
                subs = self.backend.api.get_library_subscriptions(
                    limit=self.backend.subscribed_artist_limit
                )
                logger.debug(
                    "YTMusic found %d artists in subscriptions", len(subs)
                )
                return [
                    Ref.artist(
                        uri=f"ytmusic:artist:{a['browseId']}", name=a["artist"]
                    )
                    for a in subs
                ]
            except Exception:
                logger.exception(
                    "YTMusic failed getting artists from subscriptions"
                )
        elif uri == "ytmusic:artist":
            try:
                library_artists = [
                    Ref.artist(
                        uri=f"ytmusic:artist:{a['browseId']}", name=a["artist"]
                    )
                    for a in self.backend.api.get_library_artists(limit=100)
                ]
                logger.debug(
                    "YTMusic found %d artists in library", len(library_artists)
                )
            except Exception:
                logger.exception("YTMusic failed getting artists from library")
                library_artists = []
            if self.backend.auth:
                try:
                    upload_artists = [
                        Ref.artist(
                            uri=f"ytmusic:artist:{a['browseId']}:upload",
                            name=a["artist"],
                        )
                        for a in self.backend.api.get_library_upload_artists(
                            limit=100
                        )
                    ]
                    logger.debug(
                        "YTMusic found %d uploaded artists", len(upload_artists)
                    )
                except Exception:
                    logger.exception("YTMusic failed getting uploaded artists")
                    upload_artists = []
            else:
                upload_artists = []
            return library_artists + upload_artists
        elif uri == "ytmusic:album":
            try:
                library_albums = [
                    Ref.album(
                        uri=f"ytmusic:album:{a['browseId']}", name=a["title"]
                    )
                    for a in self.backend.api.get_library_albums(limit=100)
                ]
                logger.debug(
                    "YTMusic found %d albums in library", len(library_albums)
                )
            except Exception:
                logger.exception("YTMusic failed getting albums from library")
                library_albums = []
            if self.backend.auth:
                try:
                    upload_albums = [
                        Ref.album(
                            uri=f"ytmusic:album:{a['browseId']}:upload",
                            name=a["title"],
                        )
                        for a in self.backend.api.get_library_upload_albums()
                    ]
                    logger.debug(
                        "YTMusic found %d uploaded albums", len(upload_albums)
                    )
                except Exception:
                    logger.exception("YTMusic failed getting uploaded albums")
                    upload_albums = []
            else:
                upload_albums = []
            return library_albums + upload_albums
        elif uri == "ytmusic:liked":
            try:
                res = self.backend.api.get_liked_songs(
                    limit=self.backend.playlist_item_limit
                )
                tracks = self.playlistToTracks(res)
                logger.debug("YTMusic found %d liked songs", len(res["tracks"]))
                return [Ref.track(uri=t.uri, name=t.name) for t in tracks]
            except Exception:
                logger.exception("YTMusic failed getting liked songs")
        elif uri == "ytmusic:history":
            try:
                res = self.backend.api.get_history()
                tracks = self.playlistToTracks({"tracks": res})
                logger.debug(
                    "YTMusic found %d songs from recent history", len(res)
                )
                return [Ref.track(uri=t.uri, name=t.name) for t in tracks]
            except Exception:
                logger.exception("YTMusic failed getting listening history")
        elif uri == "ytmusic:watch":
            try:
                playback = self.backend.playback
                if playback.last_id is not None:
                    track_id = playback.last_id
                elif self.backend.auth:
                    hist = self.backend.api.get_history()
                    track_id = hist[0]["videoId"]
                if track_id:
                    res = self.backend.api.get_watch_playlist(
                        track_id, limit=self.backend.playlist_item_limit
                    )
                    if "tracks" in res:
                        logger.debug(
                            'YTMusic found %d watch songs for "%s"',
                            len(res["tracks"]),
                            track_id,
                        )
                        res["tracks"].pop(0)
                        tracks = self.playlistToTracks(res)
                        return [
                            Ref.track(uri=t.uri, name=t.name) for t in tracks
                        ]
            except Exception:
                logger.exception("YTMusic failed getting watch songs")
        elif uri == "ytmusic:mood":
            try:
                logger.debug("YTMusic loading mood/genre playlists")
                moods = {}
                response = self.backend.api._send_request(
                    "browse", {"browseId": "FEmusic_moods_and_genres"}
                )
                for sect in nav(response, SINGLE_COLUMN_TAB + SECTION_LIST):
                    for cat in nav(sect, ["gridRenderer", "items"]):
                        title = nav(
                            cat,
                            [
                                "musicNavigationButtonRenderer",
                                "buttonText",
                                "runs",
                                0,
                                "text",
                            ],
                        ).strip()
                        endpnt = nav(
                            cat,
                            [
                                "musicNavigationButtonRenderer",
                                "clickCommand",
                                "browseEndpoint",
                                "browseId",
                            ],
                        )
                        params = nav(
                            cat,
                            [
                                "musicNavigationButtonRenderer",
                                "clickCommand",
                                "browseEndpoint",
                                "params",
                            ],
                        )
                        moods[title] = {
                            "name": title,
                            "uri": "ytmusic:mood:" + params + ":" + endpnt,
                        }
                return [
                    Ref.directory(uri=moods[a]["uri"], name=moods[a]["name"])
                    for a in sorted(moods.keys())
                ]
            except Exception:
                logger.exception("YTMusic failed to load mood/genre playlists")
        elif uri.startswith("ytmusic:mood:"):
            try:
                ret = []
                _, _, params, endpnt = uri.split(":")
                response = self.backend.api._send_request(
                    "browse", {"browseId": endpnt, "params": params}
                )
                for sect in nav(response, SINGLE_COLUMN_TAB + SECTION_LIST):
                    key = []
                    if "gridRenderer" in sect:
                        key = ["gridRenderer", "items"]
                    elif "musicCarouselShelfRenderer" in sect:
                        key = ["musicCarouselShelfRenderer", "contents"]
                    elif "musicImmersiveCarouselShelfRenderer" in sect:
                        key = [
                            "musicImmersiveCarouselShelfRenderer",
                            "contents",
                        ]
                    if len(key):
                        for item in nav(sect, key):
                            title = nav(
                                item, ["musicTwoRowItemRenderer"] + TITLE_TEXT
                            ).strip()
                            #                           if 'subtitle' in item['musicTwoRowItemRenderer']:
                            #                               title += ' ('
                            #                               for st in item['musicTwoRowItemRenderer']['subtitle']['runs']:
                            #                                   title += st['text']
                            #                               title += ')'
                            brId = nav(
                                item,
                                ["musicTwoRowItemRenderer"]
                                + NAVIGATION_BROWSE_ID,
                            )
                            ret.append(
                                Ref.playlist(
                                    uri=f"ytmusic:playlist:{brId}", name=title
                                )
                            )
                return ret
            except Exception:
                logger.exception(
                    'YTMusic failed getting mood/genre playlist "%s"', uri
                )
        elif uri == "ytmusic:auto" and self.backend._auto_playlist_refresh_rate:
            try:
                return [
                    Ref.directory(uri=a["uri"], name=a["name"])
                    for a in self.ytbrowse
                ]
            except Exception:
                logger.exception("YTMusic failed getting auto playlists")
        elif (
            uri.startswith("ytmusic:auto:")
            and self.backend._auto_playlist_refresh_rate
        ):
            try:
                for a in self.ytbrowse:
                    if a["uri"] == uri:
                        ret = []
                        for i in a["items"]:
                            if i["type"] == "playlist":
                                ret.append(
                                    Ref.playlist(uri=i["uri"], name=i["name"])
                                )
                                logger.debug(
                                    "playlist: %s - %s", i["name"], i["uri"]
                                )
                            elif i["type"] == "artist":
                                ret.append(
                                    Ref.artist(uri=i["uri"], name=i["name"])
                                )
                                logger.debug(
                                    "artist: %s - %s", i["name"], i["uri"]
                                )
                            elif i["type"] == "album":
                                ret.append(
                                    Ref.album(uri=i["uri"], name=i["name"])
                                )
                                logger.debug(
                                    "album: %s - %s", i["name"], i["uri"]
                                )
                        return ret
            except Exception:
                logger.exception(
                    'YTMusic failed getting auto playlist "%s"', uri
                )
        elif uri.startswith("ytmusic:artist:"):
            bId, upload = parse_uri(uri)
            if upload:
                try:
                    res = self.backend.api.get_library_upload_artist(bId)
                    tracks = self.uploadArtistToTracks(res)
                    logger.debug(
                        'YTMusic found %d songs for uploaded artist "%s"',
                        len(res),
                        res[0]["artist"][0]["name"],
                    )
                    return [Ref.track(uri=t.uri, name=t.name) for t in tracks]
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for uploaded artist "%s"',
                        bId,
                    )
            else:
                try:
                    res = self.backend.api.get_artist(bId)
                    tracks = self.artistToTracks(res)
                    logger.debug(
                        'YTMusic found %d songs for artist "%s" in library',
                        len(res["songs"]),
                        res["name"],
                    )
                    return [Ref.track(uri=t.uri, name=t.name) for t in tracks]
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for artist "%s"', bId
                    )
        elif uri.startswith("ytmusic:album:"):
            bId, upload = parse_uri(uri)
            if upload:
                try:
                    res = self.backend.api.get_library_upload_album(bId)
                    tracks = self.uploadAlbumToTracks(res, bId)
                    logger.debug(
                        'YTMusic found %d songs for uploaded album "%s"',
                        len(res["tracks"]),
                        res["title"],
                    )
                    return [Ref.track(uri=t.uri, name=t.name) for t in tracks]
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for uploaded album "%s"',
                        bId,
                    )
            else:
                try:
                    res = self.backend.api.get_album(bId)
                    tracks = self.albumToTracks(res, bId)
                    logger.debug(
                        'YTMusic found %d songs for album "%s" in library',
                        len(res["tracks"]),
                        res["title"],
                    )
                    return [Ref.track(uri=t.uri, name=t.name) for t in tracks]
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for album "%s"', bId
                    )
        elif uri.startswith("ytmusic:playlist:"):
            bId, upload = parse_uri(uri)
            try:
                res = self.backend.api.get_playlist(
                    bId, limit=self.backend.playlist_item_limit
                )
                tracks = self.playlistToTracks(res)
                return [Ref.track(uri=t.uri, name=t.name) for t in tracks]
            except Exception:
                logger.exception(
                    "YTMusic failed to get tracks from playlist '%s'", bId
                )
        return []

    def lookup(self, uri):
        bId, upload = parse_uri(uri)
        if upload:
            if uri.startswith("ytmusic:album:"):
                try:
                    res = self.backend.api.get_library_upload_album(bId)
                    tracks = self.albumToTracks(res, bId)
                    return tracks
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for album "%s"', bId
                    )
            elif uri.startswith("ytmusic:artist:"):
                try:
                    res = self.backend.api.get_library_upload_artist(bId)
                    tracks = self.artistToTracks(res)
                    return tracks
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for artist "%s"', bId
                    )
        else:
            if uri.startswith("ytmusic:album:"):
                try:
                    res = self.backend.api.get_album(bId)
                    tracks = self.albumToTracks(res, bId)
                    return tracks
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for album "%s"', bId
                    )
            elif uri.startswith("ytmusic:artist:"):
                try:
                    res = self.backend.api.get_artist(bId)
                    tracks = self.artistToTracks(res)
                    return tracks
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for artist "%s"', bId
                    )
            elif uri.startswith("ytmusic:playlist:"):
                try:
                    res = self.backend.api.get_playlist(
                        bId, limit=self.backend.playlist_item_limit
                    )
                    tracks = self.playlistToTracks(res)
                    return tracks
                except Exception:
                    logger.exception(
                        'YTMusic failed getting tracks for playlist "%s"', bId
                    )
        if (bId) in self.TRACKS:
            return [self.TRACKS[bId]]
        return []

    def get_distinct(self, field, query=None):
        ret = set()
        if field == "artist" or field == "albumartist":
            # try:
            #     uploads = self.backend.api.get_library_upload_artists(limit=100)
            # except Exception:
            #     logger.exception("YTMusic failed getting uploaded artists")
            #     uploads = []
            #     pass
            try:
                library = self.backend.api.get_library_artists(
                    limit=self.backend.playlist_item_limit
                )
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
        #         uploads = self.backend.api.get_library_upload_albums(limit=self.backend.playlist_item_limit)
        #     except Exception:
        #         logger.exception("YTMusic failed getting uploaded albums")
        #         uploads = []
        #         pass
        #     try:
        #         library = self.backend.api.get_library_albums(limit=self.backend.playlist_item_limit)
        #     except Exception:
        #         logger.exception("YTMusic failed getting albums from library")
        #         library = []
        #         pass
        #     for a in uploads:
        #         ret.add(a["title"])
        #     for a in library:
        #         ret.add(a["title"])
        return ret

    def get_images(self, uris):
        ret = {}
        for uri in uris:
            images = []
            comp = uri.split(":")
            if len(comp) == 3:
                logger.debug("YTMusic getting images for %s", uri)
                func, bId = comp[1:3]
                if bId not in self.IMAGES:
                    try:
                        if func == "artist":
                            data = self.backend.api.get_artist(bId)
                            images = self.addThumbnails(bId, data, False)
                        elif func == "album":
                            data = self.backend.api.get_album(bId)
                            images = self.addThumbnails(bId, data)
                        elif func == "playlist":
                            data = self.backend.api.get_playlist(bId)
                            images = self.addThumbnails(bId, data, False)
                        elif func == "track":
                            if (
                                bId in self.TRACKS
                                and self.TRACKS[bId].album is not None
                                and self.TRACKS[bId].album.uri is not None
                            ):
                                album, upload = parse_uri(
                                    self.TRACKS[bId].album.uri
                                )
                                if upload:
                                    data = self.backend.api.get_library_upload_album(
                                        album
                                    )
                                else:
                                    data = self.backend.api.get_album(album)
                                images = self.addThumbnails(bId, data)
                    except Exception:
                        logger.error(
                            "YTMusic unable to get image url for %s", uri
                        )
                else:
                    images = self.IMAGES[bId]
            elif len(comp) == 4 and comp[3] == "upload":
                logger.debug("YTMusic getting images for %s", uri)
                func, bId = comp[1:3]
                if bId not in self.IMAGES:
                    try:
                        if func == "artist":
                            data = self.backend.api.get_library_upload_artist(
                                bId
                            )
                            images = self.addThumbnails(bId, data, False)
                        elif func == "album":
                            data = self.backend.api.get_library_upload_album(
                                bId
                            )
                            images = self.addThumbnails(bId, data)
                        elif func == "track":
                            if (
                                bId in self.TRACKS
                                and self.TRACKS[bId].album is not None
                                and self.TRACKS[bId].album.uri is not None
                            ):
                                album, upload = parse_uri(
                                    self.TRACKS[bId].album.uri
                                )
                                if upload:
                                    data = self.backend.api.get_library_upload_album(
                                        album
                                    )
                                else:
                                    data = self.backend.api.get_album(album)
                                images = self.addThumbnails(bId, data)
                    except Exception:
                        logger.error(
                            "YTMusic unable to get image url for uploaded %s",
                            uri,
                        )
                else:
                    images = self.IMAGES[bId]
            ret[uri] = images
            logger.debug("YTMusic found %d image urls for %s", len(images), uri)
        return ret

    def search(self, query=None, uris=None, exact=False):
        results = []
        logger.debug("YTMusic searching for %s", query)
        if "any" in query:
            try:
                res = self.backend.api.search(
                    " ".join(query["any"]), filter=None
                )
                results = self.parseSearch(res)
            except Exception:
                logger.exception(
                    'YTMusic search failed for query "any"="%s"',
                    " ".join(query["any"]),
                )
        elif "track_name" in query:
            try:
                res = self.backend.api.search(
                    " ".join(query["track_name"]), filter="songs"
                )
                if exact:
                    results = self.parseSearch(
                        res, "track", query["track_name"]
                    )
                else:
                    results = self.parseSearch(res)
            except Exception:
                logger.exception(
                    'YTMusic search failed for query "title"="%s"',
                    " ".join(query["track_name"]),
                )
        elif "albumartist" in query or "artist" in query:
            q1 = ("albumartist" in query and query["albumartist"]) or []
            q2 = ("artist" in query and query["artist"]) or []
            try:
                res = self.backend.api.search(
                    " ".join(q1 + q2), filter="artists"
                )
                if exact:
                    results = self.parseSearch(res, "artist", q1 + q2)
                else:
                    results = self.parseSearch(res)
            except Exception:
                logger.exception(
                    'YTMusic search failed for query "artist"="%s"',
                    " ".join(q1 + q2),
                )
        elif "album" in query:
            try:
                res = self.backend.api.search(
                    " ".join(query["album"]), filter="albums"
                )
                if exact:
                    results = self.parseSearch(res, "album", query["album"])
                else:
                    results = self.parseSearch(res)
            except Exception:
                logger.exception(
                    'YTMusic search failed for query "album"="%s"',
                    " ".join(query["album"]),
                )
        else:
            logger.debug(
                'YTMusic skipping search, unsupported field types "%s"',
                " ".join(query.keys()),
            )
            return None
        return results

    def addThumbnails(self, bId, data, addTracks=True):
        images = []
        if bId not in self.IMAGES and "thumbnails" in data:
            for th in data["thumbnails"]:
                if "url" in th:
                    images.append(
                        Image(
                            uri=th["url"],
                            width=th["width"],
                            height=th["height"],
                        )
                    )
            images.reverse()
            self.IMAGES[bId] = images
            if addTracks and "tracks" in data:
                for song in data["tracks"]:
                    if song["videoId"] not in self.IMAGES:
                        self.IMAGES[song["videoId"]] = images
        return images

    def playlistToTracks(self, pls):
        ret = []
        if "tracks" in pls:
            for track in pls["tracks"]:
                duration = ["0", "0"]
                if "duration" in track or "length" in track:
                    duration = (
                        track["duration"]
                        if "duration" in track
                        else track["length"]
                    ).split(":")
                artists = []
                if "artists" in track:
                    for a in track["artists"]:
                        if a["id"] not in self.ARTISTS:
                            self.ARTISTS[a["id"]] = Artist(
                                uri=f"ytmusic:artist:{a['id']}",
                                name=a["name"],
                                sortname=a["name"],
                                musicbrainz_id="",
                            )
                        artists.append(self.ARTISTS[a["id"]])
                elif "byline" in track:
                    artists = [
                        Artist(
                            name=track["byline"],
                            sortname=track["byline"],
                            musicbrainz_id="",
                        )
                    ]
                else:
                    artists = None

                if "album" in track and track["album"] is not None:
                    if track["album"]["id"] not in self.ALBUMS:
                        self.ALBUMS[track["album"]["id"]] = Album(
                            uri=f"ytmusic:album:{track['album']['id']}",
                            name=track["album"]["name"],
                            artists=artists,
                            num_tracks=None,
                            num_discs=None,
                            date="0000",
                            musicbrainz_id="",
                        )
                    album = self.ALBUMS[track["album"]["id"]]
                else:
                    album = None

                if track["videoId"] not in self.TRACKS:
                    self.TRACKS[track["videoId"]] = Track(
                        uri=f"ytmusic:track:{track['videoId']}",
                        name=track["title"],
                        artists=artists,
                        album=album,
                        composers=[],
                        performers=[],
                        genre="",
                        track_no=None,
                        disc_no=None,
                        date="0000",
                        length=(
                            int(duration[0]) * 60000 + int(duration[1]) * 1000
                        ),
                        bitrate=0,
                        comment="",
                        musicbrainz_id="",
                        last_modified=None,
                    )
                ret.append(self.TRACKS[track["videoId"]])
        return ret

    def uploadArtistToTracks(self, artist):
        ret = []
        for track in artist:
            artists = []
            for a in track["artist"]:
                if a["id"] not in self.ARTISTS:
                    self.ARTISTS[a["id"]] = Artist(
                        uri=f"ytmusic:artist:{a['id']}:upload",
                        name=a["name"],
                        sortname=a["name"],
                        musicbrainz_id="",
                    )
                artists.append(self.ARTISTS[a["id"]])
            if track["album"]["id"] not in self.ALBUMS:
                self.ALBUMS[track["album"]["id"]] = Album(
                    uri=f"ytmusic:album:{track['album']['id']}:upload",
                    name=track["album"]["name"],
                    artists=artists,
                    num_tracks=None,
                    num_discs=None,
                    date="0000",
                    musicbrainz_id="",
                )
            self.TRACKS[track["videoId"]] = Track(
                uri=f"ytmusic:track:{track['videoId']}",
                name=track["title"],
                artists=artists,
                album=self.ALBUMS[track["album"]["id"]],
                composers=[],
                performers=[],
                genre="",
                track_no=None,
                disc_no=None,
                date="0000",
                length=None,
                bitrate=0,
                comment="",
                musicbrainz_id="",
                last_modified=None,
            )
            ret.append(self.TRACKS[track["videoId"]])
        return ret

    def artistToTracks(self, artist):
        if (
            "songs" in artist
            and "browseId" in artist["songs"]
            and artist["songs"]["browseId"] is not None
        ):
            res = self.backend.api.get_playlist(
                artist["songs"]["browseId"],
                limit=self.backend.playlist_item_limit,
            )
            tracks = self.playlistToTracks(res)
            logger.debug(
                "YTMusic found %d tracks for %s", len(tracks), artist["name"]
            )
            return tracks
        return None

    def uploadAlbumToTracks(self, album, bId):
        ret = []
        if album["artist"]["id"] not in self.ARTISTS:
            self.ARTISTS[album["artist"]["id"]] = Artist(
                uri=f"ytmusic:artist:{album['artist']['id']}:upload",
                name=album["artist"]["name"],
                sortname=album["artist"]["name"],
                musicbrainz_id="",
            )
        artists = [self.ARTISTS[album["artist"]["id"]]]
        if bId not in self.ALBUMS:
            self.ALBUMS[bId] = Album(
                uri=f"ytmusic:album:{bId}:upload",
                name=album["title"],
                artists=artists,
                num_tracks=int(album["trackCount"])
                if str(album["trackCount"]).isnumeric()
                else None,
                num_discs=None,
                date=f"{album['year']}",
                musicbrainz_id="",
            )
        if "tracks" in album:
            for track in album["tracks"]:
                if track["videoId"] not in self.TRACKS:
                    self.TRACKS[track["videoId"]] = Track(
                        uri=f"ytmusic:track:{track['videoId']}",
                        name=track["title"],
                        artists=artists,
                        album=self.ALBUMS[bId],
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
                ret.append(self.TRACKS[track["videoId"]])
        return ret

    def albumToTracks(self, album, bId):
        ret = []
        if "realeaseDate" in album:
            date = f"{album['releaseDate']['year']}"
        elif "year" in album:
            date = album["year"]
        else:
            date = "0000"
        artists = []
        artistname = ""
        if type(album["artist"]) is list:
            artist = album["artist"][0]
        else:
            artist = album["artist"]
        if artist["id"] not in self.ARTISTS:
            self.ARTISTS[artist["id"]] = Artist(
                uri=f"ytmusic:artist:{artist['id']}",
                name=artist["name"],
                sortname=artist["name"],
                musicbrainz_id="",
            )
        artists.append(self.ARTISTS[artist["id"]])
        artistname = artist["name"]
        if bId not in self.ALBUMS:
            self.ALBUMS[bId] = Album(
                uri=f"ytmusic:album:{bId}",
                name=album["title"],
                artists=artists,
                num_tracks=int(album["trackCount"])
                if str(album["trackCount"]).isnumeric()
                else None,
                num_discs=None,
                date=date,
                musicbrainz_id="",
            )
        for song in album["tracks"]:
            if song["videoId"] not in self.TRACKS:
                # Annoying workaround for Various Artists
                if "artists" not in song or song["artists"] == artistname:
                    songartists = artists
                else:
                    songartists = [Artist(name=song["artists"])]
                self.TRACKS[song["videoId"]] = Track(
                    uri=f"ytmusic:track:{song['videoId']}",
                    name=song["title"],
                    artists=songartists,
                    album=self.ALBUMS[bId],
                    composers=[],
                    performers=[],
                    genre="",
                    track_no=int(song["index"])
                    if str(song["index"]).isnumeric()
                    else None,
                    disc_no=None,
                    date=date,
                    length=int(song["lengthMs"])
                    if str(song["lengthMs"]).isnumeric()
                    else None,
                    bitrate=0,
                    comment="",
                    musicbrainz_id="",
                    last_modified=None,
                )
            ret.append(self.TRACKS[song["videoId"]])
        self.addThumbnails(bId, album)
        return ret

    def parseSearch(self, results, field=None, queries=[]):
        tracks = set()
        salbums = set()
        sartists = set()
        for result in results:
            if result["resultType"] == "song":
                if field == "track" and not any(
                    q.casefold() == result["title"].casefold() for q in queries
                ):
                    continue
                if result["videoId"] in self.TRACKS:
                    tracks.add(self.TRACKS[result["videoId"]])
                else:
                    try:
                        length = [int(i) for i in result["duration"].split(":")]
                    except ValueError:
                        length = [0, 0]
                    if result["videoId"] is None:
                        continue
                    if result["videoId"] not in self.TRACKS:
                        artists = []
                        for a in result["artists"]:
                            if a["id"] not in self.ARTISTS:
                                self.ARTISTS[a["id"]] = Artist(
                                    uri=f"ytmusic:artist:{a['id']}",
                                    name=a["name"],
                                    sortname=a["name"],
                                    musicbrainz_id="",
                                )
                            artists.append(self.ARTISTS[a["id"]])
                        album = None
                        if "album" in result:
                            if result["album"]["id"] not in self.ALBUMS:
                                self.ALBUMS[result["album"]["id"]] = Album(
                                    uri=f"ytmusic:album:{result['album']['id']}",
                                    name=result["album"]["name"],
                                    artists=artists,
                                    num_tracks=None,
                                    num_discs=None,
                                    date="0000",
                                    musicbrainz_id="",
                                )
                                album = self.ALBUMS[result["album"]["id"]]
                        self.TRACKS[result["videoId"]] = Track(
                            uri=f"ytmusic:track:{result['videoId']}",
                            name=result["title"],
                            artists=artists,
                            album=album,
                            composers=[],
                            performers=[],
                            genre="",
                            track_no=None,
                            disc_no=None,
                            date="0000",
                            length=(length[0] * 60 * 1000) + (length[1] * 1000),
                            bitrate=0,
                            comment="",
                            musicbrainz_id="",
                            last_modified=None,
                        )
                    tracks.add(self.TRACKS[result["videoId"]])
            elif result["resultType"] == "album":
                if field == "album" and not any(
                    q.casefold() == result["title"].casefold() for q in queries
                ):
                    continue
                try:
                    if result["browseId"] not in self.ALBUMS:
                        date = result["year"]
                        self.ALBUMS[result["browseId"]] = Album(
                            uri=f"ytmusic:album:{result['browseId']}",
                            name=result["title"],
                            artists=[
                                Artist(
                                    uri="",
                                    name=result["artist"],
                                    sortname=result["artist"],
                                    musicbrainz_id="",
                                )
                            ],
                            num_tracks=None,
                            num_discs=None,
                            date=date,
                            musicbrainz_id="",
                        )
                    salbums.add(self.ALBUMS[result["browseId"]])
                except Exception:
                    logger.exception(
                        "YTMusic failed parsing album %s", result["title"]
                    )
            elif result["resultType"] == "artist":
                if field == "artist" and not any(
                    q.casefold() == result["artist"].casefold() for q in queries
                ):
                    continue
                try:
                    artistq = self.backend.api.get_artist(result["browseId"])
                    if result["browseId"] not in self.ARTISTS:
                        self.ARTISTS[result["browseId"]] = Artist(
                            uri=f"ytmusic:artist:{result['browseId']}",
                            name=artistq["name"],
                            sortname=artistq["name"],
                            musicbrainz_id="",
                        )
                    sartists.add(self.ARTISTS[result["browseId"]])
                    if "albums" in artistq:
                        if "params" in artistq["albums"]:
                            albums = self.backend.api.get_artist_albums(
                                artistq["channelId"],
                                artistq["albums"]["params"],
                            )
                            for album in albums:
                                if album["browseId"] not in self.ALBUMS:
                                    self.ALBUMS[album["browseId"]] = Album(
                                        uri=f"ytmusic:album:{album['browseId']}",
                                        name=album["title"],
                                        artists=[
                                            self.ARTISTS[result["browseId"]]
                                        ],
                                        date=album["year"],
                                        musicbrainz_id="",
                                    )
                                salbums.add(self.ALBUMS[album["browseId"]])
                        elif "results" in artistq["albums"]:
                            for album in artistq["albums"]["results"]:
                                if album["browseId"] not in self.ALBUMS:
                                    self.ALBUMS[album["browseId"]] = Album(
                                        uri=f"ytmusic:album:{album['browseId']}",
                                        name=album["title"],
                                        artists=[
                                            self.ARTISTS[result["browseId"]]
                                        ],
                                        date=album["year"],
                                        musicbrainz_id="",
                                    )
                                salbums.add(self.ALBUMS[album["browseId"]])
                    if "singles" in artistq and "results" in artistq["singles"]:
                        for single in artistq["singles"]["results"]:
                            if single["browseId"] not in self.ALBUMS:
                                self.ALBUMS[single["browseId"]] = Album(
                                    uri=f"ytmusic:album:{single['browseId']}",
                                    name=single["title"],
                                    artists=[self.ARTISTS[result["browseId"]]],
                                    date=single["year"],
                                    musicbrainz_id="",
                                )
                            salbums.add(self.ALBUMS[single["browseId"]])
                    if "songs" in artistq:
                        if "results" in artistq["songs"]:
                            for song in artistq["songs"]["results"]:
                                if song["videoId"] in self.TRACKS:
                                    tracks.add(self.TRACKS[song["videoId"]])
                                else:
                                    album = None
                                    if "album" in song:
                                        if (
                                            song["album"]["id"]
                                            not in self.ALBUMS
                                        ):
                                            self.ALBUMS[
                                                song["album"]["id"]
                                            ] = Album(
                                                uri=f"ytmusic:album:{song['album']['id']}",
                                                name=song["album"]["name"],
                                                artists=[
                                                    self.ARTISTS[
                                                        result["browseId"]
                                                    ]
                                                ],
                                                date="1999",
                                                musicbrainz_id="",
                                            )
                                        album = self.ALBUMS[song["album"]["id"]]
                                    if song["videoId"] not in self.TRACKS:
                                        self.TRACKS[song["videoId"]] = Track(
                                            uri=f"ytmusic:track:{song['videoId']}",
                                            name=song["title"],
                                            artists=[
                                                self.ARTISTS[result["browseId"]]
                                            ],
                                            album=album,
                                            composers=[],
                                            performers=[],
                                            genre="",
                                            track_no=None,
                                            disc_no=None,
                                            date="0000",
                                            length=None,
                                            bitrate=0,
                                            comment="",
                                            musicbrainz_id="",
                                            last_modified=None,
                                        )
                                    tracks.add(self.TRACKS[song["videoId"]])
                except Exception:
                    logger.exception(
                        "YTMusic failed parsing artist %s", result["artist"]
                    )
        tracks = list(tracks)
        for track in tracks:
            bId, _ = parse_uri(track.uri)
            self.TRACKS[bId] = track
        logger.debug(
            "YTMusic search returned %d results",
            len(tracks) + len(sartists) + len(salbums),
        )
        return SearchResult(
            uri="ytmusic:search",
            tracks=tracks,
            artists=list(sartists),
            albums=list(salbums),
        )


def parse_uri(uri):
    components = uri.split(":")
    bId = components[2]
    upload = (len(components) > 3 and components[3] == "upload") or False
    return bId, upload
