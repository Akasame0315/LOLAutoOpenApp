import os
import json
from tkinter import filedialog, messagebox

COMMON_RIOT_PATHS = [
    r"C:\Riot Games\Riot Client\RiotClientServices.exe"
]
COMMON_LOCKFILE_DIRS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Riot Games\Riot Client\Config")
]

def auto_find_file(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def load_or_create_config(config_path):
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f) or {}
        except json.JSONDecodeError:
            config = {}

    if not config.get("riotClientPath"):
        auto_path = auto_find_file(COMMON_RIOT_PATHS)
        if auto_path:
            config["riotClientPath"] = auto_path

    if not config.get("lockfileDir"):
        auto_lock_dir = auto_find_file(COMMON_LOCKFILE_DIRS)
        if auto_lock_dir:
            config["lockfileDir"] = auto_lock_dir

    if not config.get("riotClientPath") or not config.get("lockfileDir"):
        messagebox.showinfo("Setup", "Please select Riot Client path and lockfile folder.")
        if not config.get("riotClientPath"):
            riot_path = filedialog.askopenfilename(title="Select RiotClientServices.exe", filetypes=[("Executable", "*.exe")])
            if not riot_path:
                raise FileNotFoundError("RiotClientServices.exe not selected.")
            config["riotClientPath"] = riot_path
        if not config.get("lockfileDir"):
            lockfile_dir = filedialog.askdirectory(title="Select Riot Client 'Config' folder")
            if not lockfile_dir:
                raise FileNotFoundError("Lockfile folder not selected.")
            config["lockfileDir"] = lockfile_dir

    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

    return config
