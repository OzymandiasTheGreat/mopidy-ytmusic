from pathlib import Path
import os
from mopidy import commands
from mopidy_ytmusic import logger


class YTMusicCommand(commands.Command):
    def __init__(self):
        super().__init__()
        self.add_child("setup", SetupCommand())


class SetupCommand(commands.Command):
    help = "Generate auth.json"

    def run(self, args, config):
        from ytmusicapi.ytmusic import YTMusic

        filepath = input(
            "Enter the path where you want to save auth.json [default=current dir]: "
        )
        if not filepath:
            filepath = os.getcwd()
        path = Path(filepath + "/auth.json")
        print('Using "' + str(path) + '"')
        if path.exists():
            print("File already exists!")
            return 1
        print(
            "Open Youtube Music, open developer tools (F12), go to Network tab,"
        )
        print(
            'right click on a POST request and choose "Copy request headers".'
        )
        print("Then paste (CTRL+SHIFT+V) them here and press CTRL+D.")
        try:
            print(YTMusic.setup(filepath=str(path)))
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
