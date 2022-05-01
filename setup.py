# -*- coding: utf-8 -*-
from setuptools import setup

packages = ["mopidy_ytmusic"]

package_data = {"": ["*"]}

install_requires = [
    "Mopidy>=3,<4",
    "pytube>=12.1.0,<13.0.0",
    "ytmusicapi>=0.22.0,<0.23.0",
]

entry_points = {"mopidy.ext": ["ytmusic = mopidy_ytmusic:Extension"]}

setup_kwargs = {
    "name": "mopidy-ytmusic",
    "version": "0.3.5",
    "description": "Mopidy extension for playling music/managing playlists in Youtube Music",
    "long_description": None,
    "author": "Ozymandias (Tomas Ravinskas)",
    "author_email": "tomas.rav@gmail.com",
    "maintainer": None,
    "maintainer_email": None,
    "url": None,
    "packages": packages,
    "package_data": package_data,
    "install_requires": install_requires,
    "entry_points": entry_points,
    "python_requires": ">=3.7,<4.0",
}


setup(**setup_kwargs)
