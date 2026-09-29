# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_dir = Path(SPECPATH)

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all(
    "customtkinter"
)
keyring_datas, keyring_binaries, keyring_hiddenimports = collect_all(
    "keyring"
)

datas = []
datas += ctk_datas
datas += keyring_datas
datas += [
    (
        str(project_dir / "assets"),
        "assets",
    ),
    (
        str(project_dir / "vendor" / "vlc" / "plugins"),
        "vendor/vlc/plugins",
    ),
]

binaries = []
binaries += ctk_binaries
binaries += keyring_binaries
binaries += [
    (
        str(project_dir / "vendor" / "ffmpeg" / "ffmpeg.exe"),
        "vendor/ffmpeg",
    ),
    (
        str(project_dir / "vendor" / "ffmpeg" / "ffprobe.exe"),
        "vendor/ffmpeg",
    ),
    (
        str(project_dir / "vendor" / "vlc" / "libvlc.dll"),
        "vendor/vlc",
    ),
    (
        str(project_dir / "vendor" / "vlc" / "libvlccore.dll"),
        "vendor/vlc",
    ),
]

hiddenimports = []
hiddenimports += ctk_hiddenimports
hiddenimports += keyring_hiddenimports
hiddenimports += [
    "vlc",
    "keyring.backends.Windows",
    "win32ctypes",
]

analysis = Analysis(
    ["app.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="Tapo-Viewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_dir / "assets" / "icon.ico"),
)
