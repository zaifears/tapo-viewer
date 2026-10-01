from __future__ import annotations

import os
import threading
from typing import Callable, Optional

import customtkinter as ctk
import tkinter as tk

from runtime_paths import prepare_vlc_environment


TAPO_BLUE = "#00A4E4"
TAPO_BLUE_HOVER = "#008BC2"
TAPO_CARD_BG = "#1E2026"
TAPO_PANEL_BG = "#08090B"
TAPO_MUTED = "#8A8D98"
TAPO_GREEN = "#2ECC71"
TAPO_AMBER = "#FFA000"
TAPO_RED = "#E74C3C"
FONT_FAMILY = "Segoe UI"


class EmbeddedVLCPlayer(ctk.CTkFrame):
    """
    Embedded LibVLC video player for CustomTkinter.

    Windows uses MediaPlayer.set_hwnd() with the native Tk window handle.
    Includes full audio output controls, first-click responsive buttons,
    interactive pause/resume toggling, and return-to-live navigation.
    """

    def __init__(
        self,
        master,
        status_callback: Optional[Callable[[str, str], None]] = None,
        external_callback: Optional[Callable[[], None]] = None,
        live_callback: Optional[Callable[[], None]] = None,
        quality_callback: Optional[Callable[[str], None]] = None,
        initial_volume: int = 80,
        initially_muted: bool = False,
        initial_quality: str = "HD",
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=TAPO_CARD_BG,
            corner_radius=12,
            **kwargs,
        )

        self.status_callback = status_callback
        self.external_callback = external_callback
        self.live_callback = live_callback
        self.quality_callback = quality_callback
        self._current_quality = initial_quality

        self._vlc = None
        self._instance = None
        self._player = None
        self._events = None

        self._current_url: Optional[str] = None
        self._playing_file: Optional[str] = None
        self._current_mode: str = "live"  # "live" or "replay"
        self._is_playing = False
        self._is_paused = False
        self._is_changing_media = False
        self._muted = bool(initially_muted)
        self._volume = max(0, min(100, int(initial_volume)))
        self._initialization_error: Optional[str] = None
        self._operation_lock = threading.RLock()

        self._build_ui()

        # Initialization is postponed until Tk has created window handles.
        self.after(100, self._initialize_vlc)

    def _build_ui(self) -> None:
        # Header bar: Title, back to live button, status
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=(6, 4))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")

        self.live_dot = ctk.CTkLabel(
            left,
            text="●",
            width=14,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color=TAPO_MUTED,
        )
        self.live_dot.pack(side="left")

        self.title_label = ctk.CTkLabel(
            left,
            text="Live Camera",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=13,
                weight="bold",
            ),
            text_color="#FFFFFF",
        )
        self.title_label.pack(side="left", padx=(4, 6))

        # Back to Live stream button (prominently displayed when playing recorded clips)
        self.btn_back_to_live = ctk.CTkButton(
            left,
            text="🔴 Back to Live Feed",
            width=124,
            height=24,
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self._on_back_to_live_clicked,
        )

        self.status_label = ctk.CTkLabel(
            header,
            text="Player ready",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            text_color=TAPO_MUTED,
        )
        self.status_label.pack(side="right", padx=(0, 4))

        # Video container: 16:9 aspect ratio sizing
        self.video_container = ctk.CTkFrame(
            self,
            fg_color=TAPO_PANEL_BG,
            corner_radius=8,
            height=320,
        )
        self.video_container.pack(
            fill="x",
            expand=False,
            padx=6,
            pady=(0, 6),
        )
        self.video_container.pack_propagate(False)

        # Use native tkinter.Frame to provide a stable native HWND.
        self.video_surface = tk.Frame(
            self.video_container,
            background="#050505",
            highlightthickness=0,
            borderwidth=0,
        )
        self.video_surface.pack(fill="both", expand=True)

        self.placeholder = ctk.CTkLabel(
            self.video_container,
            text="Camera stream is stopped",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=14,
                weight="bold",
            ),
            text_color=TAPO_MUTED,
            fg_color="transparent",
        )
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

        # Dynamically maintain 16:9 aspect ratio on resize
        self.bind("<Configure>", self._on_resize)

        # Controls Toolbar (Play/Pause, Stop, Sound/Mute, Volume, Quality, External)
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=6, pady=(0, 6))

        # Play / Pause toggle button
        self.play_button = ctk.CTkButton(
            controls,
            text="▶ Start Live",
            width=84,
            height=28,
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.toggle_play_pause,
        )
        self.play_button.pack(side="left", padx=(0, 4))

        # Stop button
        self.stop_button = ctk.CTkButton(
            controls,
            text="■ Stop",
            width=54,
            height=28,
            fg_color="#343740",
            hover_color=TAPO_RED,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.stop,
        )
        self.stop_button.pack(side="left", padx=(0, 6))

        # Sound / Mute toggle button
        self.mute_button = ctk.CTkButton(
            controls,
            text="🔇" if self._muted else "🔊",
            width=36,
            height=28,
            fg_color="#552222" if self._muted else "#343740",
            hover_color="#6B2D2D" if self._muted else "#454955",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=13,
            ),
            command=self.toggle_mute,
        )
        self.mute_button.pack(side="left", padx=(0, 4))

        # Volume slider
        self.volume_slider = ctk.CTkSlider(
            controls,
            from_=0,
            to=100,
            width=80,
            command=self._on_volume_changed,
        )
        self.volume_slider.set(self._volume)
        self.volume_slider.pack(side="left", padx=(0, 4))

        self.volume_label = ctk.CTkLabel(
            controls,
            text=f"{self._volume}%",
            width=32,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
            ),
            text_color=TAPO_MUTED,
        )
        self.volume_label.pack(side="left", padx=(0, 6))

        # Quality Switcher (HD / SD)
        if self.quality_callback:
            self.quality_segment = ctk.CTkSegmentedButton(
                controls,
                values=["HD", "SD"],
                width=72,
                height=26,
                selected_color=TAPO_BLUE,
                selected_hover_color=TAPO_BLUE_HOVER,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
                command=self._on_quality_segment_changed,
            )
            self.quality_segment.set(self._current_quality)
            self.quality_segment.pack(side="left", padx=(0, 6))

        # Open Externally Button
        if self.external_callback:
            self.external_button = ctk.CTkButton(
                controls,
                text="↗ External",
                width=85,
                height=28,
                fg_color="#343740",
                hover_color="#454955",
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                command=self._on_external_clicked,
            )
            self.external_button.pack(side="right")

    def _on_resize(self, event=None) -> None:
        try:
            w = self.winfo_width()
            if w > 200:
                target_h = int((w - 12) * 9 / 16)
                target_h = max(220, min(target_h, 560))
                cur_h = self.video_container.cget("height")
                if abs(cur_h - target_h) > 6:
                    self.video_container.configure(height=target_h)
        except Exception:
            pass

    def _initialize_vlc(self) -> None:
        try:
            runtime = prepare_vlc_environment()

            import vlc

            self._vlc = vlc
            plugin_dir = runtime / "plugins"

            vlc_args = [
                "--no-video-title-show",
                "--no-osd",
                "--rtsp-tcp",
                "--network-caching=800",
                "--quiet",
                "--no-mouse-events",
                "--no-keyboard-events",
                "--audio",
            ]

            # 1. Primary instance initialization
            self._instance = vlc.Instance(*vlc_args)

            # 2. Resilient fallback: minimal flags
            if self._instance is None:
                fallback_args = [
                    "--quiet",
                    "--no-video-title-show",
                    "--no-osd",
                    "--audio",
                ]
                self._instance = vlc.Instance(*fallback_args)

            # 3. Minimal fallback without custom options
            if self._instance is None:
                self._instance = vlc.Instance()

            if self._instance is None:
                err_detail = ""
                try:
                    raw_err = vlc.libvlc_errmsg()
                    if raw_err:
                        err_detail = f": {raw_err.decode('utf-8', errors='replace')}"
                except Exception:
                    pass
                raise RuntimeError(
                    f"LibVLC engine failed to initialize{err_detail}. "
                    "Confirm that the bundled LibVLC runtime and codecs are present."
                )

            self._player = self._instance.media_player_new()
            if self._player is None:
                raise RuntimeError("LibVLC failed to create media player instance.")
            self._events = self._player.event_manager()

            self._events.event_attach(
                vlc.EventType.MediaPlayerPlaying,
                self._on_vlc_playing,
            )
            self._events.event_attach(
                vlc.EventType.MediaPlayerPaused,
                self._on_vlc_paused,
            )
            self._events.event_attach(
                vlc.EventType.MediaPlayerStopped,
                self._on_vlc_stopped,
            )
            self._events.event_attach(
                vlc.EventType.MediaPlayerEncounteredError,
                self._on_vlc_error,
            )
            self._events.event_attach(
                vlc.EventType.MediaPlayerEndReached,
                self._on_vlc_ended,
            )

            self.update_idletasks()
            self._attach_video_surface()

            self._player.audio_set_volume(self._volume)
            self._player.audio_set_mute(self._muted)

            if not self._is_playing and not self._playing_file:
                self._set_status("Ready", TAPO_MUTED)

        except Exception as exc:
            self._initialization_error = str(exc)
            self._set_status("Embedded player unavailable", TAPO_RED)
            self.play_button.configure(state="disabled")

    def _attach_video_surface(self) -> None:
        if self._player is None:
            return

        window_id = self.video_surface.winfo_id()

        if os.name == "nt":
            self._player.set_hwnd(window_id)
        else:
            self._player.set_xwindow(window_id)

    def _finish_media_change(self) -> None:
        self._is_changing_media = False

    def play_url(self, stream_url: str) -> None:
        if not stream_url:
            raise ValueError("The RTSP stream URL is empty.")

        if self._initialization_error:
            raise RuntimeError(self._initialization_error)

        if self._instance is None or self._player is None:
            raise RuntimeError("Embedded player has not finished initializing.")

        with self._operation_lock:
            self._is_changing_media = True
            self._current_mode = "live"
            self._current_url = stream_url
            self._playing_file = None
            self._player.stop()

            media = self._instance.media_new(stream_url)
            media.add_option(":rtsp-tcp")
            media.add_option(":network-caching=800")

            self._player.set_media(media)
            self._attach_video_surface()

            # Ensure audio is unmuted and at proper volume before starting
            self._player.audio_set_volume(self._volume)
            self._player.audio_set_mute(self._muted)

            result = self._player.play()

            if result == -1:
                self._is_changing_media = False
                raise RuntimeError("LibVLC rejected the RTSP stream.")

            self.title_label.configure(text="Live Camera")
            self.live_dot.configure(text="●", text_color=TAPO_BLUE)
            self.btn_back_to_live.pack_forget()
            self.placeholder.place_forget()
            self._set_status("Connecting...", TAPO_BLUE)
            self.after(500, self._finish_media_change)

    def play_file(self, file_path: str) -> None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(file_path)

        if self._instance is None or self._player is None:
            raise RuntimeError("Embedded player has not finished initializing.")

        with self._operation_lock:
            self._is_changing_media = True
            self._current_mode = "replay"
            self._playing_file = file_path
            abs_path = os.path.abspath(file_path)
            media = self._instance.media_new_path(abs_path)

            self._player.stop()
            self._player.set_media(media)
            self._attach_video_surface()

            self._player.audio_set_volume(self._volume)
            self._player.audio_set_mute(self._muted)

            if self._player.play() == -1:
                self._is_changing_media = False
                raise RuntimeError("LibVLC could not open the selected file.")

            file_name = os.path.basename(file_path)
            display_name = file_name if len(file_name) <= 34 else file_name[:31] + "..."
            self.title_label.configure(text=f"Clip: {display_name}")
            self.live_dot.configure(text="🎬", text_color=TAPO_BLUE)
            self.btn_back_to_live.pack(side="left", padx=(4, 0))
            self.placeholder.place_forget()
            self._set_status("Playing clip", TAPO_BLUE)
            self.after(500, self._finish_media_change)

    def toggle_play_pause(self) -> None:
        if self._player is None:
            return

        with self._operation_lock:
            state = self._player.get_state()

            # Stopped, Ended, or Error: restart active stream/clip
            if state in (self._vlc.State.Stopped, self._vlc.State.Ended, self._vlc.State.Error, self._vlc.State.NothingSpecial):
                if self._current_mode == "replay" and self._playing_file and os.path.exists(self._playing_file):
                    self.play_file(self._playing_file)
                elif self.live_callback:
                    self.live_callback()
                elif self._current_url:
                    self.play_url(self._current_url)
                return

            # Currently Playing: Pause
            if state == self._vlc.State.Playing:
                self._player.pause()
                self._set_paused_state()
            # Paused: Resume
            else:
                self._player.play()
                self._set_playing_state()

    def stop(self) -> None:
        if self._player is None:
            return

        with self._operation_lock:
            self._player.stop()
            self._is_playing = False
            self._is_paused = False
            self._show_stopped_state()

    def toggle_mute(self) -> None:
        self._muted = not self._muted

        if self._player is not None:
            self._player.audio_set_mute(self._muted)
            if not self._muted:
                self._player.audio_set_volume(self._volume)

        self.mute_button.configure(
            text="🔇" if self._muted else "🔊",
            fg_color="#552222" if self._muted else "#343740",
            hover_color="#6B2D2D" if self._muted else "#454955",
        )

    def _on_volume_changed(self, value: float) -> None:
        self._volume = int(value)
        self.volume_label.configure(text=f"{self._volume}%")

        if self._player is not None:
            if self._muted and self._volume > 0:
                self._muted = False
                self._player.audio_set_mute(False)
                self.mute_button.configure(
                    text="🔊",
                    fg_color="#343740",
                    hover_color="#454955",
                )
            self._player.audio_set_volume(self._volume)

    def get_volume(self) -> int:
        return self._volume

    def is_muted(self) -> bool:
        return self._muted

    def set_quality(self, quality: str) -> None:
        self._current_quality = quality
        if hasattr(self, "quality_segment"):
            self.quality_segment.set(quality)

    def _on_quality_segment_changed(self, value: str) -> None:
        self._current_quality = value
        if self.quality_callback:
            self.quality_callback(value)

    def _on_back_to_live_clicked(self) -> None:
        with self._operation_lock:
            self._is_changing_media = True
            if self._player is not None:
                self._player.stop()
            self._playing_file = None
            self._current_mode = "live"
            self.btn_back_to_live.pack_forget()
            self.title_label.configure(text="Live Camera")
            self.live_dot.configure(text="●", text_color=TAPO_MUTED)
            self.placeholder.configure(text="Connecting to live stream...")
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self._set_status("Switching to live...", TAPO_BLUE)
            if self.live_callback:
                self.live_callback()
            elif self._current_url:
                self.play_url(self._current_url)
            self.after(500, self._finish_media_change)

    def _on_external_clicked(self) -> None:
        if self.external_callback:
            self.external_callback()

    # --- VLC Event Callbacks ---
    def _on_vlc_playing(self, _event) -> None:
        self.after(0, self._set_playing_state)

    def _on_vlc_paused(self, _event) -> None:
        self.after(0, self._set_paused_state)

    def _on_vlc_stopped(self, _event) -> None:
        if getattr(self, "_is_changing_media", False):
            return
        self.after(0, self._show_stopped_state)

    def _on_vlc_ended(self, _event) -> None:
        self.after(0, self._on_playback_ended)

    def _on_vlc_error(self, _event) -> None:
        self.after(
            0,
            lambda: self._set_error_state(
                "Stream unavailable or playback error."
            ),
        )

    def _set_playing_state(self) -> None:
        self._is_playing = True
        self._is_paused = False
        self.placeholder.place_forget()
        self.play_button.configure(
            text="⏸ Pause",
            fg_color="#343740",
            hover_color="#454955",
        )

        if self._current_mode == "replay":
            file_name = os.path.basename(self._playing_file) if self._playing_file else "Recording"
            display_name = file_name if len(file_name) <= 34 else file_name[:31] + "..."
            self.live_dot.configure(text="🎬", text_color=TAPO_BLUE)
            self.title_label.configure(text=f"Clip: {display_name}")
            self.btn_back_to_live.pack(side="left", padx=(4, 0))
            self._set_status("Playing Clip", TAPO_BLUE)
        else:
            self.live_dot.configure(text="●", text_color=TAPO_GREEN)
            self.title_label.configure(text="Live Camera")
            self.btn_back_to_live.pack_forget()
            self._set_status("Live", TAPO_GREEN)

        # Staged checks to guarantee un-muting once audio track negotiation completes
        for delay in (250, 750, 1500, 3000):
            self.after(delay, self._ensure_audio_pipeline)

    def _ensure_audio_pipeline(self) -> None:
        if self._player is None:
            return
        try:
            self._player.audio_set_volume(self._volume)
            self._player.audio_set_mute(self._muted)

            # Query track descriptions
            tracks = self._player.audio_get_track_description()
            if tracks:
                cur_track = self._player.audio_get_track()
                if cur_track == -1:
                    # -1 means disabled; find first active track ID
                    for tid, tname in tracks:
                        if tid != -1:
                            self._player.audio_set_track(tid)
                            break
        except Exception:
            pass

    def _set_paused_state(self) -> None:
        self._is_paused = True
        self.play_button.configure(
            text="▶ Resume",
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
        )

        if self._current_mode == "replay":
            file_name = os.path.basename(self._playing_file) if self._playing_file else "Recording"
            display_name = file_name if len(file_name) <= 34 else file_name[:31] + "..."
            self.live_dot.configure(text="⏸", text_color=TAPO_AMBER)
            self.title_label.configure(text=f"Clip: {display_name}")
            self.btn_back_to_live.pack(side="left", padx=(4, 0))
            self._set_status("Clip Paused", TAPO_AMBER)
        else:
            self.live_dot.configure(text="●", text_color=TAPO_AMBER)
            self.title_label.configure(text="Live Camera")
            self.btn_back_to_live.pack_forget()
            self._set_status("Paused", TAPO_AMBER)

    def _show_stopped_state(self) -> None:
        if getattr(self, "_is_changing_media", False):
            return

        self._is_playing = False
        self._is_paused = False

        if self._current_mode == "replay":
            file_name = os.path.basename(self._playing_file) if self._playing_file else "Recording"
            display_name = file_name if len(file_name) <= 34 else file_name[:31] + "..."
            self.placeholder.configure(text=f"Clip playback stopped: {display_name}")
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self.live_dot.configure(text="■", text_color=TAPO_MUTED)
            self.play_button.configure(
                text="▶ Play",
                fg_color=TAPO_BLUE,
                hover_color=TAPO_BLUE_HOVER,
            )
            self.title_label.configure(text=f"Clip: {display_name}")
            self.btn_back_to_live.pack(side="left", padx=(4, 0))
            self._set_status("Stopped", TAPO_MUTED)
        else:
            self._playing_file = None
            self.placeholder.configure(text="Camera stream is stopped")
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self.live_dot.configure(text="●", text_color=TAPO_MUTED)
            self.play_button.configure(
                text="▶ Start Live",
                fg_color=TAPO_BLUE,
                hover_color=TAPO_BLUE_HOVER,
            )
            self.title_label.configure(text="Live Camera")
            self.btn_back_to_live.pack_forget()
            self._set_status("Stopped", TAPO_MUTED)

    def _on_playback_ended(self) -> None:
        self._is_playing = False
        self._is_paused = False

        if self._current_mode == "replay":
            file_name = os.path.basename(self._playing_file) if self._playing_file else "Recording"
            display_name = file_name if len(file_name) <= 34 else file_name[:31] + "..."
            self.placeholder.configure(text="Clip playback finished")
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self.live_dot.configure(text="■", text_color=TAPO_MUTED)
            self.play_button.configure(
                text="▶ Replay",
                fg_color=TAPO_BLUE,
                hover_color=TAPO_BLUE_HOVER,
            )
            self.title_label.configure(text=f"Clip: {display_name}")
            self.btn_back_to_live.pack(side="left", padx=(4, 0))
            self._set_status("Ended", TAPO_MUTED)
        else:
            self._show_stopped_state()

    def _set_error_state(self, message: str) -> None:
        self._is_playing = False
        self._is_paused = False
        self.placeholder.configure(text=message)
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
        self.live_dot.configure(text_color=TAPO_RED)

        if self._current_mode == "replay":
            self.play_button.configure(
                text="▶ Retry Clip",
                fg_color=TAPO_BLUE,
                hover_color=TAPO_BLUE_HOVER,
            )
            self.btn_back_to_live.pack(side="left", padx=(4, 0))
        else:
            self.play_button.configure(
                text="▶ Retry Live",
                fg_color=TAPO_BLUE,
                hover_color=TAPO_BLUE_HOVER,
            )
            self.btn_back_to_live.pack_forget()
        self._set_status("Playback error", TAPO_RED)

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, text_color=color)

        if self.status_callback:
            self.status_callback(text, color)

    def close(self) -> None:
        with self._operation_lock:
            if self._player is not None:
                try:
                    self._player.stop()
                    self._player.release()
                except Exception:
                    pass

            if self._instance is not None:
                try:
                    self._instance.release()
                except Exception:
                    pass

            self._player = None
            self._instance = None
            self._vlc = None
