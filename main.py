# main.py
import os
import sys
import threading
from config import load_or_create_config
from riot_client import start_client_and_launch_game
from game_ui import GameLauncherUI

BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "appsettings.json")


def main():
    # Load configuration
    config = load_or_create_config(CONFIG_PATH)
    riot_client_path = config["riotClientPath"]

    # Create UI and set callback for when user chooses game
    def on_game_selected(product_id, patchline):
        threading.Thread(
            target=start_game,
            args=(riot_client_path, product_id, patchline, ui.log),
            daemon=True
        ).start()

    ui = GameLauncherUI(on_select=on_game_selected)
    ui.run()


def start_game(riot_client_path, product_id, patchline, log_fn):
    """
    Check for updates and launch the game.
    """
    start_client_and_launch_game(riot_client_path, product_id, patchline, log_fn)


if __name__ == "__main__":
    main()
