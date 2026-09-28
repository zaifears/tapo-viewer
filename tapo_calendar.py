import calendar
import datetime
from typing import Callable, Optional, Set, List
import customtkinter as ctk

# Tapo Brand Palette & Typography
TAPO_BLUE = "#00A4E4"
TAPO_BLUE_HOVER = "#0088BF"
BG_DARK = "#16171B"
CARD_BG = "#1F2127"
TEXT_MUTED = "#6C707C"
TEXT_WHITE = "#FFFFFF"
DOT_COLOR = "#00A4E4"
FONT_FAMILY = "Segoe UI"


class TapoCalendar(ctk.CTkFrame):
    """
    A Tapo-authentic monthly calendar widget.
    Highlights available recording days with a signature Tapo Blue dot.
    Highlights the active selected day in a solid Tapo Blue circular badge.
    Uses Segoe UI for crisp TrueType numerals without Windows bitmap font distortions.
    """
    def __init__(
        self,
        master,
        on_date_selected: Optional[Callable[[str], None]] = None,
        initial_date: Optional[str] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=CARD_BG, corner_radius=12, **kwargs)

        self.on_date_selected = on_date_selected
        self.recording_dates: Set[str] = set()

        # Parse initial date
        today = datetime.date.today()
        if initial_date:
            try:
                parts = [int(p) for p in initial_date.split("-")]
                self.current_year = parts[0]
                self.current_month = parts[1]
                self.selected_date = initial_date
            except Exception:
                self.current_year = today.year
                self.current_month = today.month
                self.selected_date = today.strftime("%Y-%m-%d")
        else:
            self.current_year = today.year
            self.current_month = today.month
            self.selected_date = today.strftime("%Y-%m-%d")

        self._build_ui()
        self.render_month()

    def _build_ui(self):
        # 1. Header Bar: < 2026-09 > and SD Card Badge
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=16, pady=(14, 10))

        nav_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        nav_box.pack(side="left")

        self.btn_prev = ctk.CTkButton(
            nav_box,
            text="‹",
            width=28,
            height=28,
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            fg_color="transparent",
            hover_color="#2B2D35",
            command=self._prev_month
        )
        self.btn_prev.pack(side="left", padx=(0, 6))

        self.lbl_month_year = ctk.CTkLabel(
            nav_box,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=TEXT_WHITE
        )
        self.lbl_month_year.pack(side="left", padx=4)

        self.btn_next = ctk.CTkButton(
            nav_box,
            text="›",
            width=28,
            height=28,
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            fg_color="transparent",
            hover_color="#2B2D35",
            command=self._next_month
        )
        self.btn_next.pack(side="left", padx=(6, 0))

        # SD Storage Badge on right (like Tapo app toggle)
        badge_box = ctk.CTkFrame(self.header_frame, fg_color="#121316", corner_radius=16)
        badge_box.pack(side="right")

        self.lbl_sd_badge = ctk.CTkLabel(
            badge_box,
            text="💾 MicroSD",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=TAPO_BLUE,
            padx=10,
            pady=3
        )
        self.lbl_sd_badge.pack()

        # 2. Weekdays Header: S M T W T F S
        self.weekdays_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.weekdays_frame.pack(fill="x", padx=12, pady=(0, 6))

        weekdays = ["S", "M", "T", "W", "T", "F", "S"]
        for col_idx, day_name in enumerate(weekdays):
            lbl = ctk.CTkLabel(
                self.weekdays_frame,
                text=day_name,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                text_color=TEXT_MUTED
            )
            lbl.grid(row=0, column=col_idx, sticky="ew", padx=2, pady=2)
            self.weekdays_frame.grid_columnconfigure(col_idx, weight=1)

        # 3. Days Grid Frame
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        for c in range(7):
            self.grid_frame.grid_columnconfigure(c, weight=1)

    def set_recording_dates(self, dates: List[str]):
        """
        Pass list of 'YYYY-MM-DD' dates. Dots will appear beneath these dates.
        """
        self.recording_dates = set(dates)
        self.render_month()

    def set_selected_date(self, date_str: str):
        self.selected_date = date_str
        try:
            parts = [int(p) for p in date_str.split("-")]
            self.current_year = parts[0]
            self.current_month = parts[1]
        except Exception:
            pass
        self.render_month()

    def _prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.render_month()

    def _next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.render_month()

    def render_month(self):
        # Update Month Year Header
        month_str = f"{self.current_year:04d}-{self.current_month:02d}"
        self.lbl_month_year.configure(text=month_str)

        # Clear existing cells
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)

        for row_idx, week in enumerate(month_days):
            for col_idx, day_num in enumerate(week):
                if day_num == 0:
                    # Empty spacer cell
                    spacer = ctk.CTkLabel(self.grid_frame, text="", height=40)
                    spacer.grid(row=row_idx, column=col_idx, padx=1, pady=2, sticky="nsew")
                    continue

                date_str = f"{self.current_year:04d}-{self.current_month:02d}-{day_num:02d}"
                has_recording = date_str in self.recording_dates
                is_selected = date_str == self.selected_date

                # Build day cell container
                cell = ctk.CTkFrame(
                    self.grid_frame,
                    fg_color="transparent",
                    corner_radius=8,
                    cursor="hand2"
                )
                cell.grid(row=row_idx, column=col_idx, padx=1, pady=2, sticky="nsew")
                cell.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))

                # Number button / badge
                if is_selected:
                    btn_fg = TAPO_BLUE
                    btn_text_color = "#FFFFFF"
                    font_weight = "bold"
                    hover_col = TAPO_BLUE_HOVER
                else:
                    btn_fg = "transparent"
                    btn_text_color = TEXT_WHITE if has_recording else TEXT_MUTED
                    font_weight = "bold" if has_recording else "normal"
                    hover_col = "#2B2D35"

                # Day button using Segoe UI font (renders double digits with perfect TrueType kerning)
                day_btn = ctk.CTkButton(
                    cell,
                    text=str(day_num),
                    width=34,
                    height=28,
                    corner_radius=14,
                    fg_color=btn_fg,
                    text_color=btn_text_color,
                    hover_color=hover_col,
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight=font_weight),
                    cursor="hand2",
                    command=lambda d=date_str: self._on_day_click(d)
                )
                day_btn.pack(pady=(2, 0))

                # Dot Indicator for available recordings
                if has_recording:
                    dot_color = "#FFFFFF" if is_selected else TAPO_BLUE
                    dot = ctk.CTkLabel(
                        cell,
                        text="●",
                        font=ctk.CTkFont(family=FONT_FAMILY, size=7),
                        text_color=dot_color,
                        height=8
                    )
                    dot.pack(pady=(0, 2))
                    dot.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))
                else:
                    spacer = ctk.CTkLabel(cell, text="", height=8)
                    spacer.pack(pady=(0, 2))
                    spacer.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))

    def _on_day_click(self, date_str: str):
        self.selected_date = date_str
        self.render_month()
        if self.on_date_selected:
            self.on_date_selected(date_str)
