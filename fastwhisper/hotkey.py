"""Global hotkey handling: hold-to-talk and toggle modes."""
from __future__ import annotations

import logging
import threading
from typing import Callable

import keyboard

log = logging.getLogger(__name__)

POLL_INTERVAL = 0.02


class HotkeyError(RuntimeError):
    pass


class HotkeyListener:
    """Watches one global hotkey and reports press/release or toggle events."""

    def __init__(
        self,
        combo: str,
        mode: str,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        self.combo = combo
        self.mode = mode
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_cancel = on_cancel
        self._handle = None
        self._active = False
        self._watcher: threading.Thread | None = None
        self._stop_watch = threading.Event()

    @property
    def parts(self) -> list[str]:
        return [part.strip() for part in self.combo.split("+") if part.strip()]

    def start(self) -> None:
        try:
            self._handle = keyboard.add_hotkey(
                self.combo, self._on_trigger, suppress=True, trigger_on_release=False
            )
        except Exception as exc:
            raise HotkeyError(f"Cannot register the hotkey '{self.combo}': {exc}") from exc
        log.info("hotkey %s registered in %s mode", self.combo, self.mode)

    def stop(self) -> None:
        self._stop_watch.set()
        if self._handle is not None:
            try:
                keyboard.remove_hotkey(self._handle)
            except (KeyError, ValueError):
                pass
            self._handle = None
        if self._active:
            self._active = False

    def _on_trigger(self) -> None:
        if self.mode == "toggle":
            if self._active:
                self._active = False
                self.on_stop()
            else:
                self._active = True
                self.on_start()
                self._watch_cancel()
            return

        # Hold mode: the hotkey fired on press, so wait for the release.
        if self._active:
            return
        self._active = True
        self.on_start()
        self._watch_release()

    def _all_pressed(self) -> bool:
        for part in self.parts:
            try:
                if not keyboard.is_pressed(part):
                    return False
            except (ValueError, KeyError):
                # Unknown key name: assume it is no longer held rather than hang.
                return False
        return True

    def _watch_release(self) -> None:
        def run() -> None:
            while not self._stop_watch.is_set():
                if not self._all_pressed():
                    break
                if self._escape_pressed():
                    self._active = False
                    if self.on_cancel:
                        self.on_cancel()
                    return
                self._stop_watch.wait(POLL_INTERVAL)
            self._active = False
            self.on_stop()

        self._spawn(run)

    def _watch_cancel(self) -> None:
        """In toggle mode Esc aborts the recording without transcribing."""

        def run() -> None:
            while not self._stop_watch.is_set() and self._active:
                if self._escape_pressed():
                    self._active = False
                    if self.on_cancel:
                        self.on_cancel()
                    return
                self._stop_watch.wait(POLL_INTERVAL)

        self._spawn(run)

    def _spawn(self, target) -> None:  # noqa: ANN001
        self._watcher = threading.Thread(target=target, daemon=True)
        self._watcher.start()

    @staticmethod
    def _escape_pressed() -> bool:
        try:
            return keyboard.is_pressed("esc")
        except Exception:
            return False


def normalize(combo: str) -> str:
    """Validates a hotkey string, raising HotkeyError if the syntax is wrong."""
    try:
        keyboard.parse_hotkey(combo)
    except Exception as exc:
        raise HotkeyError(f"Invalid hotkey '{combo}': {exc}") from exc
    return combo
