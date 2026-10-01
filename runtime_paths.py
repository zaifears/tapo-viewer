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


def ffplay_path() -> Optional[str]:
    return find_executable("ffplay", "vendor/ffmpeg")


def vlc_exe_path() -> Optional[str]:
    return find_executable("vlc", "vendor/vlc")


def vlc_runtime_dir() -> Optional[Path]:
    """
    Resolve bundled LibVLC or an installed VLC runtime.
    """
    # 1. Bundled in vendor/vlc (standard bundle layout)
    bundled = resource_path("vendor", "vlc")
    if (bundled / "libvlc.dll").is_file():
        return bundled

    # 2. Bundled at root of bundle
    root_bundled = bundle_dir()
    if (root_bundled / "libvlc.dll").is_file():
        return root_bundled

    # 3. System installed VLC
    if os.name == "nt":
        candidates = [
            Path(os.environ.get("PROGRAMFILES", "")) / "VideoLAN" / "VLC",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "VideoLAN" / "VLC",
        ]

        for candidate in candidates:
            if candidate and (candidate / "libvlc.dll").is_file():
                return candidate

    return None


def vlc_plugins_dir(runtime: Optional[Path] = None) -> Optional[Path]:
    """
    Locate the VLC plugins directory for the active runtime.
    """
    if runtime is None:
        runtime = vlc_runtime_dir()

    if runtime:
        candidate = runtime / "plugins"
        if candidate.is_dir():
            return candidate

    # Check bundle vendor/vlc/plugins
    bundled = resource_path("vendor", "vlc", "plugins")
    if bundled.is_dir():
        return bundled

    # Check bundle root plugins
    root_bundled = bundle_dir() / "plugins"
    if root_bundled.is_dir():
        return root_bundled

    return None


def prepare_vlc_environment() -> Path:
    """
    Configure DLL and plugin discovery before importing vlc.
    Explicitly synchronizes python-vlc, C runtime, and Win32 process environments.
    """
    runtime = vlc_runtime_dir()

    if runtime is None:
        raise RuntimeError(
            "LibVLC runtime was not found. The application installation "
            "may be incomplete. Reinstall Tapo-Viewer or install VLC."
        )

    libvlc_dll = runtime / "libvlc.dll"
    libvlccore_dll = runtime / "libvlccore.dll"
    plugin_dir = vlc_plugins_dir(runtime)

    if not libvlc_dll.is_file():
        raise RuntimeError(
            f"LibVLC library file not found: {libvlc_dll}"
        )

    # 1. Explicitly inform python-vlc module of library and module paths
    dll_path_str = str(libvlc_dll.resolve())
    os.environ["PYTHON_VLC_LIB_PATH"] = dll_path_str
    if plugin_dir:
        plugin_path_str = str(plugin_dir.resolve())
        os.environ["PYTHON_VLC_MODULE_PATH"] = plugin_path_str
        os.environ["VLC_PLUGIN_PATH"] = plugin_path_str

    # 2. Synchronize Win32 process environment variables so C/C++ runtime reads them
    if os.name == "nt":
        try:
            import ctypes
            set_env = ctypes.windll.kernel32.SetEnvironmentVariableW
            set_env("PYTHON_VLC_LIB_PATH", dll_path_str)
            if plugin_dir:
                set_env("PYTHON_VLC_MODULE_PATH", plugin_path_str)
                set_env("VLC_PLUGIN_PATH", plugin_path_str)
        except Exception:
            pass

    # 3. Add runtime to PATH
    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{runtime.resolve()}{os.pathsep}{current_path}"

    # 4. Windows DLL directory and pre-loading
    if os.name == "nt":
        if hasattr(os, "add_dll_directory"):
            global _VLC_DLL_HANDLE
            try:
                _VLC_DLL_HANDLE = os.add_dll_directory(str(runtime.resolve()))
            except Exception:
                pass

        try:
            import ctypes
            if libvlccore_dll.is_file():
                ctypes.CDLL(str(libvlccore_dll.resolve()))
            ctypes.CDLL(dll_path_str)
        except Exception:
            pass

    return runtime


_VLC_DLL_HANDLE = None
