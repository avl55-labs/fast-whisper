"""The settings window: a sidebar and one page per group of options.

Everything here writes straight into the shared `Config` and saves it, so a change takes
effect without restarting. Options that need the app to re-arm something - the hotkey, the
model - call back into it.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import tkinter as tk
from typing import Callable

from . import audio, autostart, history, models, output
from .config import CONFIG_PATH, LOG_PATH, Config, app_dir
from PIL import ImageTk

from .widgets import (
    ACCENT,
    BG,
    BORDER,
    CARD,
    FONT,
    FONT_SECTION,
    FONT_SMALL,
    FONT_TITLE,
    MUTED,
    SIDEBAR,
    SIDEBAR_ACTIVE,
    TEXT,
    Button,
    Card,
    Dropdown,
    Gauge,
    ScrollArea,
    Switch,
    section_label,
)

log = logging.getLogger(__name__)

PAGES = [
    ("general", "General"),
    ("sound", "Sound"),
    ("models", "Models"),
    ("vocabulary", "Vocabulary"),
    ("history", "History"),
    ("about", "About"),
]

MODES = [("Hold to talk", "hold"), ("Toggle on and off", "toggle")]
LANGUAGES = [("Russian", "ru"), ("English", "en"), ("Detect automatically", "auto")]
OUTPUTS = [
    ("Paste into the window", "paste"),
    ("Type it out", "type"),
    ("Copy to clipboard only", "clipboard"),
]
POSITIONS = [("Top of the screen", "top"), ("Bottom", "bottom"), ("Middle", "center")]
MIN_SECONDS = [("0.2 s", 0.2), ("0.4 s", 0.4), ("0.7 s", 0.7), ("1.0 s", 1.0)]
MAX_SECONDS = [("1 minute", 60.0), ("5 minutes", 300.0), ("15 minutes", 900.0)]


class SettingsWindow:
    """One instance at a time; `open` reuses the existing window if there is one."""

    _current: "SettingsWindow | None" = None

    @classmethod
    def open(cls, root: tk.Tk, cfg: Config, app, capture: Callable[[], None]) -> None:  # noqa: ANN001
        if cls._current is not None and cls._current.alive:
            cls._current.focus()
            return
        cls._current = cls(root, cfg, app, capture)

    def __init__(self, root: tk.Tk, cfg: Config, app, capture: Callable[[], None]) -> None:  # noqa: ANN001
        self.cfg = cfg
        self.app = app
        self.capture = capture
        self.alive = True
        self.pages: dict[str, tk.Frame] = {}
        self.nav_items: dict[str, tk.Label] = {}
        self.current = "general"

        self.win = tk.Toplevel(root)
        self.win.title("FastWhisper")
        self.win.geometry("1000x660")
        self.win.minsize(900, 560)
        self.win.configure(bg=BG)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self._build_sidebar()
        self._build_body()
        self.show("general")
        self.focus()

    # ---------- chrome ----------

    def _build_sidebar(self) -> None:
        bar = tk.Frame(self.win, bg=SIDEBAR, width=190)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        tk.Label(
            bar, text="FastWhisper", bg=SIDEBAR, fg=TEXT, font=FONT_TITLE, anchor="w"
        ).pack(fill="x", padx=18, pady=(20, 16))

        for key, title in PAGES:
            item = tk.Label(
                bar, text=title, bg=SIDEBAR, fg=TEXT, font=FONT,
                anchor="w", padx=14, pady=8, cursor="hand2",
            )
            item.pack(fill="x", padx=8, pady=1)
            item.bind("<Button-1>", lambda _e, k=key: self.show(k))
            self.nav_items[key] = item

        footer = tk.Frame(bar, bg=SIDEBAR)
        footer.pack(side="bottom", fill="x", pady=16, padx=14)
        tk.Label(
            footer, text="Offline. Free. No account.", bg=SIDEBAR, fg=MUTED, font=FONT_SMALL,
            anchor="w", justify="left",
        ).pack(fill="x")

    def _build_body(self) -> None:
        self.body = tk.Frame(self.win, bg=BG)
        self.body.pack(side="right", fill="both", expand=True)

        header = tk.Frame(self.body, bg=BG)
        header.pack(fill="x", padx=28, pady=(20, 0))
        self.title_label = tk.Label(
            header, text="", bg=BG, fg=TEXT, font=FONT_TITLE, anchor="w"
        )
        self.title_label.pack(side="left")
        self.status_label = tk.Label(header, text="", bg=BG, fg=MUTED, font=FONT_SMALL)
        self.status_label.pack(side="right")

        self.container = tk.Frame(self.body, bg=BG)
        self.container.pack(fill="both", expand=True, padx=20, pady=(8, 16))

    def show(self, key: str) -> None:
        for name, item in self.nav_items.items():
            active = name == key
            item.configure(bg=SIDEBAR_ACTIVE if active else SIDEBAR,
                           fg=ACCENT if active else TEXT)
        for page in self.pages.values():
            page.pack_forget()

        if key not in self.pages:
            builder = getattr(self, f"_page_{key}")
            area = ScrollArea(self.container)
            page_body = tk.Frame(area.body, bg=BG)
            page_body.pack(fill="both", expand=True, padx=8)
            builder(page_body)
            self.pages[key] = area
        self.pages[key].pack(fill="both", expand=True)
        self.current = key
        self.title_label.configure(text=dict(PAGES)[key])

        if key == "models":
            self._refresh_models()
        elif key == "history":
            self._refresh_history()

    def focus(self) -> None:
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def close(self) -> None:
        self.alive = False
        SettingsWindow._current = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    # ---------- helpers ----------

    def _save(self) -> None:
        self.cfg.save()
        self.status_label.configure(text="Saved")
        self.win.after(1200, lambda: self.status_label.configure(text=""))

    def _setter(self, field: str) -> Callable[[object], None]:
        def apply(value: object) -> None:
            setattr(self.cfg, field, value)
            self._save()

        return apply

    # ---------- pages ----------

    def _page_general(self, parent: tk.Frame) -> None:
        section_label(parent, "DICTATION")
        card = Card(parent)

        _row, slot = card.row("Hotkey", "The key you hold, or press, to dictate")
        self.hotkey_value = tk.Label(
            slot, text=self.cfg.hotkey.upper(), bg=CARD, fg=MUTED, font=FONT
        )
        self.hotkey_value.pack(side="left", padx=(0, 10))
        Button(slot, "Change...", self._change_hotkey).pack(side="left")

        _row, slot = card.row("Mode", "Hold the key while speaking, or press once to start")
        Dropdown(slot, MODES, self.cfg.mode, self._set_mode).pack()

        _row, slot = card.row("Language", "Recognition is more accurate with a fixed language")
        Dropdown(slot, LANGUAGES, self.cfg.language, self._setter("language")).pack()

        _row, slot = card.row("Model", "Change and download models on the Models page")
        options = [(item.title, item.name) for item in models.CATALOGUE]
        self.model_dropdown = Dropdown(slot, options, self.cfg.model, self._set_model)
        self.model_dropdown.pack()

        section_label(parent, "TEXT")
        card = Card(parent)
        _row, slot = card.row("Result", "Where the recognized text goes")
        Dropdown(slot, OUTPUTS, self.cfg.output, self._setter("output")).pack()

        _row, slot = card.row(
            "Keep a history", f"Every result is appended to {history.HISTORY_PATH.name}"
        )
        Switch(slot, self.cfg.save_history, self._setter("save_history")).pack()

        section_label(parent, "FEEDBACK")
        card = Card(parent)
        _row, slot = card.row(
            "Floating panel", "Shows a live waveform while recording and while transcribing"
        )
        Switch(slot, self.cfg.overlay, self._setter("overlay")).pack()

        _row, slot = card.row("Panel position", "")
        Dropdown(slot, POSITIONS, self.cfg.overlay_position, self._setter("overlay_position")).pack()

        _row, slot = card.row("Sound effects", "Short beeps when recording starts and stops")
        Switch(slot, self.cfg.beep, self._setter("beep")).pack()

        _row, slot = card.row("Notifications", "A tray balloon with the recognized text")
        Switch(slot, self.cfg.notifications, self._setter("notifications")).pack()

        section_label(parent, "APPLICATION")
        card = Card(parent)
        _row, slot = card.row("Launch at login", "Start FastWhisper when you sign in to Windows")
        Switch(slot, autostart.is_enabled(), self._set_autostart).pack()

        _row, slot = card.row("Settings file", str(CONFIG_PATH))
        Button(slot, "Open", lambda: _open(CONFIG_PATH)).pack()

    def _page_sound(self, parent: tk.Frame) -> None:
        section_label(parent, "MICROPHONE")
        card = Card(parent)

        devices: list[tuple[str, object]] = [("System default", None)]
        devices += [(name[:38], index) for index, name in audio.list_input_devices()]
        _row, slot = card.row("Input device", "")
        Dropdown(slot, devices, self.cfg.input_device, self._set_device, width=26).pack()

        _row, slot = card.row(
            "Boost quiet recordings",
            "Lifts a low input to a usable level before recognition",
        )
        Switch(slot, self.cfg.auto_gain, self._setter("auto_gain")).pack()

        _row, slot = card.row(
            "Silence removal", "Trims quiet parts before recognition, which is faster and cleaner"
        )
        Switch(slot, self.cfg.vad, self._setter("vad")).pack()

        section_label(parent, "LIMITS")
        card = Card(parent)
        _row, slot = card.row(
            "Ignore recordings shorter than", "Guards against an accidental tap on the hotkey"
        )
        Dropdown(slot, MIN_SECONDS, self.cfg.min_seconds, self._setter("min_seconds")).pack()

        _row, slot = card.row("Stop recording after", "A safety net for a stuck key")
        Dropdown(slot, MAX_SECONDS, self.cfg.max_seconds, self._set_max_seconds).pack()

        section_label(parent, "PERFORMANCE")
        card = Card(parent)
        threads = [("Half the cores (default)", 0), ("4", 4), ("8", 8), ("16", 16)]
        _row, slot = card.row(
            "CPU threads", f"This machine has {os.cpu_count()} logical cores"
        )
        Dropdown(slot, threads, self.cfg.cpu_threads, self._set_threads).pack()

    def _page_models(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text=(
                "Every model here runs on this machine, with no account and no cloud. Larger "
                "ones are more accurate and slower; the speed and accuracy bars are relative to "
                "each other, and the wait is what you actually get on this CPU."
            ),
            bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=640,
        ).pack(fill="x", pady=(8, 4), padx=4)

        self.model_rows: dict[str, dict] = {}
        self._badges: list = []  # PhotoImages have to outlive this method
        section_label(parent, "SPEECH MODELS")
        card = Card(parent)
        for info in models.CATALOGUE:
            icon = ImageTk.PhotoImage(models.badge(info))
            self._badges.append(icon)
            _row, slot = card.row(
                info.title,
                f"{info.author} · {info.packager} · {info.languages} "
                f"· {info.latency}",
                icon=icon,
                wrap=380,
            )

            gauge = tk.Frame(slot, bg=CARD)
            gauge.pack(side="left", padx=(0, 14))
            tk.Label(gauge, text="Accuracy", bg=CARD, fg=MUTED, font=FONT_SMALL).pack()
            Gauge(gauge, info.accuracy).pack(pady=(2, 0))

            state = tk.Label(slot, text="", bg=CARD, fg=MUTED, font=FONT_SMALL, width=9,
                             anchor="e")
            state.pack(side="left", padx=(0, 10))
            action = Button(slot, "Download", lambda i=info: self._download(i))
            action.pack(side="left", padx=(0, 6))
            remove = Button(slot, "Delete", lambda i=info: self._delete(i))
            remove.pack(side="left")
            self.model_rows[info.name] = {
                "state": state, "action": action, "remove": remove, "info": info,
            }

        tk.Label(
            parent,
            text=(
                "Badges mark who trained each model, not a partnership: the weights are open "
                "and used under their own licences."
            ),
            bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=640,
        ).pack(fill="x", pady=(8, 4), padx=4)

    def _page_vocabulary(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text=(
                "Names, jargon and spellings the model should prefer. They are passed to Whisper "
                "as context before each recording, which nudges it towards your wording. One "
                "entry per line; keep the list short, a long one dilutes the effect."
            ),
            bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=620,
        ).pack(fill="x", pady=(8, 8), padx=4)

        frame = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        frame.pack(fill="both", expand=True)
        self.vocab_text = tk.Text(
            frame, height=14, bg=CARD, fg=TEXT, font=FONT, relief="flat",
            highlightthickness=0, padx=12, pady=10, wrap="word",
        )
        self.vocab_text.pack(fill="both", expand=True)
        self.vocab_text.insert("1.0", "\n".join(self.cfg.vocabulary))

        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", pady=10)
        Button(actions, "Save", self._save_vocabulary, primary=True).pack(side="left")
        tk.Label(
            actions, text="Applies to the next recording.", bg=BG, fg=MUTED, font=FONT_SMALL
        ).pack(side="left", padx=12)

    def _page_history(self, parent: tk.Frame) -> None:
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=(8, 8))
        self.search_var = tk.StringVar()
        entry = tk.Entry(
            top, textvariable=self.search_var, font=FONT, bg=CARD, fg=TEXT,
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        entry.insert(0, "")
        self.search_var.trace_add("write", lambda *_: self._refresh_history())
        Button(top, "Refresh", self._refresh_history).pack(side="left")

        self.history_box = tk.Frame(parent, bg=BG)
        self.history_box.pack(fill="both", expand=True)

    def _page_about(self, parent: tk.Frame) -> None:
        from . import __version__

        section_label(parent, "ABOUT")
        card = Card(parent)
        _row, slot = card.row("Version", f"FastWhisper {__version__}")
        _row, slot = card.row("Recognition", "faster-whisper on the CTranslate2 runtime")
        _row, slot = card.row("Data folder", str(app_dir()))
        Button(slot, "Open", lambda: _open(app_dir())).pack()
        _row, slot = card.row("Log file", str(LOG_PATH))
        Button(slot, "Open", lambda: _open(LOG_PATH)).pack()

        section_label(parent, "PRIVACY")
        Card(parent).row(
            "Nothing leaves this machine",
            "Audio is held in memory and discarded after recognition. The only network "
            "request the app makes is downloading a model.",
        )

    # ---------- actions ----------

    def _change_hotkey(self) -> None:
        self.capture()

    def refresh_hotkey(self) -> None:
        try:
            self.hotkey_value.configure(text=self.cfg.hotkey.upper())
        except tk.TclError:
            pass

    def _set_mode(self, mode: object) -> None:
        self.cfg.mode = str(mode)
        self._save()
        self.app.reload_hotkey()

    def _set_model(self, name: object) -> None:
        self.cfg.model = str(name)
        self._save()
        self.status_label.configure(text="Loading model...")

        def load() -> None:
            self.app.transcriber.unload()
            try:
                self.app.transcriber.load()
                message = "Model ready"
            except Exception as exc:
                log.exception("model load failed")
                message = f"Model error: {exc}"
            self.win.after(0, lambda: self.status_label.configure(text=message))

        threading.Thread(target=load, daemon=True).start()

    def _set_device(self, index: object) -> None:
        self.cfg.input_device = index if index is None else int(index)  # type: ignore[arg-type]
        self.app.recorder.device = self.cfg.input_device
        self._save()

    def _set_max_seconds(self, value: object) -> None:
        self.cfg.max_seconds = float(value)  # type: ignore[arg-type]
        self.app.recorder.max_seconds = self.cfg.max_seconds
        self._save()

    def _set_threads(self, value: object) -> None:
        self.cfg.cpu_threads = int(value)  # type: ignore[arg-type]
        self._save()
        self.status_label.configure(text="Applies after the model reloads")

    def _set_autostart(self, value: bool) -> None:
        if value:
            autostart.enable()
        else:
            autostart.disable()

    def _save_vocabulary(self) -> None:
        lines = [line.strip() for line in self.vocab_text.get("1.0", "end").splitlines()]
        self.cfg.vocabulary = [line for line in lines if line]
        self._save()

    # ---------- models page ----------

    def _refresh_models(self) -> None:
        for name, widgets in self.model_rows.items():
            info = widgets["info"]
            downloaded = models.is_downloaded(info)
            active = self.cfg.model == name
            if downloaded:
                size = models.human_size(models.disk_size(info))
                widgets["state"].configure(
                    text="in use" if active else size,
                    fg=ACCENT if active else MUTED,
                )
                widgets["action"].configure(text="Use")
                widgets["action"].command = lambda i=info: self._use(i)
                widgets["action"].set_enabled(not active)
                widgets["remove"].set_enabled(not active)
            else:
                widgets["state"].configure(text=f"{info.size_gb:.1f} GB", fg=MUTED)
                widgets["action"].configure(text="Download")
                widgets["action"].command = lambda i=info: self._download(i)
                widgets["action"].set_enabled(True)
                widgets["remove"].set_enabled(False)

    def _use(self, info: models.ModelInfo) -> None:
        self.model_dropdown.set(info.name)
        self._set_model(info.name)
        self._refresh_models()

    def _download(self, info: models.ModelInfo) -> None:
        widgets = self.model_rows[info.name]
        widgets["action"].set_enabled(False)
        widgets["state"].configure(text="Downloading...")

        def done(error: Exception | None) -> None:
            def finish() -> None:
                if error is not None:
                    widgets["state"].configure(text="Download failed")
                    widgets["action"].set_enabled(True)
                else:
                    self._refresh_models()

            self.win.after(0, finish)

        threading.Thread(
            target=models.download, args=(info, done), daemon=True
        ).start()

    def _delete(self, info: models.ModelInfo) -> None:
        if self.cfg.model == info.name:
            return
        models.delete(info)
        self._refresh_models()

    # ---------- history page ----------

    def _refresh_history(self) -> None:
        for child in self.history_box.winfo_children():
            child.destroy()

        needle = self.search_var.get().strip().lower()
        entries = list(reversed(history.recent(200)))
        shown = 0
        for entry in entries:
            text = entry.get("text", "")
            if needle and needle not in text.lower():
                continue
            if shown >= 60:
                break
            shown += 1
            card = tk.Frame(self.history_box, bg=CARD, highlightthickness=1,
                            highlightbackground=BORDER)
            card.pack(fill="x", pady=2)
            tk.Label(
                card, text=text, bg=CARD, fg=TEXT, font=FONT, anchor="w",
                justify="left", wraplength=560, cursor="hand2",
            ).pack(side="left", fill="x", expand=True, padx=12, pady=8)
            meta = f"{entry.get('at', '')[:16].replace('T', ' ')} - {entry.get('audio_seconds', 0)}s"
            tk.Label(card, text=meta, bg=CARD, fg=MUTED, font=FONT_SMALL).pack(
                side="right", padx=12
            )
            card.bind("<Button-1>", lambda _e, t=text: output.to_clipboard(t))
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda _e, t=text: self._copy(t))

        if shown == 0:
            tk.Label(
                self.history_box,
                text="Nothing here yet." if not needle else "No results.",
                bg=BG, fg=MUTED, font=FONT,
            ).pack(pady=20)

    def _copy(self, text: str) -> None:
        output.to_clipboard(text)
        self.status_label.configure(text="Copied")
        self.win.after(1200, lambda: self.status_label.configure(text=""))


def _open(path) -> None:  # noqa: ANN001
    try:
        os.startfile(str(path))  # noqa: S606
    except OSError:
        subprocess.Popen(["explorer", str(path)])  # noqa: S603,S607
