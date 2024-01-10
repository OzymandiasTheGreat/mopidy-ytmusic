import os
from pathlib import Path

from mopidy import commands

from mopidy_ytmusic import logger


class YTMusicCommand(commands.Command):
    def __init__(self):
        super().__init__()
        self.add_child("setup", SetupCommand())
        self.add_child("reauth", ReSetupCommand())


class SetupCommand(commands.Command):
    help = "Generate auth.json"

    def run(self, args, config):
        from ytmusicapi.setup import setup_oauth

        filepath = input(
            "Enter the path where you want to save auth.json [default=current dir]: "
        )
        if not filepath:
            filepath = os.getcwd()
        path = Path(filepath + "/oauth.json")
        print('Using "' + str(path) + '"')
        if path.exists():
            print("File already exists!")
            return 1
        try:
            setup_oauth(filepath=str(path))
        except Exception:
            logger.exception("YTMusic setup failed")
            return 1
        print("Authentication JSON data saved to {}".format(str(path)))
        print("")
        print("Update your mopidy.conf to reflect the new auth file:")
        print("   [ytmusic]")
        print("   enabled=true")
        print("   auth_json=" + str(path))
        return 0


class ReSetupCommand(commands.Command):
    help = "Regenerate auth.json"

    def run(self, args, config):
        from ytmusicapi import YTMusic

        path = config["ytmusic"]["auth_json"]
        usingOauth = False
        if not path:
            logger.error("auth_json path not defined in config")
            return 1
        if config["ytmusic"]["oauth_json"] is not None:
            path = config["ytmusic"]["oauth_json"]
            usingOauth = True
        print('Updating credentials in  "' + str(path) + '"')
        if not usingOauth:
            print(
                "Open Youtube Music, open developer tools (F12), go to Network tab,"
            )
            print(
                'right click on a POST request and choose "Copy request headers".'
            )
            print("Then paste (CTRL+SHIFT+V) them here and press CTRL+D.")
        else:
            print("Updating via oauth, follow the instructions from ytmusicapi")
        try:
            print(YTMusic(auth=path))
        except Exception:
            logger.exception("YTMusic setup failed")
            return 1
        print("Authentication JSON data saved to {}".format(str(path)))
        return 0
