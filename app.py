import os
import sys
import threading
import datetime
import socket
from typing import Optional, Dict, Any, List

import customtkinter as ctk
from tkinter import messagebox, filedialog

from config_manager import (
    load_config,
    save_config,
    load_credentials,
    save_credentials,
    delete_credentials,
)
from camera_backend import CameraBackend
from tapo_calendar import TapoCalendar
from about_dialog import AboutDialog
from embedded_player import EmbeddedVLCPlayer

# =============================================================================
# TAPO-VIEWER DESIGN SYSTEM & PALETTE (Operate Mode, Segoe UI)
# =============================================================================
TAPO_BLUE = "#00A4E4"
TAPO_BLUE_HOVER = "#008BC2"
TAPO_DARK_BG = "#0D0E11"
TAPO_SIDEBAR_BG = "#15161A"
TAPO_CARD_BG = "#1E2026"
TAPO_CARD_HOVER = "#272A32"
TAPO_TEXT_MUTED = "#8A8D98"
TAPO_AMBER = "#FFA000"
TAPO_GREEN = "#2ECC71"
TAPO_RED = "#E74C3C"
FONT_FAMILY = "Segoe UI"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TapoViewerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Tapo-Viewer")
        self.geometry("1260x840")
        self.minsize(980, 600)
        self.configure(fg_color=TAPO_DARK_BG)

        # Set Window Icon
        try:
            from about_dialog import get_bundle_dir
            icon_file = os.path.join(get_bundle_dir(), "assets", "icon.ico")
            if os.path.exists(icon_file):
                self.iconbitmap(icon_file)
        except Exception:
            pass

        # Start maximized on Windows (standard full desktop view)
        try:
            self.after(50, lambda: self.state("zoomed"))
        except Exception:
            pass

        # F11 True Fullscreen Toggle
        self.is_fullscreen = False
        self.bind("<F11>", self._toggle_fullscreen)

        # Backend & Config State
        self.backend = CameraBackend()
        self.config = load_config()

        self.all_recordings: List[Dict[str, Any]] = []
        self.filtered_recordings: List[Dict[str, Any]] = []
        self.available_dates: List[str] = []
        self.selected_date: str = datetime.date.today().strftime("%Y-%m-%d")
        self.active_filter: str = "all"

        # Smooth scrolling / pagination state (eliminates jitter)
        self.rendered_count: int = 0
        self.BATCH_SIZE: int = 25

        self.active_download_thread: Optional[threading.Thread] = None
        self.auto_play_target: Optional[str] = None

        # Build Primary Screen (Login) and Dashboard Screen
        self._build_app_scaffold()
        self._show_login_screen()
        self.after(300, self._validate_runtime_dependencies)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    # =========================================================================
    # APP SCAFFOLD: VIEW MANAGEMENT
    # =========================================================================
    def _build_app_scaffold(self):
        self.container = ctk.CTkFrame(self, fg_color=TAPO_DARK_BG, corner_radius=0)
        self.container.pack(fill="both", expand=True)

        self._build_login_view()
        self._build_dashboard_view()

    def _show_login_screen(self):
        if hasattr(self, "dashboard_view") and self.dashboard_view.winfo_ismapped():
            self.dashboard_view.pack_forget()
        self.login_view.pack(fill="both", expand=True)
        self._populate_login_fields()

    def _show_dashboard_screen(self):
        if hasattr(self, "login_view") and self.login_view.winfo_ismapped():
            self.login_view.pack_forget()
        self.dashboard_view.pack(fill="both", expand=True)

    # =========================================================================
    # 1. PRIMARY SCREEN: LOGIN & WELCOME PORTAL (WITHOUT LOGIN SHOW NOTHING)
    # =========================================================================
    def _build_login_view(self):
        self.login_view = ctk.CTkFrame(self.container, fg_color=TAPO_DARK_BG, corner_radius=0)

        # Top Bar
        top_bar = ctk.CTkFrame(self.login_view, fg_color=TAPO_SIDEBAR_BG, height=46, corner_radius=0)
        top_bar.pack(fill="x", side="top")
        top_bar.pack_propagate(False)

        brand_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        brand_box.pack(side="left", padx=20, pady=6)

        ctk.CTkLabel(
            brand_box,
            text="📷 Tapo-Viewer",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=TAPO_BLUE
        ).pack(side="left")

        ctk.CTkLabel(
            brand_box,
            text="Local Studio",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=TAPO_TEXT_MUTED
        ).pack(side="left", padx=(8, 0), pady=(2, 0))

        # Right Action in top bar: About Button
        ctk.CTkButton(
            top_bar,
            text="ℹ️ About",
            width=76,
            height=26,
            fg_color="#272A32",
            hover_color=TAPO_CARD_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            command=self._open_about_dialog
        ).pack(side="right", padx=20, pady=10)

        # Main Center Container (Fits 1366x768 cleanly with 0 scrolling)
        center_scroll = ctk.CTkScrollableFrame(self.login_view, fg_color="transparent", corner_radius=0)
        center_scroll.pack(fill="both", expand=True, padx=24, pady=8)

        # Two-Column Layout Container
        grid_container = ctk.CTkFrame(center_scroll, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, pady=0)
        grid_container.grid_columnconfigure(0, weight=1, minsize=400)
        grid_container.grid_columnconfigure(1, weight=1, minsize=420)

        # ---------------------------------------------------------------------
        # LEFT COLUMN: Connection Form Card
        # ---------------------------------------------------------------------
        conn_card = ctk.CTkFrame(grid_container, corner_radius=12, fg_color=TAPO_CARD_BG)
        conn_card.grid(row=0, column=0, sticky="nsew", padx=(6, 10), pady=6)

        ctk.CTkLabel(
            conn_card,
            text="Connect Camera",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w", padx=20, pady=(14, 2))

        ctk.CTkLabel(
            conn_card,
            text="Direct local LAN connection. Zero cloud subscription required.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TAPO_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Field: Camera IP
        ctk.CTkLabel(
            conn_card,
            text="Camera IP Address",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w", padx=20, pady=(0, 2))

        self.entry_ip = ctk.CTkEntry(
            conn_card,
            placeholder_text="e.g. 192.168.0.103",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=32
        )
        self.entry_ip.pack(fill="x", padx=20, pady=(0, 8))

        # Field: Camera Account Username
        ctk.CTkLabel(
            conn_card,
            text="Camera Account Username",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w", padx=20, pady=(0, 2))

        self.entry_user = ctk.CTkEntry(
            conn_card,
            placeholder_text="e.g. zaifears",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=32
        )
        self.entry_user.pack(fill="x", padx=20, pady=(0, 8))

        # Field: Camera Account Password
        pass_label_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        pass_label_row.pack(fill="x", padx=20, pady=(0, 2))

        ctk.CTkLabel(
            pass_label_row,
            text="Camera Account Password",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color="#FFFFFF"
        ).pack(side="left")

        pass_input_box = ctk.CTkFrame(conn_card, fg_color="transparent")
        pass_input_box.pack(fill="x", padx=20, pady=(0, 8))

        self.entry_pass = ctk.CTkEntry(
            pass_input_box,
            placeholder_text="Enter camera account password",
            show="•",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=32
        )
        self.entry_pass.pack(side="left", fill="x", expand=True)

        self.btn_toggle_pass = ctk.CTkButton(
            pass_input_box,
            text="👁",
            width=38,
            height=32,
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            command=self._toggle_password_visibility
        )
        self.btn_toggle_pass.pack(side="left", padx=(6, 0))

        # -----------------------------------------------------------------
        # PROMINENT OPTION 1: Different Cloud Password
        # -----------------------------------------------------------------
        self.cloud_opt_card = ctk.CTkFrame(conn_card, fg_color="#17181D", corner_radius=8)
        self.cloud_opt_card.pack(fill="x", padx=20, pady=(0, 8))

        cloud_card_inner = ctk.CTkFrame(self.cloud_opt_card, fg_color="transparent")
        cloud_card_inner.pack(fill="x", padx=12, pady=6)

        self.var_show_cloud_pass = ctk.BooleanVar(value=False)
        self.chk_show_cloud = ctk.CTkCheckBox(
            cloud_card_inner,
            text="Different Cloud Password",
            variable=self.var_show_cloud_pass,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color="#FFFFFF",
            checkbox_height=18,
            checkbox_width=18,
            border_width=2,
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            command=self._toggle_cloud_pass_field
        )
        self.chk_show_cloud.pack(anchor="w")

        ctk.CTkLabel(
            cloud_card_inner,
            text="Enable if your TP-Link / Tapo Cloud account password differs from camera credentials.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=TAPO_TEXT_MUTED,
            wraplength=340,
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # Cloud password input container - packs directly inside cloud_card_inner when enabled!
        self.cloud_pass_container = ctk.CTkFrame(cloud_card_inner, fg_color="transparent")

        cloud_input_box = ctk.CTkFrame(self.cloud_pass_container, fg_color="transparent")
        cloud_input_box.pack(fill="x", pady=(6, 0))

        self.entry_cloud_pass = ctk.CTkEntry(
            cloud_input_box,
            placeholder_text="Enter Tapo Cloud Account Password",
            show="•",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=32
        )
        self.entry_cloud_pass.pack(side="left", fill="x", expand=True)

        self.btn_toggle_cloud_pass = ctk.CTkButton(
            cloud_input_box,
            text="👁",
            width=38,
            height=32,
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            command=self._toggle_cloud_password_visibility
        )
        self.btn_toggle_cloud_pass.pack(side="left", padx=(6, 0))

        # -----------------------------------------------------------------
        # PROMINENT OPTION 2: Remember Credentials (Disabled by default)
        # -----------------------------------------------------------------
        self.save_creds_card = ctk.CTkFrame(conn_card, fg_color="#17181D", corner_radius=8)
        self.save_creds_card.pack(fill="x", padx=20, pady=(0, 8))

        save_card_inner = ctk.CTkFrame(self.save_creds_card, fg_color="transparent")
        save_card_inner.pack(fill="x", padx=12, pady=6)

        self.var_save_creds = ctk.BooleanVar(value=False)
        self.chk_save_creds = ctk.CTkCheckBox(
            save_card_inner,
            text="Remember credentials on this PC",
            variable=self.var_save_creds,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color="#FFFFFF",
            checkbox_height=18,
            checkbox_width=18,
            border_width=2,
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER
        )
        self.chk_save_creds.pack(anchor="w")

        ctk.CTkLabel(
            save_card_inner,
            text="Save camera IP and credentials locally for instant 1-click reconnect.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=TAPO_TEXT_MUTED,
            wraplength=340,
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # Status / Feedback label
        self.lbl_login_status = ctk.CTkLabel(
            conn_card,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TAPO_AMBER,
            wraplength=360,
            justify="left"
        )
        self.lbl_login_status.pack(anchor="w", padx=20, pady=(0, 6))

        # Progress bar during login
        self.login_progress = ctk.CTkProgressBar(conn_card, height=5, progress_color=TAPO_BLUE, mode="indeterminate")

        # Action Buttons
        self.btn_connect = ctk.CTkButton(
            conn_card,
            text="⚡ Connect Camera",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            height=38,
            command=self._on_connect_clicked
        )
        self.btn_connect.pack(fill="x", padx=20, pady=(0, 6))

        self.btn_ping_test = ctk.CTkButton(
            conn_card,
            text="🔍 Quick Connection Test (Ping & Ports)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color="#272A32",
            hover_color=TAPO_CARD_HOVER,
            height=30,
            command=self._test_connection_probe
        )
        self.btn_ping_test.pack(fill="x", padx=20, pady=(0, 14))

        # ---------------------------------------------------------------------
        # RIGHT COLUMN: Comprehensive Help & Setup Assistant ("help as much as possible")
        # ---------------------------------------------------------------------
        guide_card = ctk.CTkFrame(grid_container, corner_radius=12, fg_color=TAPO_CARD_BG)
        guide_card.grid(row=0, column=1, sticky="nsew", padx=(10, 6), pady=6)

        ctk.CTkLabel(
            guide_card,
            text="📘 Tapo Camera Setup Guide",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w", padx=20, pady=(14, 2))

        ctk.CTkLabel(
            guide_card,
            text="Follow these simple steps in your official Tapo mobile app to connect:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TAPO_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Help Step 1: Camera IP
        self._build_help_step(
            parent=guide_card,
            step_num="1",
            title="Find Your Camera's IP Address",
            details="Open the Tapo mobile app ➔ Tap your camera card ➔ Tap Settings (⚙️ icon in top-right) ➔ Tap 'Device Info' ➔ Copy the 'IP Address' (e.g. 192.168.0.103)."
        )

        # Help Step 2: Camera Account (Crucial!)
        self._build_help_step(
            parent=guide_card,
            step_num="2",
            title="Create Camera Account (Crucial!)",
            details="In Camera Settings ➔ Tap 'Advanced Settings' ➔ Tap 'Camera Account'.\nCreate a local username & password.\n\n⚠️ Note: This is NOT your TP-Link email login! It is a dedicated local account used for live RTSP streaming and downloading SD card recordings directly."
        )

        # Help Step 3: Local Network
        self._build_help_step(
            parent=guide_card,
            step_num="3",
            title="Wi-Fi & Network Subnet",
            details="Ensure this computer and your Tapo camera are connected to the same Wi-Fi router or subnet (LAN-to-LAN router setups with DHCP disabled work seamlessly)."
        )

        # Help Step 4: Storage & Privacy
        self._build_help_step(
            parent=guide_card,
            step_num="4",
            title="100% Local & Private Storage",
            details="All video feeds and MicroSD files stream directly from the camera to your computer. Nothing is ever sent to external cloud servers. You can choose where to save your recordings anytime."
        )

    def _build_help_step(self, parent, step_num: str, title: str, details: str):
        box = ctk.CTkFrame(parent, fg_color="#17181D", corner_radius=8)
        box.pack(fill="x", padx=20, pady=(0, 6))

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=6)

        badge = ctk.CTkLabel(
            inner,
            text=step_num,
            width=22,
            height=22,
            corner_radius=11,
            fg_color=TAPO_BLUE,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
        )
        badge.pack(side="left", anchor="n", padx=(0, 10))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            text_col,
            text=title,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_col,
            text=details,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=TAPO_TEXT_MUTED,
            wraplength=340,
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

    def _toggle_password_visibility(self):
        if self.entry_pass.cget("show") == "•":
            self.entry_pass.configure(show="")
            self.btn_toggle_pass.configure(text="🙈")
        else:
            self.entry_pass.configure(show="•")
            self.btn_toggle_pass.configure(text="👁")

    def _toggle_cloud_pass_field(self):
        if self.var_show_cloud_pass.get():
            self.cloud_pass_container.pack(fill="x")
        else:
            self.cloud_pass_container.pack_forget()

    def _toggle_cloud_password_visibility(self):
        if self.entry_cloud_pass.cget("show") == "•":
            self.entry_cloud_pass.configure(show="")
            self.btn_toggle_cloud_pass.configure(text="🙈")
        else:
            self.entry_cloud_pass.configure(show="•")
            self.btn_toggle_cloud_pass.configure(text="👁")

    def _populate_login_fields(self):
        host = str(self.config.get("host", "")).strip()
        username = str(self.config.get("username", "")).strip()
        remember = bool(
            self.config.get("save_credentials", False)
        )

        self.entry_ip.delete(0, "end")
        self.entry_user.delete(0, "end")
        self.entry_pass.delete(0, "end")
        self.entry_cloud_pass.delete(0, "end")

        if host:
            self.entry_ip.insert(0, host)

        if username:
            self.entry_user.insert(0, username)

        self.var_save_creds.set(remember)

        if not remember or not host or not username:
            self.var_show_cloud_pass.set(False)
            self._toggle_cloud_pass_field()
            return

        try:
            camera_password, cloud_password = load_credentials(
                host,
                username,
            )

            if camera_password:
                self.entry_pass.insert(0, camera_password)

            if cloud_password:
                self.entry_cloud_pass.insert(0, cloud_password)
                self.var_show_cloud_pass.set(True)
            else:
                self.var_show_cloud_pass.set(False)

            self._toggle_cloud_pass_field()

        except Exception as exc:
            self.var_save_creds.set(False)
            self._show_login_status(
                "Saved credentials could not be loaded from Windows "
                f"Credential Manager: {exc}",
                is_error=True,
            )

    def _test_connection_probe(self):
        host = self.entry_ip.get().strip()
        if not host:
            self.lbl_login_status.configure(text="⚠️ Please enter camera IP address first.", text_color=TAPO_AMBER)
            return

        self.btn_ping_test.configure(state="disabled", text="⏳ Testing connection...")
        self.lbl_login_status.configure(text=f"Probing {host} on ports 554 (RTSP) and 443 (Control)...", text_color=TAPO_BLUE)

        def _worker():
            results = []
            # Port 554 (RTSP)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                r554 = s.connect_ex((host, 554))
                s.close()
                results.append("Port 554 (RTSP): " + ("OPEN ✅" if r554 == 0 else "CLOSED ❌"))
            except Exception:
                results.append("Port 554: Unreachable ❌")

            # Port 443 (Control)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                r443 = s.connect_ex((host, 443))
                s.close()
                results.append("Port 443 (Control): " + ("OPEN ✅" if r443 == 0 else "CLOSED ❌"))
            except Exception:
                results.append("Port 443: Unreachable ❌")

            msg = " • ".join(results)
            self.after(0, lambda: self._on_probe_complete(msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_probe_complete(self, msg: str):
        self.btn_ping_test.configure(state="normal", text="🔍 Quick Connection Test (Ping & Ports)")
        color = TAPO_GREEN if "OPEN" in msg else TAPO_RED
        self.lbl_login_status.configure(text=msg, text_color=color)

    # =========================================================================
    # 2. DASHBOARD VIEW: 0 SCROLLING SIDEBAR & RECORDINGS TIMELINE
    # =========================================================================
    def _build_dashboard_view(self):
        self.dashboard_view = ctk.CTkFrame(self.container, fg_color=TAPO_DARK_BG, corner_radius=0)
        self.dashboard_view.grid_columnconfigure(0, weight=0, minsize=350)  # Left Sidebar (0 SCROLLING!)
        self.dashboard_view.grid_columnconfigure(1, weight=1)               # Main Content Area
        self.dashboard_view.grid_rowconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # LEFT SIDEBAR: Clean, Fixed Layout (0 SCROLLING NEEDED!)
        # ---------------------------------------------------------------------
        self.sidebar_frame = ctk.CTkFrame(
            self.dashboard_view,
            corner_radius=0,
            fg_color=TAPO_SIDEBAR_BG,
            width=350
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # 1. Device Info & Disconnect Card
        self.device_card = ctk.CTkFrame(self.sidebar_frame, corner_radius=12, fg_color=TAPO_CARD_BG)
        self.device_card.pack(fill="x", padx=14, pady=(16, 10))

        status_header = ctk.CTkFrame(self.device_card, fg_color="transparent")
        status_header.pack(fill="x", padx=16, pady=(12, 4))

        self.lbl_dash_status = ctk.CTkLabel(
            status_header,
            text="● Online",
            text_color=TAPO_GREEN,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold")
        )
        self.lbl_dash_status.pack(side="left")

        # Sleek Disconnect Button
        self.btn_disconnect = ctk.CTkButton(
            status_header,
            text="Disconnect",
            width=80,
            height=26,
            fg_color="#2B2D35",
            hover_color=TAPO_RED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            command=self._on_disconnect_clicked
        )
        self.btn_disconnect.pack(side="right")

        self.lbl_device_model = ctk.CTkLabel(
            self.device_card,
            text="Tapo Camera",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color="#FFFFFF"
        )
        self.lbl_device_model.pack(anchor="w", padx=16, pady=(0, 2))

        self.lbl_device_ip = ctk.CTkLabel(
            self.device_card,
            text="IP: -",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TAPO_TEXT_MUTED
        )
        self.lbl_device_ip.pack(anchor="w", padx=16, pady=(0, 12))

        # 2. Live Feed & Media Player Card
        self.player_card = ctk.CTkFrame(
            self.sidebar_frame,
            corner_radius=10,
            fg_color=TAPO_CARD_BG,
        )
        self.player_card.pack(
            fill="x",
            padx=14,
            pady=(0, 10),
        )

        p_inner = ctk.CTkFrame(
            self.player_card,
            fg_color="transparent",
        )
        p_inner.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=10,
        )

        ctk.CTkLabel(
            p_inner,
            text="Live Stream",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color="#FFFFFF",
        ).pack(anchor="w", pady=(0, 6))

        quality_row = ctk.CTkFrame(
            p_inner,
            fg_color="transparent",
        )
        quality_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            quality_row,
            text="Quality:",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            text_color=TAPO_TEXT_MUTED,
        ).pack(side="left")

        self.segment_live_quality = ctk.CTkSegmentedButton(
            quality_row,
            values=["HD", "SD"],
            selected_color=TAPO_BLUE,
            selected_hover_color=TAPO_BLUE_HOVER,
            command=self._on_live_quality_changed,
            width=120,
            height=27,
        )
        self.segment_live_quality.set(
            self.config.get("live_stream_quality", "HD")
        )
        self.segment_live_quality.pack(side="right")

        self.btn_live_stream = ctk.CTkButton(
            p_inner,
            text="▶ Start Embedded Live Feed",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            height=34,
            command=self._on_launch_live_stream,
        )
        self.btn_live_stream.pack(fill="x", pady=(0, 6))

        self.btn_external_stream = ctk.CTkButton(
            p_inner,
            text="Open in External Player ↗",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            height=30,
            command=self._on_launch_live_stream_external,
        )
        self.btn_external_stream.pack(fill="x", pady=(0, 8))

        # Media Player selection row (Fallback)
        player_row = ctk.CTkFrame(p_inner, fg_color="transparent")
        player_row.pack(fill="x")

        ctk.CTkLabel(
            player_row,
            text="Player:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=TAPO_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        self.opt_media_player = ctk.CTkOptionMenu(
            player_row,
            values=["Auto-Detect"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            dropdown_font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color="#2B2D35",
            button_color="#363943",
            button_hover_color=TAPO_BLUE,
            height=26,
            command=self._on_player_selection_changed
        )
        self.opt_media_player.pack(side="left", fill="x", expand=True)
        self._update_player_menu_selection()

        # 3. Tapo Calendar Widget (Fits smoothly, 0 scrolling!)
        self.calendar_widget = TapoCalendar(
            self.sidebar_frame,
            on_date_selected=self._on_calendar_date_selected,
            initial_date=self.selected_date
        )
        self.calendar_widget.pack(fill="x", padx=14, pady=(0, 12))

        # 4. Local Storage Card (Works on ANY drive or folder!)
        self.storage_card = ctk.CTkFrame(self.sidebar_frame, corner_radius=10, fg_color=TAPO_CARD_BG)
        self.storage_card.pack(fill="x", padx=14, pady=(0, 14))

        s_head = ctk.CTkFrame(self.storage_card, fg_color="transparent")
        s_head.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            s_head,
            text="📁 Local Storage",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=TAPO_BLUE
        ).pack(side="left")

        self.lbl_folder_path = ctk.CTkLabel(
            self.storage_card,
            text=self.config.get("output_dir", ""),
            text_color=TAPO_TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            wraplength=310,
            justify="left"
        )
        self.lbl_folder_path.pack(anchor="w", padx=14, pady=(0, 8))

        s_btn_row = ctk.CTkFrame(self.storage_card, fg_color="transparent")
        s_btn_row.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkButton(
            s_btn_row,
            text="Change...",
            width=75,
            height=26,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            command=self._on_choose_folder
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            s_btn_row,
            text="Open Folder",
            width=90,
            height=26,
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            command=self._on_open_recordings_folder
        ).pack(side="left")

        # ---------------------------------------------------------------------
        # MAIN WORKSPACE: Playback Timeline & Recordings List
        # ---------------------------------------------------------------------
        self.main_frame = ctk.CTkFrame(self.dashboard_view, corner_radius=0, fg_color=TAPO_DARK_BG)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_rowconfigure(3, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Embedded live video panel
        self.live_player = EmbeddedVLCPlayer(
            self.main_frame,
            status_callback=self._on_live_player_status,
            external_callback=self._on_launch_live_stream_external,
            initial_volume=int(
                self.config.get("live_stream_volume", 50)
            ),
            initially_muted=bool(
                self.config.get("live_stream_muted", True)
            ),
        )
        self.live_player.grid(
            row=0,
            column=0,
            padx=20,
            pady=(18, 8),
            sticky="nsew",
        )

        # Header Bar: Active Date Display & Filter Chips
        self.header_frame = ctk.CTkFrame(self.main_frame, corner_radius=12, fg_color=TAPO_CARD_BG)
        self.header_frame.grid(row=1, column=0, padx=20, pady=(10, 8), sticky="ew")

        # Left of header: Date badge & Quick buttons
        date_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        date_box.pack(side="left", padx=16, pady=12)

        self.lbl_active_date = ctk.CTkLabel(
            date_box,
            text=f"📅 {self.selected_date}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color="#FFFFFF"
        )
        self.lbl_active_date.pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            date_box,
            text="Today",
            width=58,
            height=28,
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            command=lambda: self._select_date(datetime.date.today().strftime("%Y-%m-%d"))
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            date_box,
            text="Yesterday",
            width=72,
            height=28,
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            command=lambda: self._select_date((datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"))
        ).pack(side="left", padx=(0, 12))

        self.btn_refresh = ctk.CTkButton(
            date_box,
            text="🔄 Refresh SD Card",
            width=135,
            height=28,
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            command=self._on_refresh_sd_clicked
        )
        self.btn_refresh.pack(side="left")

        # Right of header: Segmented Filter (All, Motion, Continuous)
        filter_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        filter_box.pack(side="right", padx=16, pady=12)

        ctk.CTkLabel(filter_box, text="Filter:", font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=TAPO_TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.seg_filter = ctk.CTkSegmentedButton(
            filter_box,
            values=["All", "Motion", "Continuous"],
            selected_color=TAPO_BLUE,
            selected_hover_color=TAPO_BLUE_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            command=self._on_filter_changed
        )
        self.seg_filter.set("All")
        self.seg_filter.pack(side="left")

        # Summary Sub-header
        self.stats_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stats_bar.grid(row=2, column=0, padx=25, pady=(0, 6), sticky="ew")

        self.lbl_recordings_summary = ctk.CTkLabel(
            self.stats_bar,
            text="Detected Events",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color="#FFFFFF"
        )
        self.lbl_recordings_summary.pack(side="left")

        self.lbl_total_duration = ctk.CTkLabel(
            self.stats_bar,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TAPO_TEXT_MUTED
        )
        self.lbl_total_duration.pack(side="right")

        # Scrollable Recordings Area
        self.scroll_recordings = ctk.CTkScrollableFrame(
            self.main_frame,
            corner_radius=12,
            fg_color=TAPO_CARD_BG
        )
        self.scroll_recordings.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="nsew")

        # ---------------------------------------------------------------------
        # BOTTOM DOWNLOAD TAB: PERMANENTLY DOCKED ("stay forever")
        # ---------------------------------------------------------------------
        self.progress_panel = ctk.CTkFrame(self.main_frame, corner_radius=12, fg_color=TAPO_CARD_BG, height=85)
        self.progress_panel.grid(row=4, column=0, padx=20, pady=(0, 14), sticky="ew")

        progress_inner = ctk.CTkFrame(self.progress_panel, fg_color="transparent")
        progress_inner.pack(fill="both", expand=True, padx=16, pady=10)

        # Top row of download bar: Status + Actions + About Button
        bar_top = ctk.CTkFrame(progress_inner, fg_color="transparent")
        bar_top.pack(fill="x", pady=(0, 6))

        self.lbl_download_title = ctk.CTkLabel(
            bar_top,
            text="📥 Download Manager (Idle)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color="#FFFFFF"
        )
        self.lbl_download_title.pack(side="left")

        # Right side actions in bottom bar
        bar_actions = ctk.CTkFrame(bar_top, fg_color="transparent")
        bar_actions.pack(side="right")

        self.btn_cancel_dl = ctk.CTkButton(
            bar_actions,
            text="Cancel",
            width=65,
            height=24,
            fg_color="#3A3D47",
            hover_color=TAPO_RED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            state="disabled",
            command=self._on_cancel_download
        )
        self.btn_cancel_dl.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bar_actions,
            text="📁 Change Folder...",
            width=120,
            height=24,
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            command=self._on_choose_folder
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bar_actions,
            text="📂 Open Folder",
            width=95,
            height=24,
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            command=self._on_open_recordings_folder
        ).pack(side="left", padx=(0, 8))

        # About Button (Bottom Right)
        ctk.CTkButton(
            bar_actions,
            text="ℹ️ About",
            width=70,
            height=24,
            fg_color=TAPO_BLUE,
            hover_color=TAPO_BLUE_HOVER,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            command=self._open_about_dialog
        ).pack(side="left")

        # Bottom row: Progress Bar (greyed out when idle/failed)
        self.progress_bar = ctk.CTkProgressBar(progress_inner, progress_color="#2B2D35", height=8)
        self.progress_bar.pack(fill="x", pady=(2, 0))
        self.progress_bar.set(0)

    # =========================================================================
    # CONNECTION LOGIC & TRANSITION TO DASHBOARD
    # =========================================================================
    def _on_connect_clicked(self):
        host = self.entry_ip.get().strip()
        user = self.entry_user.get().strip()
        password = self.entry_pass.get()
        cloud_pass = self.entry_cloud_pass.get().strip() if self.var_show_cloud_pass.get() else password

        if not host:
            self._show_login_status("Please enter the camera IP address (e.g. 192.168.0.103).", is_error=True)
            return
        if not user:
            self._show_login_status("Please enter the Camera Account username.", is_error=True)
            return
        if not password:
            self._show_login_status("Please enter the Camera Account password.", is_error=True)
            return

        self.btn_connect.configure(state="disabled", text="⏳ Connecting to Camera...")
        self.lbl_login_status.configure(text="Authenticating with camera and MicroSD storage...", text_color=TAPO_BLUE)
        self.login_progress.pack(fill="x", padx=24, pady=(0, 10))
        self.login_progress.start()

        def _worker():
            try:
                # 1. Connect RTSP and Cloud/SD Management unified
                self.backend.connect(
                    host=host,
                    username=user,
                    password=password,
                    cloud_password=cloud_pass
                )
                cloud_info = self.backend.get_camera_details()
                dates = self.backend.get_dates_with_recordings()
                self.after(0, lambda: self._on_connect_success(host, user, password, cloud_pass, cloud_info, dates))
            except Exception as e:
                err_str = str(e)
                self.after(0, lambda: self._on_connect_failed("ERR_CONNECT_FAILED", f"Connection failed: {err_str}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_connect_success(self, host: str, user: str, password: str, cloud_pass: str, cloud_info: dict, dates: List[str]):
        self.login_progress.stop()
        self.login_progress.pack_forget()
        self.btn_connect.configure(state="normal", text="⚡ Connect Camera")

        # Persist non-secret preferences.
        self.config["host"] = host
        self.config["username"] = user
        self.config["save_credentials"] = (
            self.var_save_creds.get()
        )

        try:
            if self.var_save_creds.get():
                save_credentials(
                    host=host,
                    username=user,
                    camera_password=password,
                    cloud_password=(
                        cloud_pass
                        if self.var_show_cloud_pass.get()
                        else None
                    ),
                )
            else:
                delete_credentials(host, user)

        except Exception as exc:
            self.config["save_credentials"] = False
            save_config(self.config)

            self._show_error_dialog(
                "ERR_CREDENTIAL_STORE",
                "Credential Storage Error",
                "The camera connection succeeded, but Windows "
                f"Credential Manager could not update the saved "
                f"credentials.\n\n{exc}",
            )

        save_config(self.config)

        # Update Dashboard Device Card
        dev_info = cloud_info.get("device_info", {})
        if isinstance(dev_info, dict) and "device_info" in dev_info:
            dev_info = dev_info["device_info"]
        basic_info = dev_info.get("basic_info", {}) if isinstance(dev_info, dict) else {}
        model = basic_info.get("device_model", "Tapo Camera")
        alias = basic_info.get("device_alias", "")
        alias_str = f" ({alias})" if alias else ""
        self.lbl_device_model.configure(text=f"{model}{alias_str}")
        self.lbl_device_ip.configure(text=f"Host: {host} • Port 554/443")

        # Populate calendar with recording dates
        self.available_dates = dates
        self.calendar_widget.set_recording_dates(dates)

        # Refresh media player selection dropdown
        self._update_player_menu_selection()

        # Switch screen to Dashboard!
        self._show_dashboard_screen()

        # Load recordings for active date
        self._load_recordings_for_date(self.selected_date)

    def _on_connect_failed(self, code: str, msg: str):
        self.login_progress.stop()
        self.login_progress.pack_forget()
        self.btn_connect.configure(state="normal", text="⚡ Connect Camera")
        self._show_login_status(f"[{code}] {msg}", is_error=True)

    def _show_login_status(self, msg: str, is_error: bool = False):
        color = TAPO_RED if is_error else TAPO_BLUE
        self.lbl_login_status.configure(text=msg, text_color=color)

    def _on_disconnect_clicked(self):
        if hasattr(self, "live_player"):
            self.live_player.stop()

        self.backend.disconnect()
        self.all_recordings = []
        self.filtered_recordings = []
        self.available_dates = []
        self._show_login_screen()

    # =========================================================================
    # MEDIA PLAYER PREFERENCES & LIVE FEED
    # =========================================================================
    def _get_player_options(self) -> List[str]:
        available = self.backend.get_available_players()
        options = []

        # Determine auto name
        auto_name = "Auto-Detect"
        for candidate in ["mpv.net", "PotPlayer", "VLC", "FFplay (Built-in)"]:
            if candidate in available:
                auto_name = f"Auto ({candidate})"
                break
        options.append(auto_name)

        for name in ["mpv.net", "PotPlayer", "VLC", "FFplay (Built-in)", "System Default (.m3u)"]:
            if name in available and name not in options:
                options.append(name)

        custom_path = self.config.get("custom_player_path", "")
        if custom_path and os.path.exists(custom_path):
            exe_name = os.path.basename(custom_path)
            options.append(f"Custom: {exe_name}")

        options.append("Browse for Player (.exe)...")
        return options

    def _update_player_menu_selection(self):
        opts = self._get_player_options()
        self.opt_media_player.configure(values=opts)

        pref = self.config.get("preferred_player", "auto")
        if pref == "auto":
            self.opt_media_player.set(opts[0])
        elif pref == "custom":
            custom_path = self.config.get("custom_player_path", "")
            if custom_path and os.path.exists(custom_path):
                exe_name = os.path.basename(custom_path)
                matching = [o for o in opts if o.startswith(f"Custom: {exe_name}")]
                self.opt_media_player.set(matching[0] if matching else opts[0])
            else:
                self.opt_media_player.set(opts[0])
        elif pref in opts:
            self.opt_media_player.set(pref)
        else:
            self.opt_media_player.set(opts[0])

    def _on_player_selection_changed(self, choice: str):
        if choice == "Browse for Player (.exe)...":
            file_path = filedialog.askopenfilename(
                title="Select Media Player Executable",
                filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
            )
            if file_path and os.path.exists(file_path):
                self.config["custom_player_path"] = file_path
                self.config["preferred_player"] = "custom"
                save_config(self.config)
                self._update_player_menu_selection()
            else:
                self._update_player_menu_selection()
            return

        if choice.startswith("Auto"):
            self.config["preferred_player"] = "auto"
        elif choice.startswith("Custom:"):
            self.config["preferred_player"] = "custom"
        else:
            self.config["preferred_player"] = choice
        save_config(self.config)

    def _on_launch_live_stream(self):
        try:
            quality = self.config.get(
                "live_stream_quality",
                "HD",
            )
            stream_url = self.backend.get_live_stream_url(
                quality=quality
            )
            self.live_player.play_url(stream_url)

        except Exception as exc:
            self._show_error_dialog(
                "ERR_EMBEDDED_PLAYER",
                "Live Stream Error",
                f"Could not start the embedded live stream:\n\n{exc}",
                action=(
                    "Confirm that the camera is connected, RTSP is enabled, "
                    "and the bundled LibVLC runtime is present. You can also "
                    "use the external-player fallback."
                ),
            )

    def _on_launch_live_stream_external(self):
        try:
            player_pref = self.config.get(
                "preferred_player",
                "auto",
            )
            custom_path = self.config.get(
                "custom_player_path"
            )

            self.backend.launch_live_stream_player(
                player_choice=player_pref,
                custom_path=custom_path,
            )

        except Exception as exc:
            self._show_error_dialog(
                "ERR_EXTERNAL_PLAYER",
                "External Player Error",
                f"Could not launch an external player:\n\n{exc}",
            )

    def _on_live_quality_changed(self, quality: str):
        self.config["live_stream_quality"] = quality
        save_config(self.config)

        if self.backend.is_rtsp_connected:
            try:
                stream_url = self.backend.get_live_stream_url(
                    quality=quality
                )
                self.live_player.play_url(stream_url)
            except Exception as exc:
                self._show_error_dialog(
                    "ERR_STREAM_QUALITY",
                    "Stream Quality Error",
                    f"Could not switch to {quality} quality:\n\n{exc}",
                )

    def _on_live_player_status(
        self,
        status_text: str,
        _status_color: str,
    ):
        if hasattr(self, "btn_live_stream"):
            if status_text == "Live":
                self.btn_live_stream.configure(
                    text="● Embedded Feed Active",
                    fg_color=TAPO_GREEN,
                )
            else:
                self.btn_live_stream.configure(
                    text="▶ Start Embedded Live Feed",
                    fg_color=TAPO_BLUE,
                )

    # =========================================================================
    # CALENDAR & DATE SELECTION
    # =========================================================================
    def _on_calendar_date_selected(self, date_str: str):
        self._select_date(date_str)

    def _select_date(self, date_str: str):
        self.selected_date = date_str
        self.lbl_active_date.configure(text=f"📅 {date_str}")
        self.calendar_widget.set_selected_date(date_str)

        if self.backend.is_cloud_connected:
            self._load_recordings_for_date(date_str)

    def _on_refresh_sd_clicked(self):
        if not self.backend.is_cloud_connected:
            self._show_error_dialog("ERR_NOT_CONNECTED", "Camera Disconnected", "Please connect to the camera first.")
            return

        self.btn_refresh.configure(state="disabled", text="⏳ Refreshing...")

        def _worker():
            try:
                dates = self.backend.get_dates_with_recordings()
                self.available_dates = dates
                self.after(0, lambda: self.calendar_widget.set_recording_dates(dates))
                self.after(0, lambda: self._load_recordings_for_date(self.selected_date))
            except Exception as e:
                self.after(0, lambda: self._show_error_dialog("ERR_REFRESH_FAILED", "Refresh Failed", f"Could not refresh SD card: {e}"))
            finally:
                self.after(0, lambda: self.btn_refresh.configure(state="normal", text="🔄 Refresh SD Card"))

        threading.Thread(target=_worker, daemon=True).start()

    # =========================================================================
    # LOADING SCREEN & JITTER-FREE BATCH RENDERING
    # =========================================================================
    def _show_loading_screen(self, date_str: str):
        for widget in self.scroll_recordings.winfo_children():
            widget.destroy()

        loading_frame = ctk.CTkFrame(self.scroll_recordings, fg_color="transparent")
        loading_frame.pack(pady=100)

        ctk.CTkLabel(
            loading_frame,
            text="🔄",
            font=ctk.CTkFont(family=FONT_FAMILY, size=36)
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            loading_frame,
            text=f"Loading Recordings for {date_str}...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color="#FFFFFF"
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            loading_frame,
            text="Reading timeline index from camera MicroSD card...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TAPO_TEXT_MUTED
        ).pack(pady=(0, 16))

        pb = ctk.CTkProgressBar(loading_frame, width=280, progress_color=TAPO_BLUE, mode="indeterminate")
        pb.pack()
        pb.start()

    def _load_recordings_for_date(self, date_str: str):
        self._show_loading_screen(date_str)
        self.lbl_recordings_summary.configure(text=f"Loading events for {date_str}...")
        self.lbl_total_duration.configure(text="")

        output_dir = self.config.get("output_dir", "")

        def _worker():
            try:
                recs = self.backend.get_recordings(date_str, output_dir=output_dir)
                self.after(0, lambda: self._on_recordings_loaded(recs))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._on_recordings_load_failed(err_msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_recordings_loaded(self, recs: List[Dict[str, Any]]):
        self.all_recordings = recs
        self._apply_filter_and_render(reset_pagination=True)

    def _on_recordings_load_failed(self, err_msg: str):
        self._show_empty_placeholder(f"Could not load recordings for this date.\n\nError: {err_msg}")
        self.lbl_recordings_summary.configure(text="Error loading events")

    def _on_filter_changed(self, value: str):
        self.active_filter = value.lower()
        self._apply_filter_and_render(reset_pagination=True)

    def _apply_filter_and_render(self, reset_pagination: bool = False):
        if not self.all_recordings:
            self._show_empty_placeholder("No recordings found on the SD card for this date.")
            self.lbl_recordings_summary.configure(text="Detected Events (0)")
            self.lbl_total_duration.configure(text="")
            return

        if self.active_filter == "motion":
            self.filtered_recordings = [r for r in self.all_recordings if r["is_motion"]]
        elif self.active_filter == "continuous":
            self.filtered_recordings = [r for r in self.all_recordings if not r["is_motion"]]
        else:
            self.filtered_recordings = self.all_recordings

        total_secs = sum(r["duration_sec"] for r in self.filtered_recordings)
        dur_str = self.backend._format_duration(total_secs)

        count = len(self.filtered_recordings)
        self.lbl_recordings_summary.configure(text=f"Detected Events ({count})")
        self.lbl_total_duration.configure(text=f"Total Duration: {dur_str}")

        if reset_pagination:
            self.rendered_count = 0
            for widget in self.scroll_recordings.winfo_children():
                widget.destroy()

        self._render_next_batch()

    def _render_next_batch(self):
        start_idx = self.rendered_count
        end_idx = min(start_idx + self.BATCH_SIZE, len(self.filtered_recordings))

        if start_idx == 0 and not self.filtered_recordings:
            self._show_empty_placeholder("No events match the active filter.")
            return

        # Remove existing 'Load More' button
        if hasattr(self, "load_more_btn") and self.load_more_btn and self.load_more_btn.winfo_exists():
            self.load_more_btn.destroy()

        for idx in range(start_idx, end_idx):
            rec = self.filtered_recordings[idx]
            self._render_event_card(rec)

        self.rendered_count = end_idx

        # Show 'Load More' button if more items remain
        if self.rendered_count < len(self.filtered_recordings):
            remaining = len(self.filtered_recordings) - self.rendered_count
            self.load_more_btn = ctk.CTkButton(
                self.scroll_recordings,
                text=f"▼ Load More Events ({remaining} remaining)...",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                fg_color="#272A32",
                hover_color=TAPO_CARD_HOVER,
                height=36,
                command=self._render_next_batch
            )
            self.load_more_btn.pack(fill="x", padx=12, pady=10)

    def _refresh_rendered_cards(self):
        target_count = max(self.BATCH_SIZE, self.rendered_count)
        self.rendered_count = 0
        for widget in self.scroll_recordings.winfo_children():
            widget.destroy()

        end_idx = min(target_count, len(self.filtered_recordings))
        for idx in range(0, end_idx):
            rec = self.filtered_recordings[idx]
            self._render_event_card(rec)

        self.rendered_count = end_idx

        if self.rendered_count < len(self.filtered_recordings):
            remaining = len(self.filtered_recordings) - self.rendered_count
            self.load_more_btn = ctk.CTkButton(
                self.scroll_recordings,
                text=f"▼ Load More Events ({remaining} remaining)...",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                fg_color="#272A32",
                hover_color=TAPO_CARD_HOVER,
                height=36,
                command=self._render_next_batch
            )
            self.load_more_btn.pack(fill="x", padx=12, pady=10)

    def _render_event_card(self, rec: Dict[str, Any]):
        card = ctk.CTkFrame(
            self.scroll_recordings,
            corner_radius=10,
            fg_color="#18191E",
            border_width=1,
            border_color="#252730"
        )
        card.pack(fill="x", padx=10, pady=5)

        # Left: Thumbnail Container with Duration Pill
        thumb_frame = ctk.CTkFrame(card, width=95, height=54, corner_radius=6, fg_color="#101114")
        thumb_frame.pack_propagate(False)
        thumb_frame.pack(side="left", padx=12, pady=10)

        icon_text = "🏃" if rec["is_motion"] else "⏱️"
        ctk.CTkLabel(thumb_frame, text=icon_text, font=ctk.CTkFont(family=FONT_FAMILY, size=20)).place(relx=0.5, rely=0.4, anchor="center")

        dur_pill = ctk.CTkLabel(
            thumb_frame,
            text=rec["duration_str"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=9, weight="bold"),
            fg_color="#000000",
            corner_radius=4,
            padx=4,
            pady=1
        )
        dur_pill.place(relx=0.92, rely=0.9, anchor="se")

        # Center: Timestamp & Event Metadata
        center_frame = ctk.CTkFrame(card, fg_color="transparent")
        center_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            center_frame,
            text=rec["start_str"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w")

        detail_row = ctk.CTkFrame(center_frame, fg_color="transparent")
        detail_row.pack(anchor="w", pady=(2, 0))

        type_color = TAPO_AMBER if rec["is_motion"] else TAPO_BLUE
        ctk.CTkLabel(
            detail_row,
            text=f"● {rec['type_label']}  (➔ {rec['end_str']})",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=type_color
        ).pack(side="left", padx=(0, 8))

        if rec["is_downloaded"]:
            ctk.CTkLabel(
                detail_row,
                text="✓ Saved on PC",
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                text_color="#2ECC71",
                fg_color="#123821",
                corner_radius=6,
                padx=8,
                pady=2
            ).pack(side="left")

        # Right: Action Buttons (Play & Download)
        action_frame = ctk.CTkFrame(card, fg_color="transparent")
        action_frame.pack(side="right", padx=14, pady=10)

        play_bg = TAPO_GREEN if rec["is_downloaded"] else TAPO_BLUE
        play_hover = "#27AE60" if rec["is_downloaded"] else TAPO_BLUE_HOVER

        btn_play = ctk.CTkButton(
            action_frame,
            text="▶ Play",
            width=78,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=play_bg,
            hover_color=play_hover,
            corner_radius=6,
            command=lambda r=rec: self._on_play_clicked(r)
        )
        btn_play.pack(side="left", padx=(0, 8))

        dl_text = "⬇ Re-download" if rec["is_downloaded"] else "⬇ Download"
        btn_dl = ctk.CTkButton(
            action_frame,
            text=dl_text,
            width=105 if rec["is_downloaded"] else 90,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="#2B2D35",
            hover_color=TAPO_CARD_HOVER,
            corner_radius=6,
            command=lambda r=rec: self._on_download_clicked(r)
        )
        btn_dl.pack(side="left")

    def _show_empty_placeholder(self, text: str):
        for widget in self.scroll_recordings.winfo_children():
            widget.destroy()

        placeholder = ctk.CTkLabel(
            self.scroll_recordings,
            text=text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            text_color=TAPO_TEXT_MUTED,
            justify="center"
        )
        placeholder.pack(pady=70)

    # =========================================================================
    # DOWNLOAD & PLAYBACK (Works On Any Drive/Folder, Remuxes Cleanly)
    # =========================================================================
    def _on_play_clicked(self, rec: Dict[str, Any]):
        if (
            rec["is_downloaded"] and
            os.path.exists(rec["file_path"])
        ):
            try:
                self.live_player.play_file(rec["file_path"])

            except Exception as embedded_error:
                try:
                    player_pref = self.config.get(
                        "preferred_player",
                        "auto",
                    )
                    custom_path = self.config.get(
                        "custom_player_path",
                    )

                    self.backend.play_file(
                        rec["file_path"],
                        player_choice=player_pref,
                        custom_path=custom_path,
                    )

                except Exception as external_error:
                    self._show_error_dialog(
                        "ERR_PLAYBACK",
                        "Playback Error",
                        "Neither the embedded player nor the external "
                        "fallback could open the recording.\n\n"
                        f"Embedded player: {embedded_error}\n"
                        f"External player: {external_error}",
                    )
        else:
            self.auto_play_target = rec["file_path"]
            self._start_download(rec)

    def _on_download_clicked(self, rec: Dict[str, Any]):
        self.auto_play_target = None
        self._start_download(rec)

    def _set_progress_bar_idle(self):
        self.progress_bar.configure(progress_color="#2B2D35")
        self.progress_bar.set(0)

    def _set_progress_bar_active(self, percent: float):
        self.progress_bar.configure(progress_color=TAPO_BLUE)
        self.progress_bar.set(percent)

    def _set_progress_bar_complete(self):
        self.progress_bar.configure(progress_color=TAPO_GREEN)
        self.progress_bar.set(1.0)

    def _start_download(self, rec: Dict[str, Any]):
        if self.active_download_thread and self.active_download_thread.is_alive():
            self._show_error_dialog("ERR_DOWNLOAD_BUSY", "Download Busy", "Another clip is currently downloading. Please wait or cancel the active download.")
            return

        self.btn_cancel_dl.configure(state="normal")
        self._set_progress_bar_active(0.0)
        self.lbl_download_title.configure(text=f"📥 Downloading: {rec['start_str']} - {rec['end_str']}")

        output_dir = self.config.get("output_dir", "")

        def _progress_cb(status: dict):
            self.after(0, lambda: self._update_download_progress(status))

        def _worker():
            try:
                file_path = self.backend.download_clip_sync(
                    recording=rec,
                    output_dir=output_dir,
                    progress_cb=_progress_cb
                )
                self.after(0, lambda: self._on_download_complete(rec, file_path))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._on_download_error(err_msg))

        self.active_download_thread = threading.Thread(target=_worker, daemon=True)
        self.active_download_thread.start()

    def _update_download_progress(self, status: dict):
        percent = status.get("percent", 0.0)
        text = status.get("status_text", "")
        self._set_progress_bar_active(percent)
        pct_display = f"{int(percent * 100)}%"
        self.lbl_download_title.configure(text=f"📥 {text} ({pct_display})")

    def _on_download_complete(self, rec: Dict[str, Any], file_path: str):
        self.btn_cancel_dl.configure(state="disabled")
        self._set_progress_bar_complete()
        self.lbl_download_title.configure(text=f"✓ Download complete: {os.path.basename(file_path)}")

        rec["is_downloaded"] = True
        rec["file_path"] = file_path
        self._refresh_rendered_cards()

        should_auto_play = bool(
            self.config.get(
                "auto_play_after_download",
                True,
            )
        )

        if (
            should_auto_play and
            self.auto_play_target and
            os.path.exists(file_path)
        ):
            self.auto_play_target = None

            try:
                self.live_player.play_file(file_path)
            except Exception as exc:
                print(f"Embedded auto-play warning: {exc}")

    def _on_download_error(self, err_msg: str):
        self.btn_cancel_dl.configure(state="disabled")
        self._set_progress_bar_idle()
        self.lbl_download_title.configure(text="Download failed or cancelled")
        self._show_error_dialog("ERR_DOWNLOAD_FAILED", "Download Error", f"Clip download failed:\n\n{err_msg}")

    def _on_cancel_download(self):
        self.backend.cancel_download()
        self.btn_cancel_dl.configure(state="disabled")
        self._set_progress_bar_idle()
        self.lbl_download_title.configure(text="Cancelling download...")

    # =========================================================================
    # FOLDER UTILITIES (Place Recordings Anywhere on Any Drive)
    # =========================================================================
    def _on_choose_folder(self):
        current_dir = self.config.get("output_dir", "")
        folder = filedialog.askdirectory(initialdir=current_dir, title="Select Recordings Storage Folder")
        if folder:
            # Verify write access to user's chosen directory
            try:
                os.makedirs(folder, exist_ok=True)
                test_file = os.path.join(folder, ".tapo_write_test")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
            except Exception as e:
                self._show_error_dialog(
                    "ERR_STORAGE_PERM",
                    "Storage Access Error",
                    f"Cannot write to chosen directory:\n{folder}\n\nError: {e}\n\nPlease choose a different folder."
                )
                return

            self.config["output_dir"] = folder
            save_config(self.config)
            self.lbl_folder_path.configure(text=folder)

            # Re-evaluate all loaded recordings against newly selected folder
            for rec in self.all_recordings:
                base_name = os.path.splitext(rec["file_name"])[0]
                mp4_path = os.path.join(folder, f"{base_name}.mp4")
                ts_path = os.path.join(folder, f"{base_name}.ts")
                if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 1024:
                    rec["file_path"] = mp4_path
                    rec["is_downloaded"] = True
                elif os.path.exists(ts_path) and os.path.getsize(ts_path) > 1024:
                    rec["file_path"] = ts_path
                    rec["is_downloaded"] = True
                else:
                    rec["file_path"] = mp4_path
                    rec["is_downloaded"] = False

            self._refresh_rendered_cards()

    def _on_open_recordings_folder(self):
        folder = self.config.get("output_dir", "")
        if not folder:
            from config_manager import APP_DIR
            folder = os.path.join(APP_DIR, "recordings")
        os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    # =========================================================================
    # DIALOGS & LIFECYCLE
    # =========================================================================
    def _open_about_dialog(self):
        AboutDialog(self)

    def _show_error_dialog(self, code: str, title: str, explanation: str, action: str = ""):
        msg = f"[{code}] {explanation}"
        if action:
            msg += f"\n\nSuggested Fix:\n{action}"
        messagebox.showerror(f"{title} ({code})", msg)

    def _validate_runtime_dependencies(self):
        status = self.backend.get_runtime_dependency_status()

        missing = []

        if not status["ffmpeg_available"]:
            missing.append("FFmpeg")

        if not status["ffprobe_available"]:
            missing.append("FFprobe")

        if missing:
            self._show_error_dialog(
                "ERR_RUNTIME_DEPENDENCY",
                "Installation Incomplete",
                "The following application components are missing:\n\n"
                + "\n".join(f"• {item}" for item in missing),
                action=(
                    "Reinstall Tapo-Viewer or restore the files under "
                    "vendor\\ffmpeg."
                ),
            )

    def _on_close(self):
        try:
            if hasattr(self, "live_player"):
                self.config["live_stream_volume"] = (
                    self.live_player.get_volume()
                )
                self.config["live_stream_muted"] = (
                    self.live_player.is_muted()
                )
                self.live_player.close()

            save_config(self.config)

        finally:
            self.backend.disconnect()
            self.destroy()


if __name__ == "__main__":
    app = TapoViewerApp()
    app.mainloop()
