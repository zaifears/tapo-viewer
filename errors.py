"""
Central error diagnosis for Tapo-Viewer.

Every failure shown to the user is turned into a ``Diagnosis`` that says:
  * WHAT failed (title + summary, in plain language),
  * WHY it most likely failed (causes),
  * HOW to fix it (numbered steps),
  * and keeps the raw technical text for support/bug reports.

``diagnose(exc, context)`` never raises; unknown errors fall back to a generic
diagnosis that still includes the exception type and message.
"""

from __future__ import annotations

import errno
import re
from dataclasses import dataclass, field
from typing import List, Optional


# Contexts describe WHAT the app was doing when the error happened.
CTX_CONNECT = "connect"
CTX_REFRESH = "refresh"
CTX_RECORDINGS = "recordings"
CTX_DOWNLOAD = "download"
CTX_PLAYBACK = "playback"
CTX_LIVE = "live"
CTX_EXTERNAL_PLAYER = "external_player"
CTX_STORAGE = "storage"
CTX_CREDENTIALS = "credentials"


class CloudLoginError(RuntimeError):
    """
    The RTSP (live video) login succeeded, but the camera's management/SD-card
    API (pytapo) login failed. ``detail`` holds the original library message.
    """

    def __init__(self, detail: str):
        super().__init__(f"Cloud/SD card authentication failed: {detail}")
        self.detail = detail


@dataclass(frozen=True)
class Diagnosis:
    code: str
    title: str
    summary: str
    causes: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    technical: str = ""

    def short(self) -> str:
        """One compact block for small status labels."""
        return f"[{self.code}] {self.title}\n{self.summary}"

    def body(self) -> str:
        """Full explanation for dialogs."""
        parts = [self.summary]
        if self.causes:
            parts.append(
                "Most likely causes:\n" + "\n".join(f"  • {c}" for c in self.causes)
            )
        if self.steps:
            parts.append(
                "How to fix it:\n"
                + "\n".join(f"  {i}. {s}" for i, s in enumerate(self.steps, 1))
            )
        if self.technical:
            parts.append(f"Technical details (for support):\n{self.technical}")
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _tech(exc: BaseException) -> str:
    msg = str(exc).strip()
    name = type(exc).__name__
    return f"{name}: {msg}" if msg else name


def _root_oserror(exc: BaseException) -> Optional[OSError]:
    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, OSError) and (
            cur.errno is not None or getattr(cur, "winerror", None) is not None
        ):
            return cur
        cur = cur.__cause__ or cur.__context__
    return None


def _winerr(exc: BaseException) -> Optional[int]:
    os_err = _root_oserror(exc)
    if os_err is None:
        return None
    return getattr(os_err, "winerror", None) or os_err.errno


_NETWORK_HINTS = (
    "max retries exceeded",
    "connection refused",
    "connection aborted",
    "connection reset",
    "timed out",
    "timeout",
    "no route to host",
    "network is unreachable",
    "name or service not known",
    "getaddrinfo failed",
    "sslerror",
    "read timed out",
    "remotedisconnected",
)

_NETWORK_CHECKLIST = [
    "Make sure the camera is powered on and the Tapo app can see it online.",
    "Make sure this PC is on the same network (same router / Wi-Fi) as the camera. "
    "Guest Wi-Fi, VPNs and 'AP isolation' settings block this.",
    "Check the camera's current IP address in the Tapo app "
    "(Camera Settings > Device Info) — routers can change it after a reboot. "
    "Giving the camera a fixed IP in your router prevents this.",
    "Temporarily disable VPN software and allow Tapo-Viewer through Windows Firewall.",
]


# ---------------------------------------------------------------------------
# connection (RTSP + management API)
# ---------------------------------------------------------------------------
def _diagnose_connect(exc: BaseException, text: str, low: str) -> Optional[Diagnosis]:
    tech = _tech(exc)

    # --- Stage 2: management / SD card API ---
    if isinstance(exc, CloudLoginError) or "cloud/sd card authentication failed" in low:
        detail = getattr(exc, "detail", text)
        dlow = detail.lower()
        ok_note = (
            "Good news: the live-video (RTSP) login already worked, so your IP address "
            "and Camera Account are correct. Only the second login, used for the SD card "
            "and recordings, was refused."
        )

        if "temporary suspension" in dlow or "device_blocked" in dlow or "-40404" in dlow:
            secs = re.search(r"(\d+)\s*seconds", detail)
            wait = f" about {secs.group(1)} seconds" if secs else " several minutes"
            return Diagnosis(
                "ERR_CAMERA_LOCKED",
                "Camera Temporarily Locked",
                "The camera has blocked further logins because of too many failed "
                f"attempts. Try again in{wait}.",
                causes=[
                    "Several wrong-password attempts in a row (the camera locks "
                    "itself as protection).",
                ],
                steps=[
                    f"Wait{wait}, without pressing Connect again (each attempt restarts the timer).",
                    "Re-check the TP-Link/Tapo cloud password by signing in to the Tapo app.",
                    "Then reconnect with 'Different Cloud Password' ticked and the correct password.",
                ],
                technical=tech,
            )

        if "invalid authentication data" in dlow:
            return Diagnosis(
                "ERR_CLOUD_AUTH",
                "SD Card Login Rejected",
                ok_note
                + "\n\nThe camera refused the second login (needed to list and "
                "download SD card recordings).",
                causes=[
                    "Most common: the camera's management API does not accept the local "
                    "'Camera Account'. It needs the account username 'admin' together with "
                    "your TP-Link / Tapo cloud (app) password, which is usually different "
                    "from the Camera Account password.",
                    "The TP-Link/Tapo cloud password typed (or saved) is wrong or was "
                    "changed recently.",
                    "Your cloud password contains special characters that were "
                    "mistyped (try typing it into Notepad first and copy/paste it).",
                    "Recent camera firmware changed how third-party login works "
                    "(it now relies on the cloud password).",
                ],
                steps=[
                    "On the login screen, tick 'Different Cloud Password'.",
                    "Enter the password you use to sign in to the Tapo app "
                    "(your TP-Link account password, NOT the Camera Account password).",
                    "Click Connect Camera again.",
                    "Still failing? Sign in to the Tapo app with that same password to "
                    "confirm it is correct, and check the camera has the latest firmware.",
                    "Avoid repeated retries: after ~10 wrong attempts the camera locks "
                    "itself for a few minutes.",
                ],
                technical=tech,
            )

        if any(h in dlow for h in _NETWORK_HINTS):
            return Diagnosis(
                "ERR_CLOUD_UNREACHABLE",
                "Camera Management Port Not Reachable",
                ok_note.replace("Only the second login", "The second connection")
                + "\n\nThe camera did not answer on its secure control port (443), "
                "which is used for SD card access.",
                causes=[
                    "Windows Firewall, antivirus or a router rule is blocking port 443 "
                    "to the camera.",
                    "The camera is busy or low on Wi-Fi signal and dropped the connection.",
                ],
                steps=[
                    "Use 'Quick Connection Test' on the login screen — port 443 should show OPEN.",
                    "Allow Tapo-Viewer through Windows Firewall / your antivirus.",
                    "Move the camera closer to the router or restart the camera, then retry.",
                ],
                technical=tech,
            )

        return Diagnosis(
            "ERR_CLOUD_UNKNOWN",
            "SD Card Login Failed",
            ok_note + "\n\nThe camera's management API returned an unexpected answer.",
            causes=[
                "Unsupported or very new camera firmware.",
                "The camera is busy or restarting.",
            ],
            steps=[
                "Wait a minute and try again.",
                "Try ticking 'Different Cloud Password' and enter your Tapo app password.",
                "If it keeps failing, copy the technical details below when asking for help.",
            ],
            technical=tech,
        )

    # --- Stage 1: network / RTSP ---
    if isinstance(exc, TimeoutError) and "port 554" in low:
        return Diagnosis(
            "ERR_CAMERA_TIMEOUT",
            "Camera Did Not Respond",
            "The camera did not answer on the live-video port (554) within 3 seconds.",
            causes=[
                "Wrong IP address, or the camera's IP address changed.",
                "Camera is offline, asleep, or on a different network.",
            ],
            steps=_NETWORK_CHECKLIST,
            technical=tech,
        )

    if isinstance(exc, ConnectionError) and "cannot reach camera" in low:
        code = _winerr(exc)
        if code in (11001, errno.ENOENT) or "getaddrinfo" in low or "name or service" in low:
            return Diagnosis(
                "ERR_BAD_HOST",
                "Invalid Camera Address",
                "The text entered as the camera address is not a valid IP address or "
                "hostname.",
                causes=["Typo in the IP address (expected format: 192.168.0.103)."],
                steps=[
                    "Type the IPv4 address exactly as shown in the Tapo app "
                    "(Camera Settings > Device Info > IP Address).",
                    "Do not include 'http://', 'rtsp://' or a port number.",
                ],
                technical=tech,
            )
        if code in (10061, errno.ECONNREFUSED):
            return Diagnosis(
                "ERR_RTSP_REFUSED",
                "Camera Refused the Connection",
                "The device at this address answered but is not accepting live-video "
                "connections on port 554.",
                causes=[
                    "The IP belongs to a different device (router, PC, another camera).",
                    "The Camera Account has not been created yet — RTSP only turns on "
                    "after you create one in the Tapo app.",
                    "Camera firmware is still starting up after a reboot.",
                ],
                steps=[
                    "Confirm the IP in the Tapo app.",
                    "In the Tapo app: Camera Settings > Advanced Settings > Camera Account — "
                    "create a username/password and save.",
                    "Wait 30–60 seconds after the camera reboots, then retry.",
                ],
                technical=tech,
            )
        if code in (10060, errno.ETIMEDOUT):
            return Diagnosis(
                "ERR_CAMERA_TIMEOUT",
                "Camera Did Not Respond",
                "The connection attempt to the camera timed out.",
                causes=["Wrong IP, camera offline, or blocked by a network rule."],
                steps=_NETWORK_CHECKLIST,
                technical=tech,
            )
        return Diagnosis(
            "ERR_CAMERA_UNREACHABLE",
            "Camera Not Reachable",
            "This PC could not open a network connection to the camera.",
            causes=[
                "Camera is offline or the IP address is wrong.",
                "PC and camera are on different networks.",
                "Firewall, VPN or router isolation is blocking traffic.",
            ],
            steps=_NETWORK_CHECKLIST,
            technical=tech,
        )

    if isinstance(exc, PermissionError) or "username or password was rejected" in low:
        return Diagnosis(
            "ERR_RTSP_AUTH",
            "Camera Account Rejected",
            "The camera accepted the connection but rejected the username or password.",
            causes=[
                "You entered your TP-Link / Tapo email login instead of the local "
                "Camera Account.",
                "Typo, extra space, or wrong capital letters in the username/password.",
                "Camera Account password was changed in the Tapo app.",
            ],
            steps=[
                "In the Tapo app open Camera Settings > Advanced Settings > Camera Account.",
                "Re-enter (or reset) the username and password there and save.",
                "Type the same values here. Usernames and passwords are case-sensitive.",
            ],
            technical=tech,
        )

    if "ffprobe is unavailable" in low or "ffprobe could not be started" in low:
        return Diagnosis(
            "ERR_RUNTIME_DEPENDENCY",
            "Installation Incomplete",
            "The FFprobe tool used to verify the camera stream is missing or cannot start.",
            causes=[
                "The vendor\\ffmpeg folder is missing or incomplete.",
                "Antivirus quarantined ffprobe.exe.",
            ],
            steps=[
                "Re-download and reinstall Tapo-Viewer.",
                "Check your antivirus quarantine/history and restore ffprobe.exe.",
            ],
            technical=tech,
        )

    if isinstance(exc, TimeoutError) and "authentication test" in low:
        return Diagnosis(
            "ERR_RTSP_PROBE_TIMEOUT",
            "Camera Too Slow to Answer",
            "The port is open, but the camera did not start streaming within 8 seconds.",
            causes=[
                "Weak Wi-Fi signal or an overloaded camera "
                "(too many viewers connected at once).",
            ],
            steps=[
                "Close the Tapo app and other viewers (VLC, Home Assistant, etc.) and retry.",
                "Improve Wi-Fi signal or restart the camera.",
            ],
            technical=tech,
        )

    if "no usable video stream" in low:
        return Diagnosis(
            "ERR_NO_VIDEO",
            "No Video From Camera",
            "The camera logged in successfully but did not send a video stream.",
            causes=["Camera Privacy Mode is on, or the camera is still starting."],
            steps=[
                "Turn off Privacy Mode in the Tapo app.",
                "Wait a minute and retry.",
            ],
            technical=tech,
        )

    if "rtsp authentication or stream validation failed" in low:
        return Diagnosis(
            "ERR_RTSP_VALIDATION",
            "Live Stream Check Failed",
            "The camera's live stream could not be verified.",
            causes=[
                "RTSP is blocked, the stream path is not supported by this model, "
                "or too many clients are connected.",
            ],
            steps=[
                "Confirm a Camera Account exists in the Tapo app.",
                "Close other apps that are watching the camera, then retry.",
            ],
            technical=tech,
        )

    if isinstance(exc, ValueError):
        return Diagnosis(
            "ERR_INPUT",
            "Missing Information",
            text or "A required field is empty.",
            steps=["Fill in the highlighted fields and try again."],
            technical=tech,
        )
    return None


# ---------------------------------------------------------------------------
# SD card listing / refresh
# ---------------------------------------------------------------------------
def _diagnose_sd(exc: BaseException, text: str, low: str, ctx: str) -> Optional[Diagnosis]:
    tech = _tech(exc)
    code = "ERR_REFRESH_FAILED" if ctx == CTX_REFRESH else "ERR_RECORDINGS_FAILED"

    if "cloud authentication required" in low:
        return Diagnosis(
            "ERR_SD_NOT_AUTHENTICATED",
            "SD Card Access Not Available",
            "This session is not logged in to the camera's SD card service, so "
            "recordings cannot be listed or downloaded.",
            steps=[
                "Click Disconnect and connect again.",
                "Tick 'Different Cloud Password' and enter your Tapo app password.",
            ],
            technical=tech,
        )
    if "sd_card_unplugged" in low or "storage_not_exist" in low or "-52409" in low or "-71114" in low:
        return Diagnosis(
            "ERR_NO_SD_CARD",
            "No SD Card Found",
            "The camera reports that no MicroSD card is installed or readable.",
            causes=["Card missing, loose, or corrupted (not formatted by the camera)."],
            steps=[
                "Check the card is inserted fully.",
                "In the Tapo app open Camera Settings > Storage and format the card.",
            ],
            technical=tech,
        )
    if "sd_loading" in low or "-71115" in low:
        return Diagnosis(
            "ERR_SD_LOADING",
            "SD Card Still Loading",
            "The camera is still mounting/indexing its SD card.",
            steps=["Wait 30–60 seconds, then press 'Refresh SD'."],
            technical=tech,
        )
    if "too_many" in low or "-52407" in low or "-52419" in low or "-71101" in low:
        return Diagnosis(
            "ERR_CAMERA_BUSY",
            "Camera Has Too Many Connections",
            "The camera is already serving the maximum number of viewers/sessions.",
            steps=[
                "Close the Tapo app, VLC, and any other app using this camera.",
                "Wait a minute, then press 'Refresh SD'.",
            ],
            technical=tech,
        )
    if "-40401" in low or "invalid stok" in low or "session" in low and "expired" in low:
        return Diagnosis(
            "ERR_SESSION_EXPIRED",
            "Camera Session Expired",
            "The camera ended our login session (it times out after inactivity "
            "or if the camera restarted).",
            steps=["Click Disconnect, then connect again."],
            technical=tech,
        )
    if "invalid authentication data" in low or "temporary suspension" in low:
        return _diagnose_connect(CloudLoginError(text), text, low)
    if any(h in low for h in _NETWORK_HINTS):
        return Diagnosis(
            code,
            "Lost Connection to Camera",
            "The camera stopped answering while reading the SD card.",
            causes=["Camera went offline, rebooted, or Wi-Fi dropped."],
            steps=_NETWORK_CHECKLIST + ["Then press 'Refresh SD'."],
            technical=tech,
        )
    return None


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------
def _diagnose_download(exc: BaseException, text: str, low: str) -> Optional[Diagnosis]:
    tech = _tech(exc)

    if "download cancelled by user" in low:
        return Diagnosis(
            "INFO_DOWNLOAD_CANCELLED",
            "Download Cancelled",
            "You cancelled the download. Any partial file was not kept as a finished clip.",
            technical=tech,
        )
    if "was not found or is empty" in low:
        return Diagnosis(
            "ERR_DOWNLOAD_EMPTY",
            "Clip Could Not Be Saved",
            "The download ended, but no usable video file was produced.",
            causes=[
                "The clip is still being recorded by the camera.",
                "The camera overwrote this segment (SD card is full and looping).",
                "Connection dropped mid-transfer.",
            ],
            steps=[
                "Wait for the recording to finish, press 'Refresh SD', and retry.",
                "Try again closer to the router / with a stronger Wi-Fi signal.",
                "Check the output folder has free disk space and write permission.",
            ],
            technical=tech,
        )
    os_err = _root_oserror(exc)
    if os_err is not None and os_err.errno in (errno.ENOSPC,):
        return Diagnosis(
            "ERR_DISK_FULL",
            "Disk Is Full",
            "There is not enough free space on the drive to save this clip.",
            steps=[
                "Free up disk space or choose another folder using 'Change Folder'.",
            ],
            technical=tech,
        )
    if os_err is not None and (os_err.errno in (errno.EACCES, errno.EPERM) or isinstance(exc, PermissionError)):
        return Diagnosis(
            "ERR_STORAGE_PERM",
            "Cannot Write to Folder",
            "Windows denied permission to save files into the recordings folder.",
            causes=[
                "Folder is protected (Program Files, OneDrive lock, antivirus 'ransomware protection').",
                "The file is open in another program.",
            ],
            steps=[
                "Choose a folder you own, e.g. Documents\\Tapo, using 'Change Folder'.",
                "Close any player that has the same file open.",
            ],
            technical=tech,
        )
    if "ffmpeg" in low and ("became unavailable" in low or "not found" in low):
        return Diagnosis(
            "ERR_RUNTIME_DEPENDENCY",
            "FFmpeg Missing",
            "FFmpeg is needed to convert clips to MP4 and could not be started.",
            steps=["Reinstall Tapo-Viewer or restore vendor\\ffmpeg."],
            technical=tech,
        )
    if "invalid authentication data" in low or "temporary suspension" in low:
        return _diagnose_connect(CloudLoginError(text), text, low)
    d = _diagnose_sd(exc, text, low, CTX_DOWNLOAD)
    if d:
        return d
    if any(h in low for h in _NETWORK_HINTS):
        return Diagnosis(
            "ERR_DOWNLOAD_NETWORK",
            "Download Interrupted",
            "The connection to the camera dropped during the download.",
            causes=["Weak Wi-Fi, camera rebooted, or another device took the camera's bandwidth."],
            steps=_NETWORK_CHECKLIST + ["Then start the download again."],
            technical=tech,
        )
    return None


# ---------------------------------------------------------------------------
# players
# ---------------------------------------------------------------------------
def _diagnose_player(exc: BaseException, text: str, low: str, ctx: str) -> Optional[Diagnosis]:
    tech = _tech(exc)

    if "err_not_connected" in low or "not connected" in low:
        return Diagnosis(
            "ERR_NOT_CONNECTED",
            "Camera Not Connected",
            "There is no active connection to the camera.",
            steps=["Click Connect Camera on the login screen first."],
            technical=tech,
        )
    if "libvlc" in low and ("failed to initialize" in low or "not found" in low or "runtime was not found" in low):
        return Diagnosis(
            "ERR_VLC_MISSING",
            "Built-in Video Engine Unavailable",
            "The embedded video player (LibVLC) could not start.",
            causes=[
                "vendor\\vlc folder is missing/incomplete or quarantined by antivirus.",
                "32-bit/64-bit mismatch with another VLC install.",
            ],
            steps=[
                "Reinstall Tapo-Viewer so the vendor\\vlc folder is restored.",
                "Meanwhile use 'Open in External Player' for live view.",
            ],
            technical=tech,
        )
    if "rejected the rtsp stream" in low:
        return Diagnosis(
            "ERR_LIVE_REJECTED",
            "Live Stream Could Not Start",
            "The video engine refused to open the camera's live stream.",
            causes=[
                "Password contains characters that break the stream address.",
                "Camera is at its maximum number of viewers.",
            ],
            steps=[
                "Close other apps viewing the camera, then reconnect.",
                "Try the SD (lower) stream quality, or an external player.",
            ],
            technical=tech,
        )
    if "has not finished initializing" in low:
        return Diagnosis(
            "ERR_PLAYER_STARTING",
            "Player Still Starting",
            "The embedded player is not ready yet.",
            steps=["Wait a couple of seconds and try again."],
            technical=tech,
        )
    if "could not open the selected file" in low:
        return Diagnosis(
            "ERR_PLAYBACK_OPEN",
            "Clip Cannot Be Played",
            "The video engine could not open the downloaded file.",
            causes=[
                "The download was incomplete or the file is corrupted.",
                "The codec is not supported.",
            ],
            steps=[
                "Delete the clip from the recordings folder and download it again.",
                "Open the file in an external player.",
            ],
            technical=tech,
        )
    if isinstance(exc, FileNotFoundError) or "file not found" in low:
        return Diagnosis(
            "ERR_FILE_MISSING",
            "Clip File Not Found",
            "The video file no longer exists at its saved location.",
            causes=["It was moved, renamed or deleted outside the app."],
            steps=["Download the clip again from the camera."],
            technical=tech,
        )
    if "no compatible external player" in low:
        return Diagnosis(
            "ERR_NO_PLAYER",
            "No External Player Found",
            "No VLC, FFplay, mpv or PotPlayer installation could be located.",
            steps=[
                "Install VLC (videolan.org) or pick a player in the player menu "
                "(Custom...).",
            ],
            technical=tech,
        )
    return None


# ---------------------------------------------------------------------------
# credentials / storage
# ---------------------------------------------------------------------------
def _diagnose_misc(exc: BaseException, text: str, low: str, ctx: str) -> Optional[Diagnosis]:
    tech = _tech(exc)
    if ctx == CTX_CREDENTIALS or "credential manager" in low:
        return Diagnosis(
            "ERR_CREDENTIAL_STORE",
            "Windows Credential Manager Problem",
            text or "Saved camera passwords could not be read or written.",
            causes=[
                "Credential Manager service is disabled or restricted by policy.",
                "A previously saved entry is damaged.",
            ],
            steps=[
                "Untick 'Remember credentials on this PC' to continue without saving.",
                "To reset: Windows Start > Credential Manager > Windows Credentials > "
                "remove entries named after Tapo-Viewer.",
            ],
            technical=tech,
        )
    if ctx == CTX_STORAGE:
        os_err = _root_oserror(exc)
        reason = os_err.strerror if os_err and os_err.strerror else str(exc)
        return Diagnosis(
            "ERR_STORAGE_PERM",
            "Cannot Use That Folder",
            f"The app could not write a test file in the chosen folder ({reason}).",
            causes=[
                "Read-only or protected location (e.g. Program Files, network drive offline).",
                "Drive is full or disconnected.",
            ],
            steps=["Choose a folder you own, such as Documents\\Tapo."],
            technical=tech,
        )
    return None


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------
def diagnose(exc: BaseException | str, context: str = CTX_CONNECT) -> Diagnosis:
    """Translate any exception (or message string) into a descriptive Diagnosis."""
    if isinstance(exc, str):
        exc = RuntimeError(exc)

    text = str(exc).strip()
    low = text.lower()
    result: Optional[Diagnosis] = None

    try:
        if context == CTX_CONNECT:
            result = _diagnose_connect(exc, text, low)
        elif context in (CTX_REFRESH, CTX_RECORDINGS):
            result = _diagnose_sd(exc, text, low, context)
        elif context == CTX_DOWNLOAD:
            result = _diagnose_download(exc, text, low)
        elif context in (CTX_PLAYBACK, CTX_LIVE, CTX_EXTERNAL_PLAYER):
            result = _diagnose_player(exc, text, low, context)

        if result is None:
            result = _diagnose_misc(exc, text, low, context)
        if result is None and context != CTX_CONNECT:
            # errors can be network/auth related in any context
            result = _diagnose_sd(exc, text, low, context)
    except Exception:  # diagnosis must never crash the UI
        result = None

    if result is not None:
        return result

    titles = {
        CTX_CONNECT: ("ERR_CONNECT_FAILED", "Could Not Connect to Camera"),
        CTX_REFRESH: ("ERR_REFRESH_FAILED", "Could Not Refresh SD Card"),
        CTX_RECORDINGS: ("ERR_RECORDINGS_FAILED", "Could Not Load Recordings"),
        CTX_DOWNLOAD: ("ERR_DOWNLOAD_FAILED", "Download Failed"),
        CTX_PLAYBACK: ("ERR_PLAYBACK", "Playback Failed"),
        CTX_LIVE: ("ERR_EMBEDDED_PLAYER", "Live Stream Failed"),
        CTX_EXTERNAL_PLAYER: ("ERR_EXTERNAL_PLAYER", "External Player Failed"),
        CTX_STORAGE: ("ERR_STORAGE_PERM", "Folder Not Usable"),
        CTX_CREDENTIALS: ("ERR_CREDENTIAL_STORE", "Credential Storage Error"),
    }
    code, title = titles.get(context, ("ERR_UNKNOWN", "Unexpected Error"))
    return Diagnosis(
        code,
        title,
        "Something unexpected happened and the app could not identify the exact cause.",
        causes=["A temporary network hiccup or an unsupported camera response."],
        steps=[
            "Try the action again.",
            "If it keeps happening, disconnect and reconnect to the camera.",
            "Report the technical details below if you ask for help.",
        ],
        technical=_tech(exc),
    )
