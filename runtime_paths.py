from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


APP_NAME = "Tapo-Viewer"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """
    Directory containing resources bundled by PyInstaller.

    In source mode:
        Project directory

    In PyInstaller one-file mode:
        Temporary extraction directory referenced by sys._MEIPASS
    """
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()

    return Path(__file__).resolve().parent


def executable_dir() -> Path:
    """
    Directory containing the executable or source entry point.

    Do not use this directory for mutable application data because it may be
    read-only when installed under Program Files.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    r"""
    Persistent per-user application-data directory.

    Windows:
        %LOCALAPPDATA%\Tapo-Viewer

    Fallback:
        ~/AppData/Local/Tapo-Viewer
    """
    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        path = Path(local_app_data) / APP_NAME
    else:
        path = Path.home() / "AppData" / "Local" / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def recordings_dir() -> Path:
    path = user_data_dir() / "recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(*parts: str) -> Path:
    return bundle_dir().joinpath(*parts)


def find_executable(
    executable_name: str,
    bundled_relative_dir: Optional[str] = None,
) -> Optional[str]:
    r"""
    Resolve a bundled executable first and then fall back to PATH.

    Example:
        find_executable("ffmpeg.exe", "vendor/ffmpeg")
    """
    names = [executable_name]

    if os.name == "nt" and not executable_name.lower().endswith(".exe"):
        names.insert(0, f"{executable_name}.exe")

    if bundled_relative_dir:
        for name in names:
            candidate = resource_path(
                *bundled_relative_dir.replace("\\", "/").split("/"),
                name,
            )

            if candidate.is_file():
                return str(candidate)

    for name in names:
        path = shutil.which(name)
        if path:
            return path

    return None


def ffmpeg_path() -> Optional[str]:
    return find_executable("ffmpeg", "vendor/ffmpeg")


def ffprobe_path() -> Optional[str]:
    return find_executable("ffprobe", "vendor/ffmpeg")


def vlc_runtime_dir() -> Optional[Path]:
    """
    Resolve bundled LibVLC or an installed VLC runtime.
    """
    bundled = resource_path("vendor", "vlc")

    if (bundled / "libvlc.dll").is_file():
        return bundled

    if os.name == "nt":
        candidates = [
            Path(os.environ.get("PROGRAMFILES", "")) / "VideoLAN" / "VLC",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "VideoLAN" / "VLC",
        ]

        for candidate in candidates:
            if candidate and (candidate / "libvlc.dll").is_file():
                return candidate

    return None


def prepare_vlc_environment() -> Path:
    """
    Configure DLL and plugin discovery before importing vlc.
    """
    runtime = vlc_runtime_dir()

    if runtime is None:
        raise RuntimeError(
            "LibVLC runtime was not found. The application installation "
            "may be incomplete. Reinstall Tapo-Viewer or install VLC."
        )

    plugin_dir = runtime / "plugins"

    if plugin_dir.is_dir():
        os.environ["VLC_PLUGIN_PATH"] = str(plugin_dir)

    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{runtime}{os.pathsep}{current_path}"

    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        # Keep the returned handle alive for the lifetime of the process.
        global _VLC_DLL_HANDLE
        _VLC_DLL_HANDLE = os.add_dll_directory(str(runtime))

    return runtime


_VLC_DLL_HANDLE = None
