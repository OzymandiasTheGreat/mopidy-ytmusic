****************************
Mopidy-YTMusic
****************************

.. image:: https://img.shields.io/pypi/v/Mopidy-YTMusic
    :target: https://pypi.org/project/Mopidy-YTMusic/
    :alt: Latest PyPI Version

.. image:: https://img.shields.io/github/v/release/OzymandiasTheGreat/mopidy-ytmusic
    :target: https://github.com/OzymandiasTheGreat/mopidy-ytmusic/releases
    :alt: Latest GitHub Release

.. image:: https://img.shields.io/github/commits-since/OzymandiasTheGreat/mopidy-ytmusic/latest
    :target: https://github.com/OzymandiasTheGreat/mopidy-ytmusic/commits/master
    :alt: Commits Since Latest Release

Mopidy extension for playing music from YouTube Music


Installation
============

Install by running::

    sudo python3 -m pip install Mopidy-YTMusic

See https://mopidy.com/ext/ytmusic/ for alternative installation methods.


Configuration
=============

By default Mopidy-YTMusic will connect to YouTube Music as a guest account.  This
has limited options.  If you would like to connect to YouTube Music with your
account (free or premium) you'll need to generate an auth.json file and configure
Mopidy-YTMusic to use it.

To create an auth.json file run :code:`mopidy ytmusic setup` (or 
:code:`sudo mopidyctl ytmusic setup` if you're running mopidy as a service, also see below) and
follow the instructions in the terminal. When you're done it will tell you what
config options you need to add to your Mopidy configuration file.
It should look something like this:

.. code::

    [ytmusic]
    auth_json = /path/to/auth.json


Authenticated users have access to their listening history, likes,
playlists and uploaded music.  Premium users have access to high quality audio
streams and other premium content. 

Annoyingly, those authentication credentials will expire from time to time.
Run :code:`mopidy ytmusic reauth` (or :code:`sudo mopidyctl ytmusic reauth`) to
paste in new headers and overwrite your existing auth.json file.
Then restart mopidy for the new credentials to go into effect.

Other configuration options are as follows:

- :code:`auto_playlist_refresh` - time (in minutes) to refresh the Auto playlists.  Default: 60. Set to 0 to disable auto playlists.
- :code:`youtube_player_refresh` - time (in minutes) to refresh the Youtube player url (used for decoding the signature).  Default: 15
- :code:`playlist_item_limit` - Number of items to grab from playlists.  This is not exact.  Default: 100
- :code:`subscribed_artist_limit` - Number of subscriptions to list. Default: 100. Set to 0 to disable subscription list.
- :code:`enable_history` - Show Recently Played playlist. Default: yes
- :code:`enable_like_songs` - Show Liked Songs playlist. Default: yes
- :code:`enable_mood_genre` - Show Mood & Genre playlists from YouTube Music's Explore directory. Default: yes
- :code:`enable_scrobbling` - Mark tracks as played on YouTube Music after listening.  Default: yes
- :code:`stream_preference` - Comma separated list of itags in the order of preference you want for stream.  Default: "141, 251, 140, 250, 249"
- :code:`verify_track_url` - Verify that track url is valid before sending to mopidy. Default: yes.  There should be no need to set this to no.

Info on YouTube Music streams:

+----------+-------+-------------+----------+
| itag     | Codec | Sample Rate | Bit Rate |
+==========+=======+=============+==========+
| 141 [*]_ | AAC   | 44.1kHz     | ~260kbps |
+----------+-------+-------------+----------+
| 251      | Opus  | 48kHz       | ~150kbps |
+----------+-------+-------------+----------+
| 140      | AAC   | 44.1kHz     | ~132kbps |
+----------+-------+-------------+----------+
| 250      | Opus  | 48kHz       | ~80kbps  |
+----------+-------+-------------+----------+
| 249      | Opus  | 48kHz       | ~64kbps  |
+----------+-------+-------------+----------+

.. [*] Available to premium accounts only.


Note for users running mopidy as a service:
-------------------------------------------

Since the mopidy user will end up
trying to create the auth.json file, you'll likely want to specify the path as
:code:`/tmp` when you run :code:`sudo mopidyctl ytmusic setup`.  Then you can
move the :code:`/tmp/auth.json` to :code:`/etc/mopidy` and add:

.. code::

    [ytmusic]
    auth_json = /etc/mopidy/auth.json

to your :code:`/etc/mopidy/mopidy.conf` file.  To make reauthentication easier,
make sure the auth.json file is owned by the mopidy user by running
:code:`sudo chown mopidy /etc/mopidy/auth.json`.

Build for Local Install
=======================

1. Install `poetry <https://python-poetry.org/docs/#installation>`
2. Run :code:`poetry build` to create the build tarball
3. The :code:`dist/Mopidy-YTMusic-x.x.x.tar.gz` file is what you'll use to install.
4. With pip: :code:`python3 -m pip install dist/Mopidy-YTMusic-x.x.x.tar.gz` to install or reinstall over an existing version.
5. Do configuration stuff if you haven't already.  


Project resources
=================

- `Source code <https://github.com/OzymandiasTheGreat/mopidy-ytmusic>`_
- `Issue tracker <https://github.com/OzymandiasTheGreat/mopidy-ytmusic/issues>`_
- `Changelog <https://github.com/OzymandiasTheGreat/mopidy-ytmusic/blob/master/CHANGELOG.rst>`_


Credits
=======

- Original author: `Tomas Ravinskas <https://github.com/OzymandiasTheGreat>`__
- Current maintainer: `Tomas Ravinskas <https://github.com/OzymandiasTheGreat>`__
- `Contributors <https://github.com/OzymandiasTheGreat/mopidy-ytmusic/graphs/contributors>`_
