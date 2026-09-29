from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from runtime_paths import recordings_dir, user_data_dir


APP_NAME = "Tapo-Viewer"
KEYRING_SERVICE = "Tapo-Viewer"

APP_DIR = str(user_data_dir())
CONFIG_FILE = str(user_data_dir() / "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "host": "",
    "username": "",
    "save_credentials": False,
    "output_dir": str(recordings_dir()),
    "auto_play_after_download": True,
    "preferred_player": "embedded",
    "custom_player_path": "",
    "live_stream_quality": "HD",
    "live_stream_muted": True,
    "live_stream_volume": 50,
}


def _credential_account(
    credential_type: str,
    host: str,
    username: str,
) -> str:
    normalized_host = host.strip().lower()
    normalized_username = username.strip().lower()

    return (
        f"{credential_type}:"
        f"{normalized_username}@{normalized_host}"
    )


def _camera_account(host: str, username: str) -> str:
    return _credential_account("camera", host, username)


def _cloud_account(host: str, username: str) -> str:
    return _credential_account("cloud", host, username)


def save_credentials(
    host: str,
    username: str,
    camera_password: str,
    cloud_password: Optional[str] = None,
) -> None:
    """
    Store credentials in the operating-system credential store.

    Raises:
        RuntimeError when the credential backend cannot save the password.
    """
    if not host.strip() or not username.strip():
        raise ValueError(
            "Host and username are required before credentials can be saved."
        )

    if not camera_password:
        raise ValueError("Camera password cannot be empty.")

    try:
        keyring.set_password(
            KEYRING_SERVICE,
            _camera_account(host, username),
            camera_password,
        )

        if cloud_password:
            keyring.set_password(
                KEYRING_SERVICE,
                _cloud_account(host, username),
                cloud_password,
            )
        else:
            delete_cloud_password(host, username)

    except KeyringError as exc:
        raise RuntimeError(
            "Windows Credential Manager could not save the credentials."
        ) from exc


def load_credentials(
    host: str,
    username: str,
) -> Tuple[str, str]:
    if not host.strip() or not username.strip():
        return "", ""

    try:
        camera_password = keyring.get_password(
            KEYRING_SERVICE,
            _camera_account(host, username),
        ) or ""

        cloud_password = keyring.get_password(
            KEYRING_SERVICE,
            _cloud_account(host, username),
        ) or ""

        return camera_password, cloud_password

    except KeyringError as exc:
        raise RuntimeError(
            "Windows Credential Manager could not retrieve the credentials."
        ) from exc


def delete_camera_password(host: str, username: str) -> None:
    try:
        keyring.delete_password(
            KEYRING_SERVICE,
            _camera_account(host, username),
        )
    except PasswordDeleteError:
        pass
    except KeyringError as exc:
        raise RuntimeError(
            "Windows Credential Manager could not delete the camera password."
        ) from exc


def delete_cloud_password(host: str, username: str) -> None:
    try:
        keyring.delete_password(
            KEYRING_SERVICE,
            _cloud_account(host, username),
        )
    except PasswordDeleteError:
        pass
    except KeyringError as exc:
        raise RuntimeError(
            "Windows Credential Manager could not delete the cloud password."
        ) from exc


def delete_credentials(host: str, username: str) -> None:
    delete_camera_password(host, username)
    delete_cloud_password(host, username)


def _safe_output_directory(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        selected = Path(value).expanduser()

        try:
            selected.mkdir(parents=True, exist_ok=True)
            return str(selected.resolve())
        except OSError:
            pass

    fallback = recordings_dir()
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback.resolve())


def _migrate_plaintext_credentials(
    raw_config: Dict[str, Any],
) -> bool:
    """
    Migrate legacy plaintext password fields into Windows Credential Manager.

    Returns True when the JSON file must be rewritten.
    """
    camera_password = raw_config.get("password")
    cloud_password = raw_config.get("cloud_password")
    save_requested = bool(raw_config.get("save_credentials", False))

    contains_legacy_fields = (
        "password" in raw_config or
        "cloud_password" in raw_config
    )

    if (
        save_requested
        and camera_password
        and raw_config.get("host")
        and raw_config.get("username")
    ):
        save_credentials(
            host=str(raw_config["host"]),
            username=str(raw_config["username"]),
            camera_password=str(camera_password),
            cloud_password=(
                str(cloud_password)
                if cloud_password
                else None
            ),
        )

    raw_config.pop("password", None)
    raw_config.pop("cloud_password", None)

    return contains_legacy_fields


def load_config() -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    config_path = Path(CONFIG_FILE)

    if config_path.is_file():
        try:
            with config_path.open("r", encoding="utf-8") as file:
                saved = json.load(file)

            if not isinstance(saved, dict):
                raise ValueError("Configuration root must be a JSON object.")

            needs_rewrite = _migrate_plaintext_credentials(saved)
            config.update(saved)

            if needs_rewrite:
                save_config(config)

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            KeyringError,
            RuntimeError,
        ) as exc:
            print(f"Configuration loading warning: {exc}")

    config["output_dir"] = _safe_output_directory(
        config.get("output_dir")
    )

    return config


def save_config(config_data: Dict[str, Any]) -> bool:
    """
    Write non-secret configuration atomically.

    Password fields are always excluded, even if callers accidentally pass
    them in config_data.
    """
    destination = Path(CONFIG_FILE)
    destination.parent.mkdir(parents=True, exist_ok=True)

    to_save = DEFAULT_CONFIG.copy()
    to_save.update(config_data)

    # Never serialize secrets.
    to_save.pop("password", None)
    to_save.pop("cloud_password", None)

    to_save["output_dir"] = _safe_output_directory(
        to_save.get("output_dir")
    )

    temp_path: Optional[str] = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(destination.parent),
            prefix="config-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(
                to_save,
                temp_file,
                indent=4,
                ensure_ascii=False,
            )
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = temp_file.name

        os.replace(temp_path, destination)
        return True

    except OSError as exc:
        print(f"Configuration saving error: {exc}")

        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        return False
