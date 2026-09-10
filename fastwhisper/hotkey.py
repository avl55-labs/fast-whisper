"""Global hotkey handling: hold-to-talk and toggle modes.

Both modes sit on the application's own keyboard hook, in `keys`, which reports the left
and right modifiers as the different keys they are and never injects anything to undo a
suppression. That removes the two problems the `keyboard` package had here:

* A suppressed chord no longer leaves a modifier stuck down. Only the last key of the
  chord is taken from the window underneath; Ctrl, Alt, Shift and Windows always pass
  through, so nothing ever has to be put back.
* The release of a chord is a real key-up event instead of a polling thread, so
  hold-to-talk stops when the key does rather than up to a poll interval later.

The callbacks run on the hook's worker thread rather than inside the hook procedure.
Windows unhooks a low-level keyboard hook whose procedure overruns `LowLevelHooksTimeout`
- 300 ms unless the machine says otherwise - and opening a microphone takes longer than
that, so doing it in the procedure used to cost the app its hotkey with no sign of why.

Whether a recording is in progress is asked of the application rather than remembered
here, so a recording that ends by some other route - too short, a microphone error - does
not leave the toggle out of step with what the app is actually doing.
"""
from __future__ import annotations

import logging
from typing import Callable

from . import keys

log = logging.getLogger(__name__)


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
        is_active: Callable[[], bool] | None = None,
    ) -> None:
        self.combo = combo.strip()
        self.mode = mode
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_cancel = on_cancel
        self.is_active = is_active or (lambda: self._recording)
        self._handle = None
        self._modifiers: tuple[frozenset[int], ...] = ()
        self._trigger: frozenset[int] = frozenset()
        self._trigger_down = False
        self._recording = False

    @property
    def is_single_key(self) -> bool:
        return not self._modifiers

    # ---------- lifecycle ----------

    def start(self) -> None:
        try:
            self._modifiers, self._trigger = keys.parse(self.combo)
        except keys.UnknownKey as exc:
            raise HotkeyError(f"Cannot use the hotkey '{self.combo}': {exc}") from exc

        keys.start()
        # A modifier left down by something else would make the first chord look wrong.
        keys.release_stuck_modifiers()
        self._handle = keys.listen(self._on_event)
        keys.suppress([(self._modifiers, self._trigger)])
        log.info(
            "hotkey %s registered in %s mode (%s)",
            self.combo,
            self.mode,
            "chord, trigger suppressed" if self._modifiers else "single key, passed through",
        )

    def stop(self) -> None:
        if self._handle is not None:
            keys.unlisten(self._handle)
            self._handle = None
        keys.suppress([])
        self._trigger_down = False
        self._recording = False

    # ---------- events ----------

    def _on_event(self, event: keys.KeyEvent) -> None:
        if event.vk == keys.VK_ESCAPE:
            if event.down and self.is_active():
                self._recording = False
                if self.on_cancel:
                    self.on_cancel()
            return

        if event.vk not in self._trigger:
            return

        if event.down:
            if self._trigger_down:
                return  # auto-repeat while the key is held
            self._trigger_down = True
            if not event.chord:
                # The key belongs to the hotkey, but its modifiers were not held.
                return
            if self.mode == "toggle" and self.is_active():
                self._recording = False
                self.on_stop()
            elif not self.is_active():
                self._recording = True
                self.on_start()
        else:
            self._trigger_down = False
            if self.mode != "toggle" and self.is_active():
                self._recording = False
                self.on_stop()


def normalize(combo: str) -> str:
    """Validates a hotkey string, raising HotkeyError if it names no real key."""
    try:
        keys.parse(combo)
    except keys.UnknownKey as exc:
        raise HotkeyError(f"Invalid hotkey '{combo}': {exc}") from exc
    return combo
