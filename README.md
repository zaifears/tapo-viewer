<div align="center">

# 📷 Tapo-Viewer

**Ability to play live and download recorded clips with modern GUI from Tapo devices**

[![Latest Release](https://img.shields.io/github/v/release/zaifears/tapo-viewer?color=00A4E4&label=Latest%20Release&style=for-the-badge)](https://github.com/zaifears/tapo-viewer/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/zaifears/tapo-viewer)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Powered by PyTapo](https://img.shields.io/badge/Powered%20By-PyTapo%20v3.4.26-00A4E4?style=for-the-badge&logo=github&logoColor=white)](https://github.com/JurajNyiri/pytapo)
[![UI](https://img.shields.io/badge/UI-CustomTkinter-2B2D35?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Local-success?style=for-the-badge)](https://github.com/zaifears/tapo-viewer)

<br/>

<p align="center">
  <a href="https://github.com/zaifears/tapo-viewer/releases/latest"><b>📥 Download Standalone (.exe)</b></a> •
  <a href="#-quick-start"><b>🚀 Quick Start</b></a> •
  <a href="#-features"><b>✨ Features</b></a> •
  <a href="#-special-thanks-to-pytapo"><b>❤️ PyTapo</b></a> •
  <a href="#-supported-cameras"><b>📹 Supported Devices</b></a>
</p>

</div>

---

### 📥 Easiest Way to Run (No Python Required)

If you just want to use the app without touching Python or terminal commands:

1. Head over to **[Releases](https://github.com/zaifears/tapo-viewer/releases/latest)**.
2. Download **`Tapo-Viewer.exe`** (or the `.zip` archive).
3. Double-click to run. All dependencies and UI assets are baked into the executable.

---

## 💡 What is Tapo-Viewer?

Official Tapo desktop software does not exist, and viewing SD card recordings usually forces you to use the mobile app or pay for Tapo Care cloud storage.

**Tapo-Viewer** gives you a clean desktop app on Windows to:
- **Watch live camera feeds** directly inside your favorite desktop player (VLC, mpv.net, PotPlayer, or FFplay) with zero latency.
- **Browse SD card recordings** through an interactive calendar with dots marking days that contain recordings.
- **Download motion events and continuous recordings** directly to your computer as ready-to-watch `.mp4` video files.
- **Keep everything 100% private and local.** The app communicates directly with your camera over your home Wi-Fi/LAN. Nothing is sent to third-party servers.

---

## ✨ Features

- **Direct RTSP Live Stream:** Launches your live feed in mpv.net, PotPlayer, VLC, or FFplay with hardware acceleration and no command prompt window popups.
- **Recording Calendar:** Custom calendar that marks dates with recordings stored on the camera's MicroSD card.
- **Batch Motion Timeline:** Smooth 60fps scrolling list with badges indicating whether an event is motion-triggered or continuous recording.
- **Automatic MP4 Conversion:** Downloads clips and remuxes them to standard `.mp4` with AAC audio (with fallback to `.ts` if FFmpeg is not installed).
- **Persistent Bottom Download Bar:** Keep track of active downloads with progress percentages and cancel buttons anytime.
- **Custom Save Locations:** Save recordings to any drive, external hard drive, or network share folder.
- **Clean Responsive Dark UI:** Designed to fit nicely on standard laptop displays (1366×768) and high-DPI screens, with `F11` fullscreen support.
- **Privacy By Default:** Login credentials are never saved unless you explicitly check the save box.

---

## ❤️ Special Thanks to PyTapo

This project relies heavily on the open-source **[pytapo](https://github.com/JurajNyiri/pytapo)** library by **[Juraj Nyíri](https://github.com/JurajNyiri)**.

PyTapo reverse-engineers TP-Link's local camera communication protocol, making it possible to:
- Authenticate locally with camera hardware over HTTP/HTTPS.
- Query recording date availability and motion event timestamps from the internal MicroSD card.
- Download media chunks directly from the camera at full Wi-Fi speed without an active internet connection.

Without Juraj Nyíri's continuous work on `pytapo`, accessing local Tapo MicroSD recordings outside the mobile app would not be possible.

---

## 📹 Supported Cameras

Works with any TP-Link Tapo camera that supports local RTSP and ONVIF accounts, including:

- **Indoor:** Tapo C100, C110, C200, C210, C220, C225, TC70
- **Outdoor:** Tapo C310, C320WS, C325WB, C500, C510W, C520WS
- **Other models:** Any Tapo camera running current firmware with local camera account support.

---

## 🚀 Quick Start (Running from Source)

### 1. Requirements
- Windows 10 or Windows 11 (64-bit)
- [Python 3.10+](https://www.python.org/downloads/)
- *(Optional but recommended)* [FFmpeg](https://ffmpeg.org/) for automatic MP4 remuxing (`winget install Gyan.FFmpeg`)

### 2. Clone and Setup
```powershell
git clone https://github.com/zaifears/tapo-viewer.git
cd tapo-viewer
```

### 3. Run
Simply double-click **`run.bat`**. 

On first run, `run.bat` automatically creates the `.venv` environment, installs all required dependencies from `requirements.txt`, and launches the app.

Or run manually:
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

---

## 🛠️ Building Your Own Executable

To compile a single standalone `.exe`:

Double-click **`build_exe.bat`** or run:

```powershell
.\.venv\Scripts\pip install pyinstaller
.\.venv\Scripts\pyinstaller --noconsole --onefile --clean --collect-all customtkinter --add-data "assets;assets" --name "Tapo-Viewer" app.py
```

Your binary will be generated inside `dist\Tapo-Viewer.exe`.

---

## 👤 Author

Developed by **Shahoriar Hossain**
- **GitHub:** [@zaifears](https://github.com/zaifears)
- **Repository:** [github.com/zaifears/tapo-viewer](https://github.com/zaifears/tapo-viewer)
- **Check out my other projects:** [LocReminder](https://github.com/zaifears/locreminder)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
