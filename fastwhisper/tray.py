"""System tray icon and menu."""
from __future__ import annotations

import logging
import os
import subprocess
import threading

import pystray
from pystray import Menu, MenuItem

from . import autostart, output
from .config import CONFIG_PATH, HISTORY_PATH, LOG_PATH, Config, app_dir
from .icons import make_icon

log = logging.getLogger(__name__)

# Labels carry the measured CPU latency per phrase, because Whisper's encoder runs over a
# fixed 30-second window and the wait barely depends on how long you actually spoke.
MODELS = [
    ("tiny", "tiny - fastest, rough"),
    ("base", "base - ~0.6s, rough"),
    ("small", "small - ~1.6s, decent"),
    ("medium", "medium - ~4.3s, good"),
    ("large-v3-turbo", "large-v3-turbo - ~5.5s, best"),
    ("large-v3", "large-v3 - slowest, best"),
]
LANGUAGES = [("Russian", "ru"), ("English", "en"), ("Auto detect", "auto")]
OUTPUTS = [
    ("Paste into window", "paste"),
    ("Type out", "type"),
    ("Clipboard only", "clipboard"),
]


def _open(path) -> None:  # noqa: ANN001
    try:
        os.startfile(str(path))  # noqa: S606 - Windows shell open
    except OSError:
        subprocess.Popen(["explorer", str(path)])  # noqa: S603,S607


class Tray:
    def __init__(self, app, cfg: Config) -> None:  # noqa: ANN001 - avoids a circular import
        self.app = app
        self.cfg = cfg
        self.detail = "Starting..."
        self.icon = pystray.Icon(
            "FastWhisper",
            make_icon("loading"),
            self._title(),
            menu=self._menu(),
        )

    # ---------- rendering ----------

    def _title(self) -> str:
        # Windows truncates tray tooltips at 127 characters.
        return f"FastWhisper - {self.detail}"[:127]

    def on_state(self, state: str, detail: str) -> None:
        self.detail = detail
        try:
            self.icon.icon = make_icon(state)
            self.icon.title = self._title()
            if self.cfg.notifications and state == "idle" and detail:
                self.icon.notify(detail, "FastWhisper")
        except Exception:
            log.debug("tray update failed", exc_info=True)

    def _menu(self) -> Menu:
        return Menu(
            MenuItem(lambda _: self._title(), None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(
                "Mode",
                Menu(
                    MenuItem(
                        "Hold to talk",
                        lambda: self._set_mode("hold"),
                        checked=lambda _: self.cfg.mode == "hold",
                        radio=True,
                    ),
                    MenuItem(
                        "Toggle on/off",
                        lambda: self._set_mode("toggle"),
                        checked=lambda _: self.cfg.mode == "toggle",
                        radio=True,
                    ),
                ),
            ),
            MenuItem(
                "Language",
                Menu(
                    *[
                        MenuItem(
                            label,
                            self._setter("language", code),
                            checked=self._checker("language", code),
                            radio=True,
                        )
                        for label, code in LANGUAGES
                    ]
                ),
            ),
            MenuItem(
                "Model",
                Menu(
                    *[
                        MenuItem(
                            label,
                            self._model_setter(name),
                            checked=self._checker("model", name),
                            radio=True,
                        )
                        for name, label in MODELS
                    ]
                ),
            ),
            MenuItem(
                "Output",
                Menu(
                    *[
                        MenuItem(
                            label,
                            self._setter("output", code),
                            checked=self._checker("output", code),
                            radio=True,
                        )
                        for label, code in OUTPUTS
                    ]
                ),
            ),
            MenuItem("Beep on record", self._toggle_beep, checked=lambda _: self.cfg.beep),
            MenuItem(
                "Show notifications",
                self._toggle_notifications,
                checked=lambda _: self.cfg.notifications,
            ),
            Menu.SEPARATOR,
            MenuItem("Copy last result", self._copy_last),
            MenuItem("Open history", lambda: _open(HISTORY_PATH)),
            MenuItem("Open settings file", lambda: _open(CONFIG_PATH)),
            MenuItem("Open log", lambda: _open(LOG_PATH)),
            MenuItem("Open data folder", lambda: _open(app_dir())),
            Menu.SEPARATOR,
            MenuItem(
                "Start with Windows",
                self._toggle_autostart,
                checked=lambda _: autostart.is_enabled(),
            ),
            MenuItem("Quit", self._quit),
        )

    # ---------- menu actions ----------

    def _setter(self, field: str, value):  # noqa: ANN001, ANN201
        def action() -> None:
            setattr(self.cfg, field, value)
            self.cfg.save()
            self.on_state(self.app.state, self.app.ready_hint())

        return action

    def _checker(self, field: str, value):  # noqa: ANN001, ANN201
        return lambda _: getattr(self.cfg, field) == value

    def _set_mode(self, mode: str) -> None:
        self.cfg.mode = mode
        self.cfg.save()
        self.app.reload_hotkey()

    def _model_setter(self, name: str):  # noqa: ANN201
        def action() -> None:
            if self.cfg.model == name:
                return
            self.cfg.model = name
            self.cfg.save()
            self.on_state("loading", f"Loading {name}...")

            def reload() -> None:
                self.app.transcriber.unload()
                try:
                    self.app.transcriber.load()
                except Exception as exc:
                    self.on_state("error", f"Model error: {exc}")
                    return
                self.on_state("idle", self.app.ready_hint())

            threading.Thread(target=reload, daemon=True).start()

        return action

    def _toggle_beep(self) -> None:
        self.cfg.beep = not self.cfg.beep
        self.cfg.save()

    def _toggle_notifications(self) -> None:
        self.cfg.notifications = not self.cfg.notifications
        self.cfg.save()

    def _toggle_autostart(self) -> None:
        autostart.toggle()

    def _copy_last(self) -> None:
        if self.app.last_text:
            output.to_clipboard(self.app.last_text)

    def _quit(self) -> None:
        self.app.shutdown()
        self.icon.stop()

    # ---------- run ----------

    def run(self) -> None:
        self.icon.run()
