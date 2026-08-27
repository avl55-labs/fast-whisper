"""Run at logon through the per-user Run key (no admin rights needed)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "FastWhisper"

try:
    import winreg
except ImportError:  # non-Windows, development only
    winreg = None  # type: ignore[assignment]


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    script = Path(sys.argv[0]).resolve()
    return f'"{Path(sys.executable)}" "{script}"'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def enable() -> None:
    if winreg is None:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
    log.info("autostart enabled")


def disable() -> None:
    if winreg is None:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        log.info("autostart disabled")
    except OSError:
        pass


def toggle() -> bool:
    if is_enabled():
        disable()
        return False
    enable()
    return True
