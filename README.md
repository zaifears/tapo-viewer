# 📷 Tapo-Viewer

A modern, production-grade Windows desktop studio for TP-Link Tapo cameras (C100, C200, C310, C320WS, C500, TC70, and all Tapo series). Built with Python, CustomTkinter, PyTapo, and FFmpeg.

**100% Local & Private.** All camera feeds, motion events, and MicroSD recordings stream directly over your local Wi-Fi or LAN with zero external cloud dependencies or subscriptions.

---

## ✨ Key Features

- **Responsive Onboarding Portal:** Fits standard laptop screens (1366×768) and high-DPI displays with zero vertical scrolling. Includes port reachability diagnostics (554 & 443), password visibility toggles, and step-by-step setup guides.
- **Hardware-Accelerated Live Feed:** Streams live 1080p video directly in your favorite player (**mpv.net**, **PotPlayer**, **VLC**, **FFplay**, or custom executable) with zero command prompt popups.
- **Native MP4 Clip Downloads:** Downloads recordings directly into high-compatibility `.mp4` format with lossless stream remuxing and automatic integrity verification.
- **Visual MicroSD Calendar:** Custom calendar widget with Segoe UI typography and signature Tapo Blue indicator dots for days with stored recordings.
- **Virtual Batch Timeline:** Jitter-free 60fps scrolling with virtual pagination that easily manages days with hundreds of motion events.
- **Flexible Storage:** Store clips on any local drive (`C:`, `D:`, external USB, or NAS share) with live directory switching and write-permission checks.
- **Permanently Docked Manager:** Always-visible bottom status panel with real-time download progress, folder quick-access, and cancel actions.
- **Fullscreen & Window Controls:** Automatically opens maximized on launch, with `F11` key for true fullscreen viewing.

---

## 🚀 Quick Start

### 1. Requirements
- Windows 10 or 11 (64-bit)
- Python 3.10+ (Python 3.13 recommended)
- FFmpeg installed and in your system PATH (e.g. via `winget install Gyan.FFmpeg`)

### 2. Installation
```powershell
git clone https://github.com/zaifears/tapo-viewer.git
cd tapo-viewer
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 3. Running
Double-click `run.bat` or run:
```powershell
.\.venv\Scripts\python.exe app.py
```

---

## 📦 Building Standalone Executable (.exe)

To bundle Tapo-Viewer into a single portable `.exe` for distribution:

```powershell
.\.venv\Scripts\pip install pyinstaller
.\.venv\Scripts\pyinstaller --noconsole --onefile --add-data "assets;assets" --name "Tapo-Viewer" app.py
```
The output file will be in `dist\Tapo-Viewer.exe`.

---

## 👤 Developer & Credits

- **Developer:** Shahoriar Hossain ([@zaifears](https://github.com/zaifears))
- **GitHub:** [github.com/zaifears/tapo-viewer](https://github.com/zaifears/tapo-viewer)
- **License:** MIT License
