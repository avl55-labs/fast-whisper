"""Delivering recognized text to the focused window."""
from __future__ import annotations

import logging
import threading
import time

import keyboard
import pyperclip

log = logging.getLogger(__name__)

_clipboard_lock = threading.Lock()


def _set_clipboard(text: str) -> None:
    for attempt in range(5):
        try:
            pyperclip.copy(text)
            return
        except Exception:  # another app may hold the clipboard open
            time.sleep(0.05 * (attempt + 1))
    raise RuntimeError("clipboard is locked by another application")


def _get_clipboard() -> str:
    try:
        return pyperclip.paste()
    except Exception:
        return ""


def paste(text: str, restore_clipboard: bool = True) -> None:
    """Puts the text on the clipboard and sends Ctrl+V to the focused window."""
    with _clipboard_lock:
        previous = _get_clipboard() if restore_clipboard else None
        _set_clipboard(text)
        # Give the target window a moment; some apps ignore a paste sent too early.
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        if previous is not None:
            # Restore only after the paste had time to read the clipboard.
            time.sleep(0.4)
            try:
                _set_clipboard(previous)
            except Exception:
                log.debug("could not restore the previous clipboard content")


def type_text(text: str) -> None:
    """Types the text key by key. Slower, but works where Ctrl+V is blocked."""
    keyboard.write(text, delay=0.005)


def to_clipboard(text: str) -> None:
    with _clipboard_lock:
        _set_clipboard(text)


def deliver(text: str, mode: str) -> None:
    if not text:
        return
    if mode == "type":
        type_text(text)
    elif mode == "clipboard":
        to_clipboard(text)
    else:
        paste(text)
