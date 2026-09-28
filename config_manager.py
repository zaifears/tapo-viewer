import json
import os
import sys

def get_app_dir() -> str:
    """Returns persistent application directory (next to .exe if frozen, or script dir)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "host": "",
    "username": "",
    "password": "",
    "cloud_password": "",
    "save_credentials": False,
    "output_dir": os.path.join(APP_DIR, "recordings"),
    "auto_play_after_download": True,
    "preferred_player": "auto",
    "custom_player_path": ""
}

def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"Error loading config: {e}")
    # Ensure output_dir exists
    os.makedirs(config["output_dir"], exist_ok=True)
    return config

def save_config(config_data: dict) -> bool:
    try:
        # If save_credentials is False, clear sensitive fields before saving
        to_save = config_data.copy()
        if not to_save.get("save_credentials", False):
            to_save["password"] = ""
            to_save["cloud_password"] = ""

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
