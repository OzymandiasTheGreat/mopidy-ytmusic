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
    auth_json = ./auth.json

To acquire auth.json file run `mopidy ytmusic setup` and follow instructions
in the terminal.

Build for Local Install
=======================

1. Install `poetry <https://python-poetry.org/docs/#installation>`
2. To create the build tarball, run::
    poetry build
3. The `dist/Mopidy-YTMusic-x.x.x.tar.gz` file is what you'll use to install.
4. To install or reinstall an over an existing version with pip, run something similar::
    python3 -m pip install dist/Mopidy-YTMusic-x.x.x.tar.gz
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
