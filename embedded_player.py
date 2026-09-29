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
TAPO_RED = "#E74C3C"
FONT_FAMILY = "Segoe UI"


class EmbeddedVLCPlayer(ctk.CTkFrame):
    """
    Embedded LibVLC video player for CustomTkinter.

    Windows uses MediaPlayer.set_hwnd() with the native Tk window handle.
    """

    def __init__(
        self,
        master,
        status_callback: Optional[Callable[[str, str], None]] = None,
        external_callback: Optional[Callable[[], None]] = None,
        initial_volume: int = 50,
        initially_muted: bool = True,
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

        self._vlc = None
        self._instance = None
        self._player = None
        self._events = None

        self._current_url: Optional[str] = None
        self._is_playing = False
        self._muted = initially_muted
        self._volume = max(0, min(100, int(initial_volume)))
        self._initialization_error: Optional[str] = None
        self._operation_lock = threading.RLock()

        self._build_ui()

        # Initialization is postponed until Tk has created window handles.
        self.after(100, self._initialize_vlc)

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(11, 8))

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
                size=14,
                weight="bold",
            ),
            text_color="#FFFFFF",
        )
        self.title_label.pack(side="left", padx=(5, 0))

        self.status_label = ctk.CTkLabel(
            header,
            text="Player initializing",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            text_color=TAPO_MUTED,
        )
        self.status_label.pack(side="right")

        self.video_container = ctk.CTkFrame(
            self,
            fg_color=TAPO_PANEL_BG,
            corner_radius=8,
            height=320,
        )
        self.video_container.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=(0, 8),
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

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=14, pady=(0, 11))

        self.play_button = ctk.CTkButton(
            controls,
            text="▶ Start Live",
            width=105,
            height=30,
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.resume,
        )
        self.play_button.pack(side="left", padx=(0, 6))

        self.stop_button = ctk.CTkButton(
            controls,
            text="■ Stop",
            width=72,
            height=30,
            fg_color="#343740",
            hover_color=TAPO_RED,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.stop,
        )
        self.stop_button.pack(side="left", padx=(0, 8))

        self.mute_button = ctk.CTkButton(
            controls,
            text="🔇 Muted" if self._muted else "🔊 Sound",
            width=82,
            height=30,
            fg_color="#343740",
            hover_color="#454955",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            command=self.toggle_mute,
        )
        self.mute_button.pack(side="left", padx=(0, 8))

        self.volume_slider = ctk.CTkSlider(
            controls,
            from_=0,
            to=100,
            width=120,
            command=self._on_volume_changed,
        )
        self.volume_slider.set(self._volume)
        self.volume_slider.pack(side="left", padx=(0, 12))

        self.volume_label = ctk.CTkLabel(
            controls,
            text=f"{self._volume}%",
            width=38,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
            ),
            text_color=TAPO_MUTED,
        )
        self.volume_label.pack(side="left")

        if self.external_callback:
            external_button = ctk.CTkButton(
                controls,
                text="Open externally ↗",
                width=115,
                height=30,
                fg_color="#343740",
                hover_color="#454955",
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=11,
                ),
                command=self.external_callback,
            )
            external_button.pack(side="right")

    def _initialize_vlc(self) -> None:
        try:
            prepare_vlc_environment()

            # Import only after DLL and VLC_PLUGIN_PATH configuration.
            import vlc

            self._vlc = vlc
            self._instance = vlc.Instance(
                "--no-video-title-show",
                "--no-osd",
                "--rtsp-tcp",
                "--network-caching=800",
                "--clock-jitter=0",
                "--clock-synchro=0",
                "--quiet",
            )
            self._player = self._instance.media_player_new()
            self._events = self._player.event_manager()

            self._events.event_attach(
                vlc.EventType.MediaPlayerPlaying,
                self._on_vlc_playing,
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
                self._on_vlc_stopped,
            )

            self.update_idletasks()
            self._attach_video_surface()

            self._player.audio_set_volume(self._volume)
            self._player.audio_set_mute(self._muted)

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
            # Source development fallback for Linux/X11.
            self._player.set_xwindow(window_id)

    def play_url(self, stream_url: str) -> None:
        if not stream_url:
            raise ValueError("The RTSP stream URL is empty.")

        if self._initialization_error:
            raise RuntimeError(self._initialization_error)

        if self._instance is None or self._player is None:
            raise RuntimeError("Embedded player has not finished initializing.")

        with self._operation_lock:
            self._current_url = stream_url
            self._player.stop()

            media = self._instance.media_new(stream_url)
            media.add_option(":rtsp-tcp")
            media.add_option(":network-caching=800")
            media.add_option(":clock-jitter=0")
            media.add_option(":clock-synchro=0")

            self._player.set_media(media)
            self._attach_video_surface()
            self._player.audio_set_volume(self._volume)
            self._player.audio_set_mute(self._muted)

            result = self._player.play()

            if result == -1:
                raise RuntimeError("LibVLC rejected the RTSP stream.")

            self.placeholder.place_forget()
            self._set_status("Connecting...", TAPO_BLUE)

    def play_file(self, file_path: str) -> None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(file_path)

        if self._instance is None or self._player is None:
            raise RuntimeError("Embedded player has not finished initializing.")

        with self._operation_lock:
            self._current_url = None
            media = self._instance.media_new_path(
                os.path.abspath(file_path)
            )

            self._player.stop()
            self._player.set_media(media)
            self._attach_video_surface()
            self._player.audio_set_volume(self._volume)
            self._player.audio_set_mute(self._muted)

            if self._player.play() == -1:
                raise RuntimeError("LibVLC could not open the selected file.")

            self.placeholder.place_forget()
            self._set_status("Opening recording...", TAPO_BLUE)

    def resume(self) -> None:
        if self._player is None:
            return

        if self._current_url and not self._is_playing:
            self.play_url(self._current_url)
            return

        self._player.play()

    def stop(self) -> None:
        if self._player is None:
            return

        with self._operation_lock:
            self._player.stop()
            self._is_playing = False
            self._show_stopped_state()

    def toggle_mute(self) -> None:
        self._muted = not self._muted

        if self._player is not None:
            self._player.audio_set_mute(self._muted)

        self.mute_button.configure(
            text="🔇 Muted" if self._muted else "🔊 Sound"
        )

    def _on_volume_changed(self, value: float) -> None:
        self._volume = int(value)
        self.volume_label.configure(text=f"{self._volume}%")

        if self._player is not None:
            self._player.audio_set_volume(self._volume)

    def get_volume(self) -> int:
        return self._volume

    def is_muted(self) -> bool:
        return self._muted

    def _on_vlc_playing(self, _event) -> None:
        self.after(
            0,
            lambda: self._set_playing_state(),
        )

    def _on_vlc_stopped(self, _event) -> None:
        self.after(
            0,
            lambda: self._show_stopped_state(),
        )

    def _on_vlc_error(self, _event) -> None:
        self.after(
            0,
            lambda: self._set_error_state(
                "Stream unavailable or authentication failed."
            ),
        )

    def _set_playing_state(self) -> None:
        self._is_playing = True
        self.placeholder.place_forget()
        self.live_dot.configure(text_color=TAPO_GREEN)
        self.play_button.configure(text="▶ Playing")
        self._set_status("Live", TAPO_GREEN)

    def _show_stopped_state(self) -> None:
        self._is_playing = False
        self.placeholder.configure(text="Camera stream is stopped")
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
        self.live_dot.configure(text_color=TAPO_MUTED)
        self.play_button.configure(text="▶ Start Live")
        self._set_status("Stopped", TAPO_MUTED)

    def _set_error_state(self, message: str) -> None:
        self._is_playing = False
        self.placeholder.configure(text=message)
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
        self.live_dot.configure(text_color=TAPO_RED)
        self.play_button.configure(text="Retry Live")
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
