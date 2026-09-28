import asyncio
import datetime
import os
import socket
import subprocess
import threading
from typing import Callable, Optional, List, Dict, Any
from pytapo import Tapo
from pytapo.media_stream.downloader import Downloader


class CameraBackend:
    def __init__(self):
        self.tapo: Optional[Tapo] = None
        self.host: str = ""
        self.username: str = ""
        self.password: str = ""
        self.cloud_password: str = ""
        self.time_correction: int = 0
        self.device_info: Dict[str, Any] = {}
        
        # Dual connection states
        self.is_rtsp_connected: bool = False
        self.is_cloud_connected: bool = False

        self._cancel_download_event = threading.Event()
        self._live_process: Optional[subprocess.Popen] = None

    # =========================================================================
    # TIER 1: RTSP FEED (Camera Account)
    # =========================================================================
    def test_and_connect_rtsp(self, host: str, username: str, password: str) -> bool:
        """
        Verify that the camera is reachable and the RTSP port 554 is accepting credentials.
        """
        self.host = host.strip()
        self.username = username.strip()
        self.password = password

        # 1. Quick socket probe
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            res = s.connect_ex((self.host, 554))
            s.close()
            if res != 0:
                raise ConnectionError(f"RTSP Port 554 is closed or unreachable on {self.host}")
        except Exception as e:
            raise ConnectionError(f"Cannot reach camera on port 554: {e}")

        # 2. Probe with ffprobe to verify credentials
        rtsp_url = self.get_rtsp_url(stream_num=1)
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-show_entries", "stream=codec_type,width,height",
                "-of", "csv=p=0"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            if result.returncode != 0:
                # Check for 401 Unauthorized
                err_text = result.stderr or result.stdout
                if "401" in err_text or "Unauthorized" in err_text:
                    raise PermissionError("Camera Account Username or Password incorrect (401 Unauthorized).")
                else:
                    raise RuntimeError(f"RTSP stream check failed: {err_text.strip() or 'Unknown error'}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("Camera timed out during RTSP handshake.")
        except (PermissionError, ConnectionError):
            raise
        except Exception as e:
            # If ffprobe is not installed, socket was already open, allow proceeding
            pass

        self.is_rtsp_connected = True
        return True

    def get_rtsp_url(self, stream_num: int = 1) -> str:
        """
        Construct RTSP stream URL for live viewing.
        stream1 = 1080p HD, stream2 = 360p SD
        """
        return f"rtsp://{self.username}:{self.password}@{self.host}:554/stream{stream_num}"

    def get_available_players(self) -> Dict[str, str]:
        """
        Detects installed media players capable of streaming live RTSP feeds.
        """
        import shutil
        players = {}

        # 1. mpv.net (Modern, fast, hardware-accelerated RTSP player)
        mpvnet_candidates = [
            r"C:\Program Files\mpv.net\mpvnet.exe",
            r"C:\Program Files (x86)\mpv.net\mpvnet.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\mpv.net\mpvnet.exe")
        ]
        for p in mpvnet_candidates:
            if os.path.exists(p):
                players["mpv.net"] = p
                break

        # 2. PotPlayer
        pot_candidates = [
            r"C:\Program Files\DAUM\PotPlayer\PotPlayer64.exe",
            r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe",
            r"C:\Program Files (x86)\DAUM\PotPlayer\PotPlayer.exe",
            r"C:\Program Files (x86)\DAUM\PotPlayer\PotPlayerMini.exe",
            r"D:\Software\PotPlayer\PotPlayer64.exe"
        ]
        for p in pot_candidates:
            if os.path.exists(p):
                players["PotPlayer"] = p
                break

        # 3. VLC
        vlc_candidates = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
        ]
        for p in vlc_candidates:
            if os.path.exists(p):
                players["VLC"] = p
                break
        if "VLC" not in players and shutil.which("vlc"):
            players["VLC"] = shutil.which("vlc")

        # 4. Standard mpv
        if shutil.which("mpv"):
            players["mpv"] = shutil.which("mpv")

        # 5. FFplay (Built-in FFmpeg Player)
        ffplay_exe = shutil.which("ffplay")
        if ffplay_exe:
            players["FFplay (Built-in)"] = ffplay_exe

        # 6. Windows Default Association
        players["System Default (.m3u)"] = "default"

        return players

    def launch_live_stream_player(self, player_choice: str = "auto", custom_path: Optional[str] = None) -> Optional[subprocess.Popen]:
        """
        Launch the camera's live 1080p stream using the user's selected player.
        Supports mpv.net, PotPlayer, VLC, FFplay, or custom player.
        """
        if not self.is_rtsp_connected:
            raise RuntimeError("[ERR_NOT_CONNECTED] Camera RTSP stream is not connected.")

        rtsp_url = self.get_rtsp_url(stream_num=1)
        available = self.get_available_players()

        target_exe = None
        if custom_path and os.path.exists(custom_path):
            target_exe = custom_path
        elif player_choice in available and available[player_choice] != "default":
            target_exe = available[player_choice]
        elif player_choice == "auto":
            # Auto-priority: mpv.net -> PotPlayer -> VLC -> FFplay
            for preferred in ["mpv.net", "PotPlayer", "VLC", "FFplay (Built-in)"]:
                if preferred in available:
                    target_exe = available[preferred]
                    break

        if target_exe and os.path.exists(target_exe):
            exe_lower = target_exe.lower()
            if "vlc" in exe_lower:
                cmd = [target_exe, rtsp_url, "--network-caching=1000", f"--meta-title=Tapo Live Feed (1080p) - {self.host}"]
            elif "potplayer" in exe_lower:
                cmd = [target_exe, rtsp_url]
            elif "mpv" in exe_lower:
                cmd = [target_exe, rtsp_url, f"--title=Tapo Live Feed (1080p) - {self.host}"]
            elif "ffplay" in exe_lower:
                cmd = [target_exe, "-rtsp_transport", "tcp", "-window_title", f"Tapo Live Feed (1080p) - {self.host}", "-x", "1280", "-y", "720", rtsp_url]
            else:
                cmd = [target_exe, rtsp_url]

            self._live_process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if "ffplay" in exe_lower else 0
            )
            return self._live_process

        # Fallback to .m3u playlist
        import tempfile
        try:
            m3u_path = os.path.join(tempfile.gettempdir(), "tapo_camera_live.m3u")
            with open(m3u_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"#EXTINF:-1,Tapo Camera Live Feed (1080p) [{self.host}]\n")
                f.write(f"{rtsp_url}\n")
            os.startfile(m3u_path)
            return None
        except Exception as e:
            raise RuntimeError(f"Could not launch media player: {e}")

    # =========================================================================
    # TIER 2: CLOUD MANAGEMENT (SD Card Search & Downloader)
    # =========================================================================
    def connect(
        self,
        host: str,
        username: str,
        password: str,
        cloud_password: Optional[str] = None,
        cloud_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Unified connection method. Connects both RTSP live stream and SD card management.
        If cloud_password is not specified, uses the camera account password.
        """
        self.host = host.strip()
        self.username = username.strip()
        self.password = password
        self.cloud_password = cloud_password.strip() if cloud_password else password

        # 1. Connect RTSP
        self.test_and_connect_rtsp(self.host, self.username, self.password)

        # 2. Connect SD Card API (PyTapo)
        user_for_cloud = (cloud_email.strip() if cloud_email else self.username) or "admin"
        try:
            self.tapo = Tapo(
                host=self.host,
                user=user_for_cloud,
                password=self.password,
                cloudPassword=self.cloud_password,
                retryStok=True
            )
            self.device_info = self.tapo.getBasicInfo()
            try:
                self.time_correction = self.tapo.getTimeCorrection()
            except Exception:
                self.time_correction = 0
            self.is_cloud_connected = True
            return self.device_info
        except Exception as e:
            self.is_cloud_connected = False
            self.tapo = None
            raise RuntimeError(f"Cloud/SD card authentication failed: {e}")

    def connect_cloud(self, cloud_password: Optional[str] = None, cloud_email: Optional[str] = None, *args, **kwargs) -> Dict[str, Any]:
        """
        Connect cloud management API with flexible parameter handling.
        """
        if args and len(args) >= 2:
            # Shifted call: connect_cloud(host, user, cloud_pass)
            self.host = str(cloud_password).strip()
            self.username = str(cloud_email).strip()
            cloud_password = str(args[0]).strip()

        actual_cloud_pass = (cloud_password.strip() if cloud_password else "") or self.password
        self.cloud_password = actual_cloud_pass
        user_for_cloud = (cloud_email.strip() if cloud_email else self.username) or "admin"

        try:
            self.tapo = Tapo(
                host=self.host,
                user=user_for_cloud,
                password=self.password,
                cloudPassword=self.cloud_password,
                retryStok=True
            )
            self.device_info = self.tapo.getBasicInfo()
            try:
                self.time_correction = self.tapo.getTimeCorrection()
            except Exception:
                self.time_correction = 0

            self.is_cloud_connected = True
            return self.device_info
        except Exception as e:
            self.is_cloud_connected = False
            self.tapo = None
            raise

    def get_camera_details(self) -> Dict[str, Any]:
        return {
            "device_info": self.device_info,
            "time_correction": self.time_correction,
            "is_rtsp_connected": self.is_rtsp_connected,
            "is_cloud_connected": self.is_cloud_connected,
        }

    def disconnect(self):
        self.is_rtsp_connected = False
        self.is_cloud_connected = False
        self.tapo = None
        self.device_info = {}
        if self._live_process and self._live_process.poll() is None:
            try:
                self._live_process.terminate()
            except Exception:
                pass

    # =========================================================================
    # SD CARD RECORDINGS (Requires Cloud Connection)
    # =========================================================================
    def get_dates_with_recordings(self) -> List[str]:
        if not self.is_cloud_connected or not self.tapo:
            raise RuntimeError("Cloud authentication required for SD card access.")

        try:
            today_str = datetime.date.today().strftime("%Y%m%d")
            raw_dates = self.tapo.getRecordingsList(start_date="20200101", end_date=today_str)
            dates = []
            if isinstance(raw_dates, list):
                for item in raw_dates:
                    if isinstance(item, dict):
                        inner = next(iter(item.values())) if len(item) == 1 and isinstance(next(iter(item.values())), dict) else item
                        d = inner.get("date") or inner.get("search_date") or item.get("date")
                    else:
                        d = str(item)
                    if d and len(str(d)) == 8:
                        d_str = str(d)
                        formatted = f"{d_str[0:4]}-{d_str[4:6]}-{d_str[6:8]}"
                        if formatted not in dates:
                            dates.append(formatted)
            dates.sort(reverse=True)
            return dates
        except Exception:
            today_fmt = datetime.date.today().strftime("%Y-%m-%d")
            return [today_fmt]

    def get_recordings(self, date_str: str, output_dir: str) -> List[Dict[str, Any]]:
        if not self.is_cloud_connected or not self.tapo:
            raise RuntimeError("Cloud authentication required for SD card access.")

        clean_date = date_str.replace("-", "").strip()
        raw_results = self.tapo.getRecordings(clean_date)

        recordings = []
        if not raw_results or not isinstance(raw_results, list):
            return recordings

        for idx, item in enumerate(raw_results):
            try:
                # Unwrap nested dict like {'search_video_results_1': {'startTime': 1790534157, 'endTime': 1790534235, 'vedio_type': 2}}
                if isinstance(item, dict) and len(item) == 1:
                    inner_val = next(iter(item.values()))
                    data = inner_val if isinstance(inner_val, dict) else item
                else:
                    data = item

                start_ts = int(data.get("startTime") if data.get("startTime") is not None else data.get("start_time", 0))
                end_ts = int(data.get("endTime") if data.get("endTime") is not None else data.get("end_time", 0))

                if start_ts <= 0 or end_ts <= 0:
                    continue

                duration_sec = max(0, end_ts - start_ts)
                start_dt = datetime.datetime.fromtimestamp(start_ts)
                end_dt = datetime.datetime.fromtimestamp(end_ts)

                start_str = start_dt.strftime("%H:%M:%S")
                end_str = end_dt.strftime("%H:%M:%S")

                raw_type = str(data.get("vedio_type") or data.get("video_type") or data.get("type", "1"))
                is_motion = raw_type != "1"
                type_label = "Motion Event" if is_motion else "Continuous"

                base_name = f"tapo_{clean_date}_{start_dt.strftime('%H%M%S')}_{end_dt.strftime('%H%M%S')}"
                mp4_file = f"{base_name}.mp4"
                ts_file = f"{base_name}.ts"
                mp4_path = os.path.join(output_dir, mp4_file)
                ts_path = os.path.join(output_dir, ts_file)

                if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 1024:
                    is_downloaded = True
                    file_name = mp4_file
                    full_path = mp4_path
                elif os.path.exists(ts_path) and os.path.getsize(ts_path) > 1024:
                    is_downloaded = True
                    file_name = ts_file
                    full_path = ts_path
                else:
                    is_downloaded = False
                    file_name = mp4_file
                    full_path = mp4_path

                recordings.append({
                    "id": idx,
                    "date": date_str,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "start_str": start_str,
                    "end_str": end_str,
                    "duration_sec": duration_sec,
                    "duration_str": self._format_duration(duration_sec),
                    "is_motion": is_motion,
                    "type_label": type_label,
                    "file_name": file_name,
                    "file_path": full_path,
                    "is_downloaded": is_downloaded,
                    "raw": data
                })
            except Exception as e:
                print(f"Error parsing recording item {item}: {e}")

        recordings.sort(key=lambda r: r["start_ts"])
        return recordings

    def _format_duration(self, seconds: int) -> str:
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def cancel_download(self):
        self._cancel_download_event.set()

    def download_clip_sync(
        self,
        recording: Dict[str, Any],
        output_dir: str,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> str:
        self._cancel_download_event.clear()
        os.makedirs(output_dir, exist_ok=True)
        norm_output_dir = os.path.abspath(output_dir)
        if not norm_output_dir.endswith(os.sep):
            norm_output_dir += os.sep

        target_file_name = recording["file_name"]
        if not target_file_name.lower().endswith(".mp4"):
            base = os.path.splitext(target_file_name)[0]
            target_file_name = f"{base}.mp4"

        final_path = os.path.join(output_dir, target_file_name)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._download_async(
                    recording=recording,
                    output_dir=norm_output_dir,
                    file_name=target_file_name,
                    final_path=final_path,
                    progress_cb=progress_cb
                )
            )
        finally:
            loop.close()

    async def _download_async(
        self,
        recording: Dict[str, Any],
        output_dir: str,
        file_name: str,
        final_path: str,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]]
    ) -> str:
        start_ts = recording["start_ts"]
        end_ts = recording["end_ts"]
        total_duration = recording["duration_sec"]

        downloader = Downloader(
            tapo=self.tapo,
            startTime=start_ts,
            endTime=end_ts,
            timeCorrection=self.time_correction,
            outputDirectory=output_dir,
            fileName=file_name,
            output="mp4",
            method="download",
            window_size=200
        )

        async for status in downloader.download():
            if self._cancel_download_event.is_set():
                if progress_cb:
                    progress_cb({
                        "action": "Cancelled",
                        "percent": 0,
                        "file_name": file_name,
                        "status_text": "Download cancelled by user"
                    })
                break

            action = status.get("currentAction", "Downloading")
            progress = status.get("progress", 0)
            total = status.get("total", total_duration)

            percent = 0.0
            if total and total > 0 and progress:
                percent = min(1.0, float(progress) / float(total))

            if action == "Converting":
                status_text = "Remuxing to MP4 (FFmpeg)..."
                percent = 0.95
            elif action == "Recording in progress":
                status_text = "Segment still recording on camera..."
            elif action == "Retrying":
                status_text = "Retrying download connection..."
            elif action == "Skipping":
                status_text = "File already downloaded, skipping."
                percent = 1.0
            else:
                pct_str = f"{int(percent * 100)}%" if percent > 0 else "..."
                status_text = f"Downloading {recording['start_str']} - {recording['end_str']} ({pct_str})"

            if progress_cb:
                progress_cb({
                    "action": action,
                    "percent": percent,
                    "file_name": recording["file_name"],
                    "status_text": status_text,
                    "file_path": final_path
                })

        if os.path.exists(final_path) and os.path.getsize(final_path) > 1024:
            if progress_cb:
                progress_cb({
                    "action": "Finished",
                    "percent": 1.0,
                    "file_name": recording["file_name"],
                    "status_text": f"Completed: {recording['file_name']}",
                    "file_path": final_path
                })
            return final_path

        # Fallback check: Did PyTapo produce a .ts file or .mp4.ts?
        base_name = os.path.splitext(final_path)[0]
        ts_candidates = [f"{base_name}.ts", f"{final_path}.ts"]
        for ts_path in ts_candidates:
            if os.path.exists(ts_path) and os.path.getsize(ts_path) > 1024:
                try:
                    remux_cmd = [
                        "ffmpeg", "-y", "-i", ts_path,
                        "-c:v", "copy", "-c:a", "aac",
                        final_path
                    ]
                    subprocess.run(
                        remux_cmd,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                    )
                    if os.path.exists(final_path) and os.path.getsize(final_path) > 1024:
                        try:
                            os.remove(ts_path)
                        except Exception:
                            pass
                        if progress_cb:
                            progress_cb({
                                "action": "Finished",
                                "percent": 1.0,
                                "file_name": recording["file_name"],
                                "status_text": f"Completed: {recording['file_name']}",
                                "file_path": final_path
                            })
                        return final_path
                except Exception as e:
                    print(f"Fallback remux notice: {e}")
                    return ts_path

        if self._cancel_download_event.is_set():
            raise RuntimeError("Download cancelled by user.")
        else:
            raise RuntimeError(f"Download finished but {recording['file_name']} was not found or is empty.")

    def play_file(self, file_path: str, player_choice: str = "auto", custom_path: Optional[str] = None):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        available = self.get_available_players()
        target_exe = None
        if custom_path and os.path.exists(custom_path):
            target_exe = custom_path
        elif player_choice in available and available[player_choice] != "default":
            target_exe = available[player_choice]
        elif player_choice == "auto":
            for preferred in ["mpv.net", "PotPlayer", "VLC", "FFplay (Built-in)"]:
                if preferred in available:
                    target_exe = available[preferred]
                    break

        if target_exe and os.path.exists(target_exe):
            subprocess.Popen([target_exe, file_path])
        else:
            os.startfile(file_path)
