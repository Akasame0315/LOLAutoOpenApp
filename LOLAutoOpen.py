import os, sys, json, subprocess, time, requests
from requests.auth import HTTPBasicAuth
import tkinter as tk 
from tkinter import Tk, filedialog, messagebox
import threading
import time

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

# Check Riot Client Version
def wait_for_update(session, base_url):
    print("Checking for Riot Client update...")
    while True:
        try:
            r = session.get(f"{base_url}/product-launcher/v1/products/league_of_legends/patchlines/live")
            if r.status_code == 200:
                data = r.json()
                state = data.get("state", "").lower()
                if state == "live":
                    print("Riot Client is up-to-date.")
                    break
                elif state == "updating":
                    print("Riot Client is updating... please wait.")
                else:
                    print(f"Current patchline state: {state}")
            else:
                print(f"Failed to get patchline status: {r.status_code}")
        except requests.exceptions.RequestException:
            pass
        time.sleep(3)  # Check every 3 seconds

# Choose game to start with Riot Client
def choose_game():
    games = {
        "League of Legends": ("league_of_legends", "live"),
        "Valorant": ("valorant", "live"),
        "Teamfight Tactics": ("bacon", "live"),
        "Legends of Runeterra": ("lor", "live")
    }
    selected = {}
    root = tk.Tk()
    root.title("Riot Game Launcher")
    root.geometry("400x300")

    status_text = tk.StringVar(value="Select a game to launch:")
    
    def update_status(message):
        status_text.set(message)
        root.update_idletasks()

    def select_game(game_id, patchline):
        selected["id"] = game_id
        selected["patchline"] = patchline
        # Replace UI with status log
        for widget in root.winfo_children():
            widget.destroy()
        tk.Label(root, textvariable=status_text, font=("Arial", 12), wraplength=350).pack(pady=20)
        # Run launch in background so UI doesn't freeze
        threading.Thread(target=launch_game_process, args=(update_status,)).start()

    def launch_game_process(update_status_func):
        update_status_func(f"Starting Riot Client for {selected['id']}...")
        time.sleep(2)  # Simulate steps
        update_status_func("Waiting for lockfile...")
        time.sleep(2)
        update_status_func("Checking for updates...")
        time.sleep(2)
        update_status_func(f"Launching {selected['id']}...")
        time.sleep(1)
        update_status_func(f"{selected['id']} launched successfully!")
        time.sleep(3)
        root.destroy()

    tk.Label(root, text="Select a game:", font=("Arial", 14)).pack(pady=10)
    for name, (gid, pl) in games.items():
        tk.Button(
            root,
            text=name,
            font=("Arial", 12),
            command=lambda g=gid, p=pl: select_game(g, p)
        ).pack(pady=5, fill="x", padx=20)

    root.mainloop()
    if "id" in selected:
        return selected["id"], selected["patchline"]
    return None, None

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

    product_id, patchline = choose_game()
    if not product_id:
        print("No game selected. Exiting...")
        return
    
    args = [
        riot_client_path,
        f"--launch-product={product_id}",
        f"--launch-patchline={patchline}"
        # "--launch-product=league_of_legends",
        # "--launch-patchline=live"
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

    wait_for_update(session, base_url)

    print(f"Launching {product_id}...")
    launch_url = f"{base_url}/product-launcher/v1/products/{product_id}/patchlines/{patchline}"
    r = session.post(launch_url)

    if r.status_code == 200:
        print(f"{product_id} launched successfully!")
    else:
        print(f"Failed to launch {product_id}: {r.status_code} - {r.text}")

if __name__ == "__main__":
    main()