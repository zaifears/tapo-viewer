import os
import sys
import webbrowser
import customtkinter as ctk
from PIL import Image

def get_bundle_dir() -> str:
    """Returns directory of bundled assets (sys._MEIPASS if PyInstaller frozen, else script dir)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.abspath(__file__))

TAPO_BLUE = "#00A4E4"
TAPO_DARK_BG = "#121316"
CARD_BG = "#1C1D22"
CARD_HOVER = "#25272F"
TEXT_MUTED = "#8E929C"
TEXT_WHITE = "#FFFFFF"
FONT_FAMILY = "Segoe UI"


class AboutDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.title("About Tapo-Viewer")
        self.geometry("480x700")
        self.minsize(440, 600)
        self.configure(fg_color=TAPO_DARK_BG)

        # Modal focus
        self.transient(parent)
        self.grab_set()

        # Center on parent window
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 240
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 350
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header with Logo + Title
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        logo_path = os.path.join(get_bundle_dir(), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path).resize((48, 48), Image.Resampling.LANCZOS)
                logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(48, 48))
                ctk.CTkLabel(header_frame, image=logo_ctk, text="").pack(side="left", padx=(0, 12))
            except Exception:
                pass

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            title_box,
            text="Tapo-Viewer",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=TEXT_WHITE
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="v1.0.1 Desktop Edition",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=TAPO_BLUE
        ).pack(anchor="w")

        ctk.CTkLabel(
            container,
            text="100% Local & Private. All camera feeds, motion events, and SD card recordings stay strictly on your local home network.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TEXT_MUTED,
            wraplength=420,
            justify="left"
        ).pack(anchor="w", pady=(0, 18))

        # =====================================================================
        # DEVELOPER SECTION
        # =====================================================================
        ctk.CTkLabel(
            container,
            text="DEVELOPER",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=TAPO_BLUE
        ).pack(anchor="w", pady=(0, 8))

        dev_card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12)
        dev_card.pack(fill="x", pady=(0, 18))

        # Avatar + Name Profile Row
        profile_row = ctk.CTkFrame(dev_card, fg_color="transparent")
        profile_row.pack(fill="x", padx=16, pady=14)

        # Load avatar image if available
        avatar_path = os.path.join(get_bundle_dir(), "assets", "avatar_circle.png")
        if not os.path.exists(avatar_path):
            avatar_path = os.path.join(get_bundle_dir(), "assets", "headshot.png")

        if os.path.exists(avatar_path):
            try:
                pil_img = Image.open(avatar_path)
                avatar_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(52, 52))
                ctk.CTkLabel(profile_row, image=avatar_ctk, text="").pack(side="left", padx=(0, 14))
            except Exception:
                ctk.CTkLabel(profile_row, text="👤", font=ctk.CTkFont(family=FONT_FAMILY, size=30)).pack(side="left", padx=(0, 14))
        else:
            ctk.CTkLabel(profile_row, text="👤", font=ctk.CTkFont(family=FONT_FAMILY, size=30)).pack(side="left", padx=(0, 14))

        name_box = ctk.CTkFrame(profile_row, fg_color="transparent")
        name_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            name_box,
            text="Shahoriar Hossain",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=TEXT_WHITE
        ).pack(anchor="w")

        ctk.CTkLabel(
            name_box,
            text="zaifears",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        # Divider
        ctk.CTkFrame(dev_card, height=1, fg_color="#272A32").pack(fill="x", padx=16)

        # Link Item: GitHub
        self._create_link_row(
            parent=dev_card,
            icon="< / >",
            title="GitHub",
            subtitle="github.com/zaifears/tapo-viewer",
            url="https://github.com/zaifears/tapo-viewer"
        )

        ctk.CTkFrame(dev_card, height=1, fg_color="#272A32").pack(fill="x", padx=16)

        # Link Item: Buy me a coffee
        self._create_link_row(
            parent=dev_card,
            icon="☕",
            title="Buy me a coffee",
            subtitle="shahoriar.bd/thanks",
            url="https://shahoriar.bd/thanks"
        )

        # =====================================================================
        # OPEN SOURCE LIBRARIES & ECOSYSTEM CREDITS
        # =====================================================================
        ctk.CTkLabel(
            container,
            text="OPEN SOURCE LIBRARIES & CREDITS",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=TAPO_BLUE
        ).pack(anchor="w", pady=(0, 8))

        credits_card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12)
        credits_card.pack(fill="x", pady=(0, 18))

        credit_intro = (
            "Tapo-Viewer's source code is licensed under the MIT License.\n\n"
            "The app icon, logo, and brand remain © Shahoriar Hossain, all rights reserved.\n"
            "Built with the power of the following open-source projects:"
        )
        ctk.CTkLabel(
            credits_card,
            text=credit_intro,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TEXT_MUTED,
            wraplength=400,
            justify="left"
        ).pack(anchor="w", padx=16, pady=(14, 10))

        # Divider
        ctk.CTkFrame(credits_card, height=1, fg_color="#272A32").pack(fill="x", padx=16)

        # Link 1: PyTapo
        self._create_link_row(
            parent=credits_card,
            icon="📡",
            title="PyTapo",
            subtitle="Tapo camera protocol & SD downloader (v3.4.26)",
            url="https://github.com/JurajNyiri/pytapo"
        )

        ctk.CTkFrame(credits_card, height=1, fg_color="#272A32").pack(fill="x", padx=16)

        # Link 2: CustomTkinter
        self._create_link_row(
            parent=credits_card,
            icon="🎨",
            title="CustomTkinter",
            subtitle="Modern, customizable Tkinter UI design framework",
            url="https://github.com/TomSchimansky/CustomTkinter"
        )

        ctk.CTkFrame(credits_card, height=1, fg_color="#272A32").pack(fill="x", padx=16)

        # Link 3: FFmpeg
        self._create_link_row(
            parent=credits_card,
            icon="🎬",
            title="FFmpeg",
            subtitle="Cross-platform multimedia streaming & remuxing engine",
            url="https://ffmpeg.org"
        )

        ctk.CTkFrame(credits_card, height=1, fg_color="#272A32").pack(fill="x", padx=16)

        # Link 4: Python
        self._create_link_row(
            parent=credits_card,
            icon="🐍",
            title="Python",
            subtitle="Core language runtime and asynchronous architecture",
            url="https://www.python.org"
        )

        # =====================================================================
        # FREE PALESTINE SOLIDARITY CARD
        # =====================================================================
        palestine_card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12)
        palestine_card.pack(fill="x", pady=(0, 10))

        palestine_img_path = os.path.join(get_bundle_dir(), "assets", "free_palestine.png")
        if os.path.exists(palestine_img_path):
            try:
                pil_pal = Image.open(palestine_img_path)
                w, h = pil_pal.size
                target_w = 400
                target_h = int(h * (target_w / w))
                ctk_pal = ctk.CTkImage(light_image=pil_pal, dark_image=pil_pal, size=(target_w, target_h))
                lbl_img = ctk.CTkLabel(palestine_card, image=ctk_pal, text="")
                lbl_img.pack(padx=12, pady=12)
            except Exception as e:
                print(f"Error loading free_palestine image: {e}")
                ctk.CTkLabel(
                    palestine_card,
                    text="FREE PALESTINE 🇵🇸",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
                    text_color="#2ECC71"
                ).pack(pady=16)
        else:
            ctk.CTkLabel(
                palestine_card,
                text="FREE PALESTINE 🇵🇸",
                font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
                text_color="#2ECC71"
            ).pack(pady=16)

    def _create_link_row(self, parent, icon: str, title: str, subtitle: str, url: str):
        row = ctk.CTkFrame(parent, fg_color="transparent", cursor="hand2")
        row.pack(fill="x", padx=16, pady=8)

        # Icon box
        ctk.CTkLabel(
            row,
            text=icon,
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=TAPO_BLUE,
            width=28
        ).pack(side="left", padx=(0, 10))

        # Title & Subtitle
        text_box = ctk.CTkFrame(row, fg_color="transparent")
        text_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            text_box,
            text=title,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=TEXT_WHITE
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_box,
            text=subtitle,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        # External Link Arrow icon
        ctk.CTkLabel(
            row,
            text="↗",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=TEXT_MUTED
        ).pack(side="right", padx=(8, 0))

        # Click handler
        row.bind("<Button-1>", lambda e: webbrowser.open(url))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e: webbrowser.open(url))
            for sub in child.winfo_children():
                sub.bind("<Button-1>", lambda e: webbrowser.open(url))
