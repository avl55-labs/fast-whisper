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

from . import output, updater
from .config import CONFIG_PATH, Config
from .i18n import _
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
        self.detail = _("Starting...")
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
        items = [
            MenuItem(lambda item: self._title(), None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(_("Settings..."), self._open_settings, default=True),
            MenuItem(_("Copy last result"), self._copy_last),
        ]
        if updater.pending is not None:
            items += [
                Menu.SEPARATOR,
                MenuItem(
                    _("Update to {version}...").format(version=updater.pending.version),
                    self._open_updates,
                ),
            ]
        items += [Menu.SEPARATOR, MenuItem(_("Quit"), self._quit)]
        return Menu(*items)

    # ---------- actions ----------

    def refresh_menu(self) -> None:
        """Rebuilds the menu, which holds translated labels."""
        try:
            self.detail = self.app.ready_hint()
            self.icon.menu = self._menu()
            self.icon.update_menu()
            self.icon.title = self._title()
        except Exception:
            log.debug("could not rebuild the tray menu", exc_info=True)

    def rebuild_menu(self) -> None:
        """Rebuilds the menu without disturbing the status line above it."""
        try:
            self.icon.menu = self._menu()
            self.icon.update_menu()
        except Exception:
            log.debug("could not rebuild the tray menu", exc_info=True)

    def on_update(self, release) -> None:  # noqa: ANN001 - updater.Release
        """Says once, quietly, that a newer version exists. Nothing is installed."""
        self.rebuild_menu()
        try:
            self.icon.notify(
                _("Version {version} is available.").format(version=release.version),
                "FastWhisper",
            )
        except Exception:
            log.debug("could not show the update notification", exc_info=True)

    def _show_settings(self, page: str) -> None:
        # Kept separate from the menu callbacks: pystray hands its actions the icon and
        # the item, which a default argument would quietly swallow.
        if self.ui is None:
            _open(CONFIG_PATH)
            return
        self.ui.open_settings(self.app, self._capture_hotkey, self.refresh_menu, page=page)

    def _open_settings(self) -> None:
        self._show_settings("general")

    def _open_updates(self) -> None:
        self._show_settings("about")

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
