"""System tray icon.

Deliberately thin: the icon shows what the app is doing and opens the settings window.
Everything configurable lives there, so this menu stays short enough to read at a glance.
"""
from __future__ import annotations

import logging
import os
import subprocess

import pystray
from pystray import Menu, MenuItem

from . import output
from .config import CONFIG_PATH, Config
from .icons import make_icon

log = logging.getLogger(__name__)


def _open(path) -> None:  # noqa: ANN001
    try:
        os.startfile(str(path))  # noqa: S606 - Windows shell open
    except OSError:
        subprocess.Popen(["explorer", str(path)])  # noqa: S603,S607


class Tray:
    def __init__(self, app, cfg: Config, ui=None) -> None:  # noqa: ANN001 - avoids a circular import
        self.app = app
        self.cfg = cfg
        self.ui = ui
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
            MenuItem("Settings...", self._open_settings, default=True),
            MenuItem("Copy last result", self._copy_last),
            Menu.SEPARATOR,
            MenuItem("Quit", self._quit),
        )

    # ---------- actions ----------

    def _open_settings(self) -> None:
        if self.ui is None:
            _open(CONFIG_PATH)
            return
        self.ui.open_settings(self.app, self._capture_hotkey)

    def _capture_hotkey(self) -> None:
        """Opens the capture window, with the current hotkey disarmed meanwhile."""
        if self.ui is None:
            return
        if self.app.listener is not None:
            self.app.listener.stop()

        def save(combo: str) -> None:
            self.cfg.hotkey = combo
            self.cfg.save()
            self.app.reload_hotkey()
            if self.ui is not None:
                self.ui.refresh_settings_hotkey()

        self.ui.open_hotkey_capture(save, self.app.reload_hotkey)

    def _copy_last(self) -> None:
        if self.app.last_text:
            output.to_clipboard(self.app.last_text)

    def _quit(self) -> None:
        self.app.shutdown()
        self.icon.stop()
        if self.ui is not None:
            self.ui.stop()

    # ---------- run ----------

    def run(self) -> None:
        self.icon.run()
