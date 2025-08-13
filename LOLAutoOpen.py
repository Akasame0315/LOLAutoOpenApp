import os, sys, json, subprocess, time, requests
from requests.auth import HTTPBasicAuth
from tkinter import Tk, filedialog, messagebox

# Get path where exe is located
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "appsettings.json")

# Default path
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

# Ensure config exists
def load_or_create_config():
    config = {}
    
    # Load if exists
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f) or {}
        except json.JSONDecodeError:
            config = {}

    # Try to auto-fill missing values
    if not config.get("riotClientPath"):
        auto_path = auto_find_file(COMMON_RIOT_PATHS)
        if auto_path:
            config["riotClientPath"] = auto_path

    if not config.get("lockfileDir"):
        auto_lock_dir = auto_find_file(COMMON_LOCKFILE_DIRS)
        if auto_lock_dir:
            config["lockfileDir"] = auto_lock_dir

    # If still missing, ask user
    if not config.get("riotClientPath") or not config.get("lockfileDir"):
        messagebox.showinfo("First-time Setup", "Please select Riot Client path and lockfile folder.")

        if not config.get("riotClientPath"):
            riot_path = filedialog.askopenfilename(
                title="Select RiotClientServices.exe",
                filetypes=[("Executable", "*.exe")])
            if not riot_path:
                raise FileNotFoundError("RiotClientServices.exe not selected.")
            config["riotClientPath"] = riot_path

        if not config.get("lockfileDir"):
            lockfile_dir = filedialog.askdirectory(
                title="Select lockfile folder (Config folder in Riot Client)")
            if not lockfile_dir:
                raise FileNotFoundError("Lockfile folder not selected.")
            config["lockfileDir"] = lockfile_dir

    # Save config
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

    return config

def main():
    Tk().withdraw()  # Hide Tkinter root window

    config = load_or_create_config()
    riot_client_path = config["riotClientPath"]
    lockfile_path = os.path.join(config["lockfileDir"], "lockfile")

    args = [
        riot_client_path,
        "--launch-product=league_of_legends",
        "--launch-patchline=live"
    ]

    if not os.path.exists(riot_client_path):
        messagebox.showerror("Error", f"Riot Client not found: {riot_client_path}")
        return

    print("Starting Riot Client...")
    subprocess.Popen(args, cwd=os.path.dirname(riot_client_path))

    print("Waiting for Riot Client login...")
    while not os.path.exists(lockfile_path) or os.path.getsize(lockfile_path) == 0:
        time.sleep(1)

    print("Lockfile found, reading...")
    with open(lockfile_path, "r") as f:
        name, port, password, protocol, address = f.read().split(":")

    session = requests.Session()
    session.auth = HTTPBasicAuth("riot", password)
    session.verify = False
    base_url = f"https://127.0.0.1:{port}"

    while True:
        try:
            r = session.get(f"{base_url}/riotclient/region-locale")
            if r.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

    print("Launching League of Legends...")
    launch_url = f"{base_url}/product-launcher/v1/products/league_of_legends/patchlines/live"
    r = session.post(launch_url)

    if r.status_code == 200:
        print("League of Legends launched successfully!")
    else:
        print(f"Failed to launch LoL: {r.status_code} - {r.text}")

if __name__ == "__main__":
    main()