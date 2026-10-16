import math
import subprocess
import sys
import time
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk
import psutil
from PIL import Image


SAMPLE_INTERVAL_MS = 3000
ANIMATION_INTERVAL_MS = 16
THEME_TRANSITION_MS = 540
SHUTDOWN_GRACE_SECONDS = 60
THEMES = {
    "Epic Games": {
        "background": "#0c0d12",
        "panel": "#171820",
        "panel_hover": "#222331",
        "field": "#11121a",
        "text": "#f6f4ff",
        "muted": "#a5a2b5",
        "accent": "#8757f5",
        "accent_hover": "#7041dc",
        "track": "#32313e",
    },
    "Steam": {
        "background": "#0c141d",
        "panel": "#172533",
        "panel_hover": "#203448",
        "field": "#111d29",
        "text": "#f0f6fc",
        "muted": "#a1b2c2",
        "accent": "#329be8",
        "accent_hover": "#2181ca",
        "track": "#2a3d4e",
    },
    "Browser Download": {
        "background": "#0d1716",
        "panel": "#172522",
        "panel_hover": "#20332e",
        "field": "#111e1b",
        "text": "#eff8f4",
        "muted": "#a0b6ad",
        "accent": "#38a982",
        "accent_hover": "#278a69",
        "track": "#2b4039",
    },
}

PROFILE_DEFAULTS = {
    "Epic Games": (50, 30),
    "Steam": (70, 40),
    "Browser Download": (50, 30),
}

STATUS_COLORS = {
    "ready": ("#303440", "#d1d5df"),
    "monitoring": ("#253951", "#9bcaff"),
    "active": ("#1f3b32", "#91e2ba"),
    "quiet": ("#463a23", "#ffdc91"),
    "countdown": ("#392d52", "#d1b7ff"),
    "error": ("#4a292b", "#ffb0a9"),
}


class ShutdownMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiet Hours Monitor")
        self.application_directory = Path(
            getattr(sys, "_MEIPASS", Path(__file__).parent)
        )
        self.logo_image_path = self.application_directory / "QuietHoursLogoTransparent.png"
        self.root.iconbitmap(str(self.application_directory / "QuietHoursMonitor.ico"))
        self.root.geometry("760x700")
        self.root.minsize(700, 600)
        self.root.withdraw()

        self.monitoring = False
        self.previous_bytes = 0
        self.inactive_time = 0.0
        self.quiet_started_at = None
        self.low_periods = 0
        self.monitor_job = None
        self.animation_job = None
        self.countdown_job = None
        self.countdown_remaining = 0
        self.countdown_deadline = None
        self.shutdown_scheduled = False
        self.threshold = 50.0
        self.required_time = 30
        self.required_periods = 3
        self.selected_source = ""
        self._status_key = "ready"
        self._theme_animation = None
        self._theme_transition_started = None
        self._theme_transition_from = {}
        self._theme_transition_to = {}
        self._scrollbar_update_job = None
        self._scrollbar_hidden = False
        self._splash = None
        self._splash_job = None
        self._splash_started_at = None
        self._splash_photo = None
        self._splash_logo = None
        self._current_theme_colors = THEMES["Epic Games"].copy()
        self._displayed_progress = 0.0
        self.section_labels = []
        self.setting_labels = []
        self.setting_fields = {}

        self.threshold_var = ctk.StringVar(value="50")
        self.required_time_var = ctk.StringVar(value="30")
        self.required_periods_var = ctk.StringVar(value="3")
        self.status_var = ctk.StringVar(value="Ready to monitor")
        self.speed_var = ctk.StringVar(value="KB/s --")
        self.inactive_var = ctk.StringVar(value="0 / 30 sec")
        self.periods_var = ctk.StringVar(value="0 / 3")
        self.countdown_var = ctk.StringVar(value="Choose a profile to get started")
        self.event_var = ctk.StringVar(value="Your activity updates will appear here.")

        ctk.set_appearance_mode("dark")
        self._build_interface()
        self.root.bind("<Configure>", self._queue_scrollbar_visibility_update, add="+")
        self.root.after_idle(self._sync_scrollbar_visibility)
        self._apply_theme("Epic Games", animate=False)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after_idle(self._show_startup_splash)

    def _show_startup_splash(self):
        self._splash_logo = Image.open(self.logo_image_path).convert("RGBA")
        self._splash = ctk.CTkToplevel(self.root)
        self._splash.overrideredirect(True)
        self._splash.attributes("-topmost", True)
        self._splash.configure(fg_color=THEMES["Epic Games"]["background"])

        width, height = 360, 370
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self._splash.geometry(f"{width}x{height}+{x}+{y}")

        self._splash_image_label = ctk.CTkLabel(
            self._splash,
            text="",
            width=260,
            height=260,
            fg_color=THEMES["Epic Games"]["background"],
        )
        self._splash_image_label.pack(pady=(18, 4))
        ctk.CTkLabel(
            self._splash,
            text="Quiet Hours",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#f6f4ff",
        ).pack()
        ctk.CTkLabel(
            self._splash,
            text="Getting things ready...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#a5a2b5",
        ).pack(pady=(3, 0))

        self._splash_started_at = time.monotonic()
        self._animate_startup_splash()

    def _animate_startup_splash(self):
        if self._splash is None:
            return
        elapsed = (time.monotonic() - self._splash_started_at) * 1000
        progress = min(elapsed / 760, 1.0)
        eased_progress = 1 - (1 - progress) ** 3
        size = round(150 + 92 * eased_progress)
        opacity = min(1.0, 0.18 + 0.82 * eased_progress)

        image = self._splash_logo.resize(
            (size, size),
            Image.Resampling.LANCZOS,
        )
        alpha = image.getchannel("A").point(lambda value: round(value * opacity))
        image.putalpha(alpha)
        self._splash_photo = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(size, size),
        )
        self._splash_image_label.configure(image=self._splash_photo)

        if elapsed >= 980:
            self._splash.destroy()
            self._splash = None
            self._splash_job = None
            self._splash_photo = None
            self._splash_logo = None
            self.root.deiconify()
            self.root.lift()
            return
        self._splash_job = self.root.after(16, self._animate_startup_splash)

    def _build_interface(self):
        self.page = ctk.CTkFrame(self.root, corner_radius=0)
        self.page.pack(fill="both", expand=True)

        self.footer = ctk.CTkFrame(self.page, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=30, pady=(8, 14))

        self.content = ctk.CTkScrollableFrame(
            self.page,
            corner_radius=0,
            fg_color="transparent",
        )
        self.content.pack(fill="both", expand=True, padx=30, pady=(18, 0))

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 18))
        self.title_label = ctk.CTkLabel(
            header,
            text="Quiet Hours",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            anchor="w",
        )
        self.title_label.pack(anchor="w")
        self.subtitle_label = ctk.CTkLabel(
            header,
            text="A calmer way to keep an eye on your downloads.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w", pady=(3, 0))

        self.profile_card = self._card(self.content, radius=18)
        self.profile_card.pack(fill="x", pady=(0, 12))
        self.profile_body = self._card_body(self.profile_card)
        self._section_label(self.profile_body, "CHOOSE YOUR DOWNLOAD")
        self.profile_row = ctk.CTkFrame(self.profile_body, fg_color="transparent")
        self.profile_row.pack(fill="x", pady=(10, 0))
        self.profile_buttons = {}
        for source in THEMES:
            button = ctk.CTkButton(
                self.profile_row,
                text=source,
                height=42,
                corner_radius=13,
                border_width=1,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                command=lambda selected=source: self.select_source(selected),
            )
            button.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.profile_buttons[source] = button
        self.profile_note = ctk.CTkLabel(
            self.profile_body,
            text="Your choice changes the app's look. Network activity is measured system-wide.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w",
        )
        self.profile_note.pack(anchor="w", pady=(9, 0))

        self.status_card = self._card(self.content, radius=18)
        self.status_card.pack(fill="x", pady=(0, 12))
        self.status_body = self._card_body(self.status_card)
        status_row = ctk.CTkFrame(self.status_body, fg_color="transparent")
        status_row.pack(fill="x")
        self._section_label(status_row, "MONITOR STATUS").pack(side="left")
        self.status_badge = ctk.CTkLabel(
            status_row,
            textvariable=self.status_var,
            corner_radius=20,
            padx=12,
            pady=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        )
        self.status_badge.pack(side="right")
        self.countdown_label = ctk.CTkLabel(
            self.status_body,
            textvariable=self.countdown_var,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=590,
        )
        self.countdown_label.pack(fill="x", anchor="w", pady=(12, 0))

        stats = ctk.CTkFrame(self.content, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 12))
        stats.grid_columnconfigure((0, 1), weight=1, uniform="stats")
        self.speed_card = self._card(stats, radius=18)
        self.speed_card.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.period_card = self._card(stats, radius=18)
        self.period_card.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.speed_body = self._card_body(self.speed_card)
        self.period_body = self._card_body(self.period_card)
        self._section_label(self.speed_body, "DOWNLOAD SPEED")
        self.speed_value = ctk.CTkLabel(
            self.speed_body,
            textvariable=self.speed_var,
            font=ctk.CTkFont(family="Segoe UI", size=27, weight="bold"),
            anchor="w",
        )
        self.speed_value.pack(anchor="w", pady=(8, 0))
        self.speed_unit = ctk.CTkLabel(
            self.speed_body,
            text="live download throughput",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w",
        )
        self.speed_unit.pack(anchor="w", pady=(0, 2))
        self._section_label(self.period_body, "QUIET PERIODS")
        self.period_value = ctk.CTkLabel(
            self.period_body,
            textvariable=self.periods_var,
            font=ctk.CTkFont(family="Segoe UI", size=27, weight="bold"),
            anchor="w",
        )
        self.period_value.pack(anchor="w", pady=(8, 0))
        self.period_note = ctk.CTkLabel(
            self.period_body,
            text="completed quiet intervals",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w",
        )
        self.period_note.pack(anchor="w", pady=(0, 2))

        self.activity_card = self._card(self.content, radius=18)
        self.activity_card.pack(fill="x", pady=(0, 12))
        self.activity_body = self._card_body(self.activity_card)
        self.activity_title = ctk.CTkLabel(
            self.activity_body,
            text="Quiet period",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
        )
        self.activity_title.pack(anchor="w")
        self.progress = ctk.CTkProgressBar(
            self.activity_body,
            height=15,
            corner_radius=8,
            border_width=0,
            mode="determinate",
            determinate_speed=0,
        )
        self.progress.pack(fill="x", pady=(15, 8))
        self.progress.set(0)
        self.progress_text = ctk.CTkLabel(
            self.activity_body,
            textvariable=self.inactive_var,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w",
        )
        self.progress_text.pack(anchor="w")
        self.event_label = ctk.CTkLabel(
            self.activity_body,
            textvariable=self.event_var,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w",
            wraplength=610,
        )
        self.event_label.pack(anchor="w", pady=(7, 0))

        self.settings_card = self._card(self.content, radius=18)
        self.settings_card.pack(fill="x", pady=(0, 14))
        self.settings_body = self._card_body(self.settings_card)
        self._section_label(self.settings_body, "YOUR THRESHOLDS")
        settings_row = ctk.CTkFrame(self.settings_body, fg_color="transparent")
        settings_row.pack(fill="x", pady=(12, 0))
        settings_row.grid_columnconfigure((0, 1, 2), weight=1, uniform="settings")
        self.entries = []
        self._make_setting(
            settings_row, 0, "threshold", "Low speed", self.threshold_var, "KB/s"
        )
        self._make_setting(
            settings_row, 1, "required_time", "Quiet period",
            self.required_time_var, "seconds"
        )
        self._make_setting(
            settings_row, 2, "required_periods", "Quiet periods",
            self.required_periods_var, "before test"
        )

        controls = ctk.CTkFrame(self.footer, fg_color="transparent")
        controls.pack(fill="x")
        self.start_button = ctk.CTkButton(
            controls,
            text="Start monitoring",
            height=44,
            corner_radius=14,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.start,
        )
        self.start_button.pack(side="left")
        self.stop_button = ctk.CTkButton(
            controls,
            text="Stop",
            height=44,
            corner_radius=14,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.stop,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(9, 0))
        self.safety_note = ctk.CTkLabel(
            self.footer,
            text=(
                "Windows shutdown starts after 3 quiet periods. "
                "You have 60 seconds to cancel with Stop."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w",
        )
        self.safety_note.pack(anchor="w", pady=(13, 0))

    def _queue_scrollbar_visibility_update(self, _event=None):
        if self._scrollbar_update_job is None:
            self._scrollbar_update_job = self.root.after_idle(
                self._sync_scrollbar_visibility
            )

    def _sync_scrollbar_visibility(self):
        self._scrollbar_update_job = None
        is_fullscreen = (
            self.root.state() == "zoomed"
            or bool(self.root.attributes("-fullscreen"))
        )
        if is_fullscreen == self._scrollbar_hidden:
            return

        if is_fullscreen:
            self.content._scrollbar.grid_remove()
        else:
            self.content._scrollbar.grid()
        self._scrollbar_hidden = is_fullscreen

    @staticmethod
    def _card(parent, radius):
        return ctk.CTkFrame(parent, corner_radius=radius, border_width=0)

    @staticmethod
    def _card_body(card):
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        return body

    def _section_label(self, parent, text):
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            anchor="w",
        )
        label.pack(anchor="w")
        self.section_labels.append(label)
        return label

    def _make_setting(self, parent, column, key, label, variable, unit):
        field = ctk.CTkFrame(parent, fg_color="transparent")
        field.grid(row=0, column=column, sticky="ew", padx=(0, 10))
        field.grid_columnconfigure(0, weight=1)
        setting_label = ctk.CTkLabel(
            field,
            text=label,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w",
        )
        setting_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.setting_labels.append(setting_label)
        input_row = ctk.CTkFrame(field, fg_color="transparent")
        input_row.grid(row=1, column=0, sticky="ew")
        allow_decimal = key == "threshold"
        validate_command = (
            self.root.register(
                lambda value, decimal=allow_decimal: self._valid_numeric_input(
                    value, decimal
                )
            ),
            "%P",
        )
        entry = ctk.CTkEntry(
            input_row,
            textvariable=variable,
            height=38,
            width=100,
            corner_radius=11,
            border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            validate="key",
            validatecommand=validate_command,
        )
        entry.pack(side="left")
        self.entries.append(entry)
        unit_label = ctk.CTkLabel(
            input_row,
            text=unit,
            font=ctk.CTkFont(family="Segoe UI", size=9),
        )
        unit_label.pack(side="left", padx=(7, 0))
        self.setting_labels.append(unit_label)
        error_label = ctk.CTkLabel(
            field,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#ff6b6b",
            anchor="w",
            justify="left",
            wraplength=190,
        )
        error_label.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        error_label.grid_remove()
        self.setting_fields[key] = {
            "entry": entry,
            "error_label": error_label,
            "variable": variable,
            "error": "",
        }
        variable.trace_add("write", lambda *_args, setting=key: self._on_setting_changed(setting))

    @staticmethod
    def _valid_numeric_input(value, allow_decimal):
        if allow_decimal:
            return value == "" or (
                value.count(".") <= 1
                and all(
                    "0" <= character <= "9" or character == "."
                    for character in value
                )
            )
        return value == "" or all("0" <= character <= "9" for character in value)

    def _setting_error(self, key):
        value = self.setting_fields[key]["variable"].get()
        if not value:
            messages = {
                "threshold": "Enter a low-speed value in KB/s.",
                "required_time": "Enter a quiet period in seconds.",
                "required_periods": "Enter the number of quiet periods.",
            }
            return messages[key]

        try:
            if key == "threshold":
                threshold = float(value)
                if not math.isfinite(threshold) or threshold < 0:
                    return "Low speed must be a finite number of 0 or higher."
            elif key == "required_time":
                if int(value) <= 0:
                    return "Quiet period must be a whole number above 0."
            elif int(value) <= 0:
                return "Quiet periods must be a whole number above 0."
        except ValueError:
            messages = {
                "threshold": "Enter a valid low-speed number, such as 50 or 2.5.",
                "required_time": "Use a whole number of seconds, such as 30.",
                "required_periods": "Use a whole number of periods, such as 3.",
            }
            return messages[key]
        return ""

    def _set_setting_error(self, key, error):
        setting = self.setting_fields[key]
        setting["error"] = error
        entry = setting["entry"]
        entry.configure(
            border_color="#ff5c66" if error else self._current_theme_colors["track"]
        )
        error_label = setting["error_label"]
        if error:
            error_label.configure(text=error)
            if not error_label.winfo_manager():
                error_label.grid()
        else:
            error_label.configure(text="")
            error_label.grid_remove()

    def _on_setting_changed(self, key):
        if self.setting_fields[key]["error"]:
            self._set_setting_error(key, self._setting_error(key))

    def _validate_settings(self):
        errors = {
            key: self._setting_error(key)
            for key in self.setting_fields
        }
        for key, error in errors.items():
            self._set_setting_error(key, error)
        return not any(errors.values())

    def select_source(self, source):
        if source not in THEMES:
            raise ValueError(f"Unknown download profile: {source}")
        self.selected_source = source
        threshold, required_time = PROFILE_DEFAULTS[source]
        self.threshold_var.set(str(threshold))
        self.required_time_var.set(str(required_time))
        self.threshold = float(threshold)
        self.required_time = required_time
        self.inactive_time = 0.0
        self.quiet_started_at = None
        self.low_periods = 0
        self._displayed_progress = 0.0
        if self.monitoring:
            try:
                self.previous_bytes = psutil.net_io_counters().bytes_recv
            except (OSError, psutil.Error) as error:
                self.stop()
                self._set_status("Network error", "error")
                messagebox.showerror("Network monitor error", str(error), parent=self.root)
                return
        self._update_progress()
        self._apply_theme(source, animate=True)
        self._log(f"{source} profile selected.")

    def _apply_theme(self, source, animate):
        if source not in THEMES:
            raise ValueError(f"Unknown theme: {source}")
        self.selected_source = source
        target = THEMES[source].copy()
        self._cancel_job("_theme_animation")
        if not animate:
            self._current_theme_colors = target
            self._render_theme(target)
            return

        self._theme_transition_from = self._current_theme_colors.copy()
        self._theme_transition_to = target
        self._theme_transition_started = time.monotonic()
        self._animate_theme_transition()

    def _render_theme(self, theme):
        self._current_theme_colors = theme.copy()
        self.root.configure(fg_color=theme["background"])
        self.page.configure(fg_color=theme["background"])
        self.content.configure(fg_color="transparent")

        for card in (self.profile_card, self.status_card, self.speed_card,
                     self.period_card, self.activity_card, self.settings_card):
            card.configure(fg_color=theme["panel"], border_color=theme["track"])

        for widget in (
            self.title_label, self.countdown_label, self.speed_value,
            self.period_value, self.activity_title,
        ):
            widget.configure(text_color=theme["text"])

        for widget in (
            self.subtitle_label, self.profile_note, self.speed_unit,
            self.period_note, self.progress_text, self.event_label,
            self.safety_note,
        ):
            widget.configure(text_color=theme["muted"])
        for widget in self.setting_labels:
            widget.configure(text_color=theme["muted"])
        for widget in self.section_labels:
            widget.configure(text_color=theme["muted"])

        for source_name, button in self.profile_buttons.items():
            selected = source_name == self.selected_source
            button.configure(
                fg_color=theme["accent"] if selected else theme["panel_hover"],
                hover_color=theme["accent_hover"] if selected else theme["track"],
                text_color=theme["text"],
                border_color=theme["accent"] if selected else theme["track"],
            )

        for setting in self.setting_fields.values():
            setting["entry"].configure(
                fg_color=theme["field"],
                border_color="#ff5c66" if setting["error"] else theme["track"],
                text_color=theme["text"],
            )

        self.progress.configure(
            fg_color=theme["track"],
        )
        self.start_button.configure(
            fg_color=theme["accent"],
            hover_color=theme["accent_hover"],
            text_color="#ffffff",
        )
        self.stop_button.configure(
            fg_color=theme["panel_hover"],
            hover_color=theme["track"],
            text_color=theme["text"],
        )
        self._update_status_badge()
        self.progress.configure(progress_color=theme["accent"])
        self.progress.set(self._displayed_progress)

    @staticmethod
    def _blend_color(start, end, fraction):
        start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
        end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
        return "#" + "".join(
            f"{round(first + (last - first) * fraction):02x}"
            for first, last in zip(start_rgb, end_rgb)
        )

    def _animate_theme_transition(self):
        elapsed = (time.monotonic() - self._theme_transition_started) * 1000
        fraction = min(elapsed / THEME_TRANSITION_MS, 1.0)
        eased_fraction = fraction * fraction * (3 - 2 * fraction)
        colors = {
            key: self._blend_color(
                self._theme_transition_from[key],
                self._theme_transition_to[key],
                eased_fraction,
            )
            for key in self._theme_transition_to
        }
        self._render_theme(colors)
        if fraction >= 1.0:
            self._theme_animation = None
        else:
            self._theme_animation = self.root.after(
                ANIMATION_INTERVAL_MS,
                self._animate_theme_transition,
            )

    def start(self):
        if not self.selected_source:
            messagebox.showinfo(
                "Choose a download profile",
                "Select Epic Games, Steam, or Browser Download before starting.",
                parent=self.root,
            )
            return

        if not self._validate_settings():
            return

        self.threshold = float(self.threshold_var.get())
        self.required_time = int(self.required_time_var.get())
        self.required_periods = int(self.required_periods_var.get())

        try:
            self.previous_bytes = psutil.net_io_counters().bytes_recv
        except (OSError, psutil.Error) as error:
            messagebox.showerror("Network monitor error", str(error), parent=self.root)
            return

        self.monitoring = True
        self.inactive_time = 0.0
        self.quiet_started_at = None
        self.low_periods = 0
        self._displayed_progress = 0.0
        self._update_progress()
        self._set_status("Monitoring", "monitoring")
        self.countdown_var.set("Waiting for network activity")
        self._set_controls(running=True)
        self._log("Monitoring started.")
        self._schedule_sample()
        self._schedule_animation()

    def stop(self):
        shutdown_error = self._cancel_scheduled_shutdown()
        self._cancel_job("monitor_job")
        self._cancel_job("animation_job")
        was_counting_down = self.countdown_job is not None
        self._cancel_job("countdown_job")
        self.monitoring = False
        self.countdown_remaining = 0
        self.countdown_deadline = None
        self.quiet_started_at = None
        self.inactive_time = 0.0
        self._displayed_progress = 0.0
        self._update_progress()
        self.countdown_var.set(
            "Countdown cancelled" if was_counting_down else "Monitoring is off"
        )
        self.speed_var.set("KB/s --")
        self._set_status("Stopped", "ready")
        self._set_controls(running=False)
        self._log("Monitoring stopped.")
        if shutdown_error is not None:
            messagebox.showerror(
                "Could not cancel Windows shutdown",
                shutdown_error,
                parent=self.root,
            )

    def _cancel_job(self, name):
        job = getattr(self, name)
        if job is not None:
            self.root.after_cancel(job)
            setattr(self, name, None)

    def _schedule_sample(self):
        self.monitor_job = self.root.after(SAMPLE_INTERVAL_MS, self._sample)

    def _schedule_animation(self):
        self.animation_job = self.root.after(ANIMATION_INTERVAL_MS, self._animate_progress)

    def _sample(self):
        self.monitor_job = None
        try:
            current = psutil.net_io_counters().bytes_recv
        except (OSError, psutil.Error) as error:
            self.stop()
            self._set_status("Network error", "error")
            self.countdown_var.set("Could not read network activity")
            messagebox.showerror("Network monitor error", str(error), parent=self.root)
            return

        downloaded = current - self.previous_bytes
        speed = max(0, downloaded) / (SAMPLE_INTERVAL_MS / 1000) / 1024
        self.previous_bytes = current
        self.speed_var.set(f"KB/s {speed:.2f}")

        if speed > self.threshold:
            self.inactive_time = 0.0
            self.quiet_started_at = None
            self._set_status("Activity detected", "active")
            self.countdown_var.set("Network activity is above the quiet threshold")
            self._log(f"Active — {speed:.2f} KB/s")
        else:
            if self.quiet_started_at is None:
                self.quiet_started_at = time.monotonic()
                self.inactive_time = 0.0
            self._set_status("Low activity", "quiet")
            self.countdown_var.set("Network activity is below the quiet threshold")
            self._log(f"Low activity — {speed:.2f} KB/s")

        self._schedule_sample()

    def _animate_progress(self):
        self.animation_job = None
        if not self.monitoring:
            return

        if self.quiet_started_at is not None:
            self.inactive_time = time.monotonic() - self.quiet_started_at
            if self.inactive_time >= self.required_time:
                self.inactive_time = 0.0
                self.quiet_started_at = None
                self.low_periods += 1
                self._log(
                    f"Quiet period complete ({self.low_periods}/{self.required_periods})."
                )
                if self.low_periods >= self.required_periods:
                    self._update_progress()
                    self._begin_countdown()
                    return

        self._update_progress()
        self._schedule_animation()

    def _begin_countdown(self):
        self._cancel_job("monitor_job")
        self._cancel_job("animation_job")
        try:
            self._schedule_windows_shutdown()
        except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
            self.monitoring = False
            self._set_controls(running=False)
            self._set_status("Shutdown error", "error")
            self.countdown_var.set("Windows could not schedule the shutdown")
            self._log(f"Windows shutdown could not be scheduled: {error}")
            messagebox.showerror(
                "Windows shutdown error",
                f"The system shutdown was not scheduled:\n{error}",
                parent=self.root,
            )
            return

        self.countdown_deadline = time.monotonic() + SHUTDOWN_GRACE_SECONDS
        self.countdown_remaining = SHUTDOWN_GRACE_SECONDS
        self._set_status("Shutdown scheduled", "countdown")
        self.countdown_var.set(
            "Windows shutdown scheduled. Press Stop within 60 seconds to cancel."
        )
        self._log("Quiet-period limit reached. Windows shutdown scheduled.")
        self._tick_countdown()

    def _schedule_windows_shutdown(self):
        if sys.platform != "win32":
            raise RuntimeError("Real system shutdown is supported only on Windows.")
        subprocess.run(
            [
                "shutdown",
                "/s",
                "/t",
                str(SHUTDOWN_GRACE_SECONDS),
                "/c",
                "Quiet Hours Monitor detected sustained low network activity.",
            ],
            check=True,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.shutdown_scheduled = True

    def _cancel_scheduled_shutdown(self):
        if not self.shutdown_scheduled:
            return None
        try:
            subprocess.run(
                ["shutdown", "/a"],
                check=True,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.CalledProcessError) as error:
            details = (
                (error.stderr or "").strip()
                if isinstance(error, subprocess.CalledProcessError)
                else str(error)
            )
            return (
                "The app could not abort the pending Windows shutdown. "
                f"Windows reported: {details}"
            )
        self.shutdown_scheduled = False
        return None

    def _tick_countdown(self):
        if self.countdown_deadline is None:
            return

        self.countdown_remaining = max(
            0, math.ceil(self.countdown_deadline - time.monotonic())
        )
        if self.countdown_remaining == 0:
            self.countdown_job = None
            self.countdown_deadline = None
            self.monitoring = False
            self.shutdown_scheduled = False
            self._set_controls(running=False)
            self.countdown_var.set("Windows shutdown is starting.")
            self._set_status("Shutdown imminent", "active")
            self._log("The scheduled Windows shutdown is now proceeding.")
            return

        self.countdown_var.set(
            f"Windows shutdown in {self.countdown_remaining} second"
            f"{'s' if self.countdown_remaining != 1 else ''} — press Stop to cancel"
        )
        self.countdown_job = self.root.after(250, self._tick_countdown)

    def _update_progress(self):
        maximum = self.required_time
        fraction = min(self.inactive_time / maximum, 1.0) if maximum else 0.0
        self._target_progress = fraction
        self.inactive_var.set(f"{min(int(self.inactive_time), maximum)} / {maximum} sec")
        self.periods_var.set(f"{self.low_periods} / {self.required_periods}")
        self._animate_progress_value()

    def _animate_progress_value(self):
        delta = self._target_progress - self._displayed_progress
        if abs(delta) < 0.002:
            self._displayed_progress = self._target_progress
        else:
            self._displayed_progress += delta * 0.38
        self.progress.set(self._displayed_progress)

    def _set_status(self, text, status):
        self._status_key = status
        self.status_var.set(text)
        self._update_status_badge()

    def _update_status_badge(self):
        background, foreground = STATUS_COLORS[self._status_key]
        self.status_badge.configure(
            fg_color=background,
            text_color=foreground,
        )

    def _set_controls(self, running):
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _log(self, message):
        self.event_var.set(message)

    def _close(self):
        shutdown_error = self._cancel_scheduled_shutdown()
        self._cancel_job("monitor_job")
        self._cancel_job("animation_job")
        self._cancel_job("countdown_job")
        self._cancel_job("_theme_animation")
        self._cancel_job("_scrollbar_update_job")
        self._cancel_job("_splash_job")
        if self._splash is not None:
            self._splash.destroy()
            self._splash = None
        if shutdown_error is not None:
            messagebox.showerror(
                "Could not cancel Windows shutdown",
                shutdown_error,
                parent=self.root,
            )
        self.root.destroy()


if __name__ == "__main__":
    app = ctk.CTk()
    ShutdownMonitorApp(app)
    app.mainloop()
