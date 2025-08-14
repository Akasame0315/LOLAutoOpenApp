# riot_client.py
import os
import subprocess
import time
import requests
from requests.auth import HTTPBasicAuth

def wait_for_update(riot_client_path, product_id, patchline, log_fn, timeout=60, retry_interval=3):
    """
    Launch Riot Client temporarily to check for updates.
    Retry until client is live or timeout is reached.
    """
    log_fn(f"Launching Riot Client for {product_id} update check...")

    try:
        # Start Riot Client in background for update check
        subprocess.Popen([
            riot_client_path,
            f"--launch-product={product_id}",
            f"--launch-patchline={patchline}"
        ], cwd=os.path.dirname(riot_client_path))
    except Exception as e:
        log_fn(f"[ERROR] Failed to start Riot Client: {e}")
        return False

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to read lockfile for API connection
            local_appdata = os.getenv("LOCALAPPDATA")
            lockfile_path = os.path.join(local_appdata, "Riot Games", "Riot Client", "Config", "lockfile")
            if os.path.exists(lockfile_path) and os.path.getsize(lockfile_path) > 0:
                with open(lockfile_path, "r") as f:
                    parts = f.read().strip().split(":")
                    if len(parts) == 5:
                        _, port, password, _, _ = parts
                        session = requests.Session()
                        session.auth = HTTPBasicAuth("riot", password)
                        session.verify = False
                        base_url = f"https://127.0.0.1:{port}"

                        # Check patchline status
                        r = session.get(f"{base_url}/product-launcher/v1/products/{product_id}/patchlines/{patchline}")
                        if r.status_code == 200:
                            state = r.json().get("state", "").lower()
                            if state == "live":
                                log_fn(f"{product_id} is up-to-date.")
                                return True
                            elif state == "updating":
                                log_fn(f"{product_id} is updating...")
        except Exception:
            # log_fn("wait_for_update: Waiting for Riot Client API to be ready...")
            log_fn(f"Oops, It's some exception...Let's Ignore it. :D")
            break

        time.sleep(retry_interval)

    log_fn("Timeout reached, proceeding anyway.")
    return True

def start_client_and_launch_game(riot_client_path, product_id="league_of_legends", patchline="live", log_fn=None):
    """
    Launch Riot Client and selected game after performing update check.
    """
    # First, check for updates
    wait_for_update(riot_client_path, product_id, patchline, log_fn)

    if log_fn:
        log_fn(f"Launching {product_id} via Riot Client...")

    args = [
        riot_client_path,
        f"--launch-product={product_id}",
        f"--launch-patchline={patchline}"
    ]

    try:
        subprocess.Popen(args, cwd=os.path.dirname(riot_client_path))
        if log_fn:
            log_fn(f"{product_id} launch command sent successfully.")
    except Exception as e:
        if log_fn:
            log_fn(f"[ERROR] Failed to launch {product_id}: {e}")
