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
import math
import queue
import tkinter as tk
from collections import deque
from typing import Callable

from .config import Config

log = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020

# Any colour that does not appear in the design; these pixels become fully transparent.
CHROMA = "#ff00fe"

WIDTH, HEIGHT = 320, 96
BAR_COUNT = 16
FRAME_MS = 33

PANEL = "#1b1c20"
BORDER = "#33353d"
CAPTION = "#8b8f9a"
ACCENT = {
    "recording": "#f2565b",
    "processing": "#e6a33c",
}


def _rounded_points(x0: float, y0: float, x1: float, y1: float, r: float) -> list[float]:
    """Polygon outline of a rounded rectangle, smoothed by the canvas."""
    return [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]


class Overlay:
    """The panel itself. All methods must run on the Tk thread."""

    def __init__(self, root: tk.Tk, cfg: Config, level_of: Callable[[], float]) -> None:
        self.cfg = cfg
        self.level_of = level_of
        self.state = "hidden"
        self._phase = 0.0
        self._alpha = 0.0
        self._target_alpha = 0.0
        self._levels: deque[float] = deque([0.0] * BAR_COUNT, maxlen=BAR_COUNT)
        self._styled = False

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.win.configure(bg=CHROMA)
        try:
            self.win.attributes("-transparentcolor", CHROMA)
        except tk.TclError:
            log.debug("transparent colour is unavailable, corners will be square")

        self.canvas = tk.Canvas(
            self.win, width=WIDTH, height=HEIGHT, bg=CHROMA, highlightthickness=0
        )
        self.canvas.pack()
        self._build()

    # ---------- drawing ----------

    def _build(self) -> None:
        self.canvas.create_polygon(
            _rounded_points(4, 4, WIDTH - 4, HEIGHT - 4, 20),
            smooth=True,
            fill=PANEL,
            outline=BORDER,
            width=1,
            tags="panel",
        )

        # Microphone glyph on the left.
        self.mic_parts = [
            self.canvas.create_oval(27, 18, 43, 40, fill=ACCENT["recording"], outline=""),
            self.canvas.create_rectangle(27, 26, 43, 34, fill=ACCENT["recording"], outline=""),
            self.canvas.create_arc(
                21, 26, 49, 48, start=180, extent=180, style=tk.ARC,
                outline=ACCENT["recording"], width=3,
            ),
            self.canvas.create_rectangle(33, 44, 37, 52, fill=ACCENT["recording"], outline=""),
        ]

        # Waveform bars.
        self.bars = []
        left, right = 68, WIDTH - 26
        step = (right - left) / BAR_COUNT
        for index in range(BAR_COUNT):
            x = left + index * step
            self.bars.append(
                self.canvas.create_rectangle(
                    x, 30, x + step - 4, 38, fill=ACCENT["recording"], outline=""
                )
            )

        self.caption = self.canvas.create_text(
            WIDTH / 2,
            HEIGHT - 22,
            text="",
            fill=CAPTION,
            font=("Segoe UI", 9),
        )

    def _paint(self) -> None:
        colour = ACCENT.get(self.state, ACCENT["recording"])
        for item in self.mic_parts:
            if self.canvas.type(item) == "arc":
                self.canvas.itemconfigure(item, outline=colour)
            else:
                self.canvas.itemconfigure(item, fill=colour)

        centre = 34
        left, right = 68, WIDTH - 26
        step = (right - left) / BAR_COUNT
        for index, bar in enumerate(self.bars):
            if self.state == "recording":
                value = self._levels[index]
            else:
                # A travelling wave, so it is obvious the app is still working.
                value = 0.18 + 0.42 * abs(math.sin(self._phase + index * 0.42))
            height = max(2.0, value * 22)
            x = left + index * step
            self.canvas.coords(bar, x, centre - height, x + step - 4, centre + height)
            self.canvas.itemconfigure(bar, fill=colour)

    # ---------- state ----------

    def show(self, state: str) -> None:
        if state == self.state:
            return
        self.state = state
        self.canvas.itemconfigure(
            self.caption,
            text="Listening - Esc to cancel" if state == "recording" else "Transcribing...",
        )
        if state == "recording":
            self._levels = deque([0.0] * BAR_COUNT, maxlen=BAR_COUNT)
        self._place()
        self._target_alpha = 0.96
        self.win.deiconify()
        self._apply_styles()

    def hide(self) -> None:
        self.state = "hidden"
        self._target_alpha = 0.0

    def _place(self) -> None:
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        x = int((screen_w - WIDTH) / 2)
        if self.cfg.overlay_position == "top":
            y = 80
        elif self.cfg.overlay_position == "center":
            y = int((screen_h - HEIGHT) / 2)
        else:
            y = screen_h - HEIGHT - 140
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
        if self.state == "recording":
            # Speech rarely exceeds an RMS of ~0.08, so scale it into a visible range.
            self._levels.appendleft(min(1.0, self.level_of() * 11.0))
        else:
            self._phase += 0.32

        if self.state != "hidden" or self._alpha > 0.01:
            self._paint()

        if abs(self._alpha - self._target_alpha) > 0.01:
            self._alpha += (self._target_alpha - self._alpha) * 0.35
            try:
                self.win.attributes("-alpha", max(0.0, min(1.0, self._alpha)))
            except tk.TclError:
                pass
            if self._alpha < 0.02 and self._target_alpha == 0.0:
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
