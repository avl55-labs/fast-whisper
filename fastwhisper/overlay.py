"""Floating panel that shows what the app is doing while you dictate.

The panel must never take focus: the text is pasted into whatever window was active when
the hotkey was pressed, so stealing focus would send the paste to the wrong place. That is
what the WS_EX_NOACTIVATE style below is for; WS_EX_TRANSPARENT additionally lets clicks
pass through to the window underneath.

Tk is not thread safe and owns the main thread, so the rest of the app never touches these
widgets directly - it posts callables through `UiHost.post`, which a periodic task drains.
"""
from __future__ import annotations

import ctypes
import logging
import queue
import tkinter as tk
from collections import deque
from typing import Callable

from PIL import ImageTk

from .config import Config
from .grains import COLUMNS, HEIGHT, WIDTH, GrainField, chroma_hex

log = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020

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
        self._photo: ImageTk.PhotoImage | None = None

        chroma = chroma_hex()
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.win.configure(bg=chroma)
        try:
            self.win.attributes("-transparentcolor", chroma)
        except tk.TclError:
            log.debug("transparent colour is unavailable, corners will be square")

        self.canvas = tk.Canvas(
            self.win, width=WIDTH, height=HEIGHT, bg=chroma, highlightthickness=0
        )
        self.canvas.pack()
        self.image_item = self.canvas.create_image(0, 0, anchor="nw")

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
        self.win.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def _apply_styles(self) -> None:
        """Marks the window as non-activating and click-through."""
        if self._styled:
            return
        try:
            self.win.update_idletasks()
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
            current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
                current | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT,
            )
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

        state = self.state if self.state != "hidden" else "processing"
        try:
            frame = self.field.render(state, self._phase, list(self._levels))
            self._photo = ImageTk.PhotoImage(frame)
            self.canvas.itemconfigure(self.image_item, image=self._photo)
        except Exception:
            log.exception("frame rendering failed")

        if abs(self._alpha - self._target_alpha) > 0.01:
            self._alpha += (self._target_alpha - self._alpha) * 0.3
            try:
                self.win.attributes("-alpha", max(0.0, min(1.0, self._alpha)))
            except tk.TclError:
                pass
            if self._alpha < 0.03 and self._target_alpha == 0.0:
                self.win.withdraw()


class UiHost:
    """Owns the Tk main loop and marshals calls from the app's worker threads."""

    def __init__(self, cfg: Config, level_of: Callable[[], float]) -> None:
        self.cfg = cfg
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("FastWhisper")
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

    def open_settings(self, app, capture: Callable[[], None]) -> None:  # noqa: ANN001
        """Opens the settings window on the Tk thread."""
        from .settings_window import SettingsWindow

        self.post(lambda: SettingsWindow.open(self.root, self.cfg, app, capture))

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
