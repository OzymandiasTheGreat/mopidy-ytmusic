****************************
Mopidy-YTMusic
****************************

.. image:: https://img.shields.io/pypi/v/Mopidy-YTMusic
    :target: https://pypi.org/project/Mopidy-YTMusic/
    :alt: Latest PyPI version

Mopidy extension for playing music from YouTube Music


Installation
============

Install by running::

    python3 -m pip install Mopidy-YTMusic

See https://mopidy.com/ext/ytmusic/ for alternative installation methods.


Configuration
=============

Before starting Mopidy, you must add configuration for
Mopidy-YTMusic to your Mopidy configuration file::

    [ytmusic]
    enabled = true

By default Mopidy-YTMusic will connect to YouTube Music as a guest account.  This
has limited options.  If you would like to connect to YouTube Music with your
account (free or premium) you'll need to generate an auth.json file and configure
Mopidy-YTMusic to use it.

To create an auth.json file run `mopidy ytmusic setup` and follow instructions
in the terminal. When you're done it will tell you what config options you need
to add to your Mopidy configuration file.

Authenticated users have access to their listening history, likes,
playlists and uploaded music.  Premium users have access to high quality audio
streams and other premium content. 

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
