"""Global hotkey handling: hold-to-talk and toggle modes.

Two paths, because the `keyboard` package treats them differently:

* A single key (``right ctrl``, ``f9``) is watched through a raw hook, matching scan
  codes. Bare modifiers are unreliable as registered hotkeys, and a hook also gives an
  exact key-up event instead of polling. Such keys are not suppressed - holding Right
  Ctrl still behaves as Ctrl for anything else listening.
* A combination (``ctrl+alt+space``) is registered as a real hotkey with suppression, so
  the keystroke never reaches the window underneath, and the release is found by polling,
  which is what the package supports.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

import keyboard

log = logging.getLogger(__name__)

POLL_INTERVAL = 0.02

MIRRORED = {"right": "left", "left": "right"}


class HotkeyError(RuntimeError):
    pass


def scan_codes_for(key: str) -> set[int]:
    """Scan codes of a single key, keeping left and right modifiers apart.

    ``key_to_scan_codes("right ctrl")`` also returns the generic Ctrl code, which would
    make the left key trigger too, so the mirror side's codes are subtracted. The generic
    code belongs to the left key, whose own list is then a subset of the right one, so an
    empty result means "keep what we had" rather than "this key does not exist".
    """
    codes = set(keyboard.key_to_scan_codes(key))
    side, _, rest = key.partition(" ")
    mirror = MIRRORED.get(side)
    if mirror and rest:
        try:
            exclusive = codes - set(keyboard.key_to_scan_codes(f"{mirror} {rest}"))
        except ValueError:
            exclusive = codes
        return exclusive or codes
    return codes


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
        self.combo = combo.strip()
        self.mode = mode
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_cancel = on_cancel
        self._handle = None
        self._hook = None
        self._codes: set[int] = set()
        self._escape_codes: set[int] = set()
        self._active = False       # combination path: the hotkey has fired
        self._key_down = False     # single-key path: the key is physically held
        self._recording = False    # single-key path: a recording is open
        self._stop_watch = threading.Event()

    @property
    def parts(self) -> list[str]:
        return [part.strip() for part in self.combo.split("+") if part.strip()]

    @property
    def is_single_key(self) -> bool:
        return len(self.parts) == 1

    # ---------- lifecycle ----------

    def start(self) -> None:
        if self.is_single_key:
            self._start_hook()
        else:
            self._start_hotkey()
        log.info(
            "hotkey %s registered in %s mode (%s)",
            self.combo,
            self.mode,
            "hook" if self.is_single_key else "suppressed hotkey",
        )

    def stop(self) -> None:
        self._stop_watch.set()
        if self._handle is not None:
            try:
                keyboard.remove_hotkey(self._handle)
            except (KeyError, ValueError):
                pass
            self._handle = None
        if self._hook is not None:
            try:
                keyboard.unhook(self._hook)
            except (KeyError, ValueError):
                pass
            self._hook = None
        self._active = False
        self._key_down = False
        self._recording = False

    # ---------- single key: raw hook ----------

    def _start_hook(self) -> None:
        try:
            self._codes = scan_codes_for(self.combo)
        except ValueError as exc:
            raise HotkeyError(f"Unknown key '{self.combo}': {exc}") from exc
        if not self._codes:
            raise HotkeyError(f"Key '{self.combo}' has no scan code on this keyboard")
        try:
            self._escape_codes = set(keyboard.key_to_scan_codes("esc"))
        except ValueError:
            self._escape_codes = set()
        self._hook = keyboard.hook(self._on_event)

    def _on_event(self, event) -> None:  # noqa: ANN001 - keyboard.KeyboardEvent
        if event.scan_code in self._escape_codes:
            if self._recording and event.event_type == keyboard.KEY_DOWN:
                self._recording = False
                if self.on_cancel:
                    self.on_cancel()
            return
        if event.scan_code not in self._codes:
            return

        if event.event_type == keyboard.KEY_DOWN:
            if self._key_down:
                return  # auto-repeat while the key is held
            self._key_down = True
            if self.mode == "toggle" and self._recording:
                self._recording = False
                self.on_stop()
            else:
                self._recording = True
                self.on_start()
        elif event.event_type == keyboard.KEY_UP:
            self._key_down = False
            if self.mode != "toggle" and self._recording:
                self._recording = False
                self.on_stop()

    # ---------- combination: registered hotkey ----------

    def _start_hotkey(self) -> None:
        try:
            self._handle = keyboard.add_hotkey(
                self.combo, self._on_trigger, suppress=True, trigger_on_release=False
            )
        except Exception as exc:
            raise HotkeyError(f"Cannot register the hotkey '{self.combo}': {exc}") from exc

    def _on_trigger(self) -> None:
        if self.mode == "toggle":
            if self._active:
                self._active = False
                self.on_stop()
            else:
                self._active = True
                self.on_start()
                self._spawn(self._watch_cancel)
            return

        if self._active:
            return
        self._active = True
        self.on_start()
        self._spawn(self._watch_release)

    def _all_pressed(self) -> bool:
        for part in self.parts:
            try:
                if not keyboard.is_pressed(part):
                    return False
            except (ValueError, KeyError):
                # Unknown key name: treat as released rather than wait forever.
                return False
        return True

    def _watch_release(self) -> None:
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

    def _watch_cancel(self) -> None:
        """In toggle mode Esc aborts the recording without transcribing."""
        while not self._stop_watch.is_set() and self._active:
            if self._escape_pressed():
                self._active = False
                if self.on_cancel:
                    self.on_cancel()
                return
            self._stop_watch.wait(POLL_INTERVAL)

    def _spawn(self, target) -> None:  # noqa: ANN001
        threading.Thread(target=target, daemon=True).start()

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
