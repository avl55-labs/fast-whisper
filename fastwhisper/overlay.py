"""Floating panel that shows what the app is doing while you dictate.

The panel must never take focus: the text is pasted into whatever window was active when
the hotkey was pressed, so stealing focus would send the paste to the wrong place. That is
what the WS_EX_NOACTIVATE style below is for; WS_EX_TRANSPARENT additionally lets clicks
pass through to the window underneath.

Tk is not thread safe and owns the main thread, so the rest of the app never touches these
widgets directly - it posts callables through `UiHost.post`, which a periodic task drains.
"""
from __future__ import annotations

import logging
import queue
import tkinter as tk
from collections import deque
from typing import Callable

from .config import Config
from .grains import COLUMNS, HEIGHT, WIDTH, GrainField
from .icons import window_icon
from .layered import LayeredSurface, make_click_through, window_handle

log = logging.getLogger(__name__)

FRAME_MS = 33
MARGIN = 26  # distance from the top edge of the screen
ALPHA = 0.88


class Overlay:
    """The panel itself. All methods must run on the Tk thread."""

    def __init__(self, root: tk.Tk, cfg: Config, level_of: Callable[[], float]) -> None:
        self.cfg = cfg
        self.level_of = level_of
        self.state = "hidden"
        self.field = GrainField()
        self._phase = 0.0
        self._alpha = 0.0
        self._target_alpha = 0.0
        self._levels: deque[float] = deque([0.0] * COLUMNS, maxlen=COLUMNS)
        self._styled = False
        self._position = (0, 0)
        self.surface = LayeredSurface(WIDTH, HEIGHT)

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{WIDTH}x{HEIGHT}+0+0")

    # ---------- state ----------

    def show(self, state: str) -> None:
        if state == self.state:
            return
        if state == "recording":
            self._levels = deque([0.0] * COLUMNS, maxlen=COLUMNS)
        self.state = state
        self._place()
        self._target_alpha = ALPHA
        self.win.deiconify()
        self._apply_styles()
        self.win.attributes("-topmost", True)

    def hide(self) -> None:
        self.state = "hidden"
        self._target_alpha = 0.0

    def _place(self) -> None:
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        x = int((screen_w - WIDTH) / 2)
        if self.cfg.overlay_position == "bottom":
            y = screen_h - HEIGHT - 140
        elif self.cfg.overlay_position == "center":
            y = int((screen_h - HEIGHT) / 2)
        else:
            y = MARGIN
        self._position = (x, y)
        self.win.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def _apply_styles(self) -> None:
        """Marks the window as layered, non-activating and click-through."""
        if self._styled:
            return
        try:
            self.win.update_idletasks()
            make_click_through(window_handle(self.win))
            self._styled = True
        except Exception:
            log.exception("could not apply the overlay window styles")

    # ---------- animation ----------

    def tick(self) -> None:
        if self.state == "hidden" and self._alpha <= 0.02:
            return

        self._phase += 0.14
        if self.state == "recording":
            # Speech rarely exceeds an RMS of ~0.08, so scale it into a visible range.
            self._levels.appendleft(min(1.0, self.level_of() * 11.0))

        if abs(self._alpha - self._target_alpha) > 0.005:
            self._alpha += (self._target_alpha - self._alpha) * 0.3
        else:
            self._alpha = self._target_alpha

        state = self.state if self.state != "hidden" else "processing"
        try:
            frame = self.field.render(state, self._phase, list(self._levels))
            x, y = self._position
            self.surface.update(window_handle(self.win), frame, x, y, self._alpha)
        except Exception:
            log.exception("frame rendering failed")

        if self._alpha < 0.03 and self._target_alpha == 0.0:
            self.win.withdraw()


class UiHost:
    """Owns the Tk main loop and marshals calls from the app's worker threads."""

    def __init__(self, cfg: Config, level_of: Callable[[], float]) -> None:
        self.cfg = cfg
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("FastWhisper")
        # Every Toplevel inherits this, so the settings and capture windows get the mark
        # instead of Tk's default feather.
        try:
            from PIL import ImageTk

            self._icon = ImageTk.PhotoImage(window_icon(64))
            self.root.iconphoto(True, self._icon)
        except Exception:
            log.debug("could not set the window icon", exc_info=True)
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.overlay = Overlay(self.root, cfg, level_of)
        self._running = True

    def post(self, action: Callable[[], None]) -> None:
        """Thread-safe: queues work to run on the Tk thread."""
        self._queue.put(action)

    def on_state(self, state: str, detail: str) -> None:
        """Translates app states into overlay visibility."""
        if not self.cfg.overlay:
            self.post(self.overlay.hide)
            return
        if state == "recording":
            self.post(lambda: self.overlay.show("recording"))
        elif state == "working":
            self.post(lambda: self.overlay.show("processing"))
        else:
            self.post(self.overlay.hide)

    def open_hotkey_capture(
        self, on_save: Callable[[str], None], on_close: Callable[[], None]
    ) -> None:
        """Opens the key-capture window on the Tk thread."""
        from .hotkey_capture import HotkeyCapture

        self.post(lambda: HotkeyCapture(self.root, self.cfg, on_save, on_close))

    def open_settings(
        self, app, capture: Callable[[], None], on_language_change: Callable[[], None] | None = None
    ) -> None:  # noqa: ANN001
        """Opens the settings window on the Tk thread."""
        from .settings_window import SettingsWindow

        self.post(
            lambda: SettingsWindow.open(self.root, self.cfg, app, capture, on_language_change)
        )

    def refresh_settings_hotkey(self) -> None:
        """Updates the hotkey shown in the settings window, if it is open."""
        from .settings_window import SettingsWindow

        def apply() -> None:
            window = SettingsWindow._current
            if window is not None and window.alive:
                window.refresh_hotkey()

        self.post(apply)

    def open_setup(self, on_choose: Callable[[str], None]) -> None:
        """Opens the first-run model picker on the Tk thread."""
        from .setup_window import SetupWindow

        self.post(lambda: SetupWindow(self.root, self.cfg, on_choose))

    def _pump(self) -> None:
        while True:
            try:
                action = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                action()
            except Exception:
                log.exception("queued UI action failed")
        try:
            self.overlay.tick()
        except Exception:
            log.exception("overlay animation failed")
        if self._running:
            self.root.after(FRAME_MS, self._pump)

    def run(self) -> None:
        self.root.after(FRAME_MS, self._pump)
        self.root.mainloop()

    def stop(self) -> None:
        self._running = False
        self.post(self.root.quit)
