"""Delivering recognized text to the focused window."""
from __future__ import annotations

import logging
import threading
import time

import pyperclip

from . import keys

log = logging.getLogger(__name__)

_clipboard_lock = threading.Lock()

VK_CONTROL = 0x11
VK_V = 0x56


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


def paste(text: str, restore_clipboard: bool = False) -> None:
    """Puts the text on the clipboard and sends Ctrl+V to the focused window.

    The text is left on the clipboard afterwards by default. A paste can miss - the window
    lost focus, the application ignores a synthetic Ctrl+V - and then the only copy of what
    you just said would be gone.

    Any modifier some other program has left held down is released first. Ctrl+V with a
    stray Shift on top is Ctrl+Shift+V, which pastes as plain text in some editors and
    does something else entirely in others.
    """
    with _clipboard_lock:
        previous = _get_clipboard() if restore_clipboard else None
        _set_clipboard(text)
        keys.release_stuck_modifiers()
        # Give the target window a moment; some apps ignore a paste sent too early.
        time.sleep(0.05)
        keys.tap(VK_CONTROL, VK_V)
        if previous is not None:
            # Restore only after the paste had time to read the clipboard.
            time.sleep(0.4)
            try:
                _set_clipboard(previous)
            except Exception:
                log.debug("could not restore the previous clipboard content")


def type_text(text: str) -> None:
    """Types the text character by character. Slower, but works where Ctrl+V is blocked.

    The characters are sent as themselves rather than as keystrokes, so what arrives does
    not depend on the keyboard layout that happens to be active. Dictating Russian into a
    window while the layout is English used to produce nothing usable.
    """
    keys.release_stuck_modifiers()
    keys.type_unicode(text)


def to_clipboard(text: str) -> None:
    with _clipboard_lock:
        _set_clipboard(text)


def deliver(text: str, mode: str, keep_clipboard: bool = True) -> None:
    if not text:
        return
    if mode == "type":
        type_text(text)
        if keep_clipboard:
            to_clipboard(text)
    elif mode == "clipboard":
        to_clipboard(text)
    else:
        paste(text, restore_clipboard=not keep_clipboard)
