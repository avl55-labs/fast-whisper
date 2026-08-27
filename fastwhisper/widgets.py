"""Small widget kit for the settings window.

Tk has no rounded containers or switches, so the few pieces the design needs are drawn on
canvases here. Everything is plain Tk: no extra dependency, and it matches the rest of the
app, which already renders its own artwork.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

# Light palette, close to the Windows 11 settings surfaces.
BG = "#f3f3f5"
CARD = "#ffffff"
BORDER = "#e3e3e8"
TEXT = "#1b1c1f"
MUTED = "#6d7079"
ACCENT = "#3b7ff5"
ACCENT_DIM = "#c9d9fb"
TRACK = "#c8cad1"
DISABLED = "#b4b7be"
SIDEBAR = "#ebebef"
SIDEBAR_ACTIVE = "#ffffff"

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_SECTION = ("Segoe UI Semibold", 10)
FONT_TITLE = ("Segoe UI Semibold", 15)


def section_label(parent: tk.Misc, text: str) -> tk.Label:
    label = tk.Label(parent, text=text, bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w")
    label.pack(fill="x", padx=4, pady=(16, 6))
    return label


class Card(tk.Frame):
    """White panel that groups related rows."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=BORDER, padx=1, pady=1)
        self.pack(fill="x", pady=(0, 4))
        self.inner = tk.Frame(self, bg=CARD)
        self.inner.pack(fill="both", expand=True)

    def row(
        self, title: str, subtitle: str = "", icon=None, wrap: int = 430
    ) -> tuple[tk.Frame, tk.Frame]:  # noqa: ANN001
        """Adds a row and returns (row frame, right-hand slot for the control)."""
        if self.inner.winfo_children():
            tk.Frame(self.inner, bg=BORDER, height=1).pack(fill="x", padx=14)

        row = tk.Frame(self.inner, bg=CARD)
        row.pack(fill="x", padx=16, pady=11)

        if icon is not None:
            holder = tk.Label(row, image=icon, bg=CARD)
            holder.image = icon  # keep a reference; Tk does not own the PhotoImage
            holder.pack(side="left", padx=(0, 12))

        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=CARD, fg=TEXT, font=FONT, anchor="w").pack(fill="x")
        if subtitle:
            tk.Label(
                text, text=subtitle, bg=CARD, fg=MUTED, font=FONT_SMALL, anchor="w",
                justify="left", wraplength=wrap,
            ).pack(fill="x")

        slot = tk.Frame(row, bg=CARD)
        slot.pack(side="right", padx=(12, 0))
        return row, slot


class Switch(tk.Canvas):
    """Two-state toggle with an animated knob."""

    WIDTH, HEIGHT = 42, 22

    def __init__(self, parent: tk.Misc, value: bool, on_change: Callable[[bool], None]) -> None:
        super().__init__(
            parent, width=self.WIDTH, height=self.HEIGHT,
            bg=CARD, highlightthickness=0, cursor="hand2",
        )
        self.value = value
        self.on_change = on_change
        self._knob = 0.0 if not value else 1.0
        self.bind("<Button-1>", self._clicked)
        self._draw()

    def _clicked(self, _event: tk.Event) -> None:
        self.value = not self.value
        self.on_change(self.value)
        self._animate()

    def set(self, value: bool) -> None:
        if value == self.value:
            return
        self.value = value
        self._animate()

    def _animate(self) -> None:
        target = 1.0 if self.value else 0.0
        if abs(self._knob - target) < 0.02:
            self._knob = target
            self._draw()
            return
        self._knob += (target - self._knob) * 0.35
        self._draw()
        self.after(16, self._animate)

    def _draw(self) -> None:
        self.delete("all")
        radius = self.HEIGHT / 2
        fill = ACCENT if self.value else TRACK
        # Track: two circles and a rectangle make the pill.
        self.create_oval(0, 0, self.HEIGHT, self.HEIGHT, fill=fill, outline="")
        self.create_oval(
            self.WIDTH - self.HEIGHT, 0, self.WIDTH, self.HEIGHT, fill=fill, outline=""
        )
        self.create_rectangle(radius, 0, self.WIDTH - radius, self.HEIGHT, fill=fill, outline="")
        # Knob.
        travel = self.WIDTH - self.HEIGHT
        x = 2 + self._knob * travel
        self.create_oval(x, 2, x + self.HEIGHT - 4, self.HEIGHT - 2, fill="white", outline="")


class Dropdown(tk.Frame):
    """Read-only option menu with a flat look."""

    def __init__(
        self,
        parent: tk.Misc,
        options: Sequence[tuple[str, object]],
        value: object,
        on_change: Callable[[object], None],
        width: int = 18,
    ) -> None:
        super().__init__(parent, bg=CARD)
        self.options = list(options)
        self.on_change = on_change
        labels = [label for label, _ in self.options]
        current = next((label for label, code in self.options if code == value), labels[0])

        self.var = tk.StringVar(value=current)
        self.menu = tk.OptionMenu(self, self.var, *labels, command=self._changed)
        self.menu.configure(
            bg=CARD, fg=TEXT, font=FONT, activebackground=BG, activeforeground=TEXT,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER,
            relief="flat", anchor="e", width=width, cursor="hand2", pady=2,
        )
        self.menu["menu"].configure(bg=CARD, fg=TEXT, font=FONT, activebackground=ACCENT_DIM,
                                    activeforeground=TEXT, relief="flat")
        self.menu.pack()

    def _changed(self, label: str) -> None:
        for text, code in self.options:
            if text == label:
                self.on_change(code)
                return

    def set(self, value: object) -> None:
        for label, code in self.options:
            if code == value:
                self.var.set(label)
                return


class Button(tk.Label):
    """Flat button; `primary` paints it in the accent colour."""

    def __init__(
        self, parent: tk.Misc, text: str, command: Callable[[], None], primary: bool = False
    ) -> None:
        self.primary = primary
        self.command = command
        self.enabled = True
        super().__init__(
            parent,
            text=text,
            font=FONT,
            bg=ACCENT if primary else CARD,
            fg="white" if primary else TEXT,
            padx=14,
            pady=5,
            cursor="hand2",
            highlightthickness=0 if primary else 1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
        )
        self.bind("<Button-1>", self._clicked)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _clicked(self, _event: tk.Event) -> None:
        if self.enabled:
            self.command()

    def _enter(self, _event: tk.Event) -> None:
        if self.enabled:
            self.configure(bg="#2f6fe0" if self.primary else BG)

    def _leave(self, _event: tk.Event) -> None:
        self.configure(bg=ACCENT if self.primary else CARD)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.configure(
            fg=("white" if self.primary else TEXT) if enabled else DISABLED,
            cursor="hand2" if enabled else "arrow",
        )


class Gauge(tk.Canvas):
    """Segmented bar, the way a rating is shown in a model list."""

    SEGMENTS = 5
    SEGMENT_W = 9
    SEGMENT_H = 3
    GAP = 3

    def __init__(self, parent: tk.Misc, value: int, colour: str = ACCENT) -> None:
        width = self.SEGMENTS * (self.SEGMENT_W + self.GAP)
        super().__init__(parent, width=width, height=10, bg=CARD, highlightthickness=0)
        for index in range(self.SEGMENTS):
            x = index * (self.SEGMENT_W + self.GAP)
            self.create_rectangle(
                x, 3, x + self.SEGMENT_W, 3 + self.SEGMENT_H,
                fill=colour if index < value else "#dfe0e5", outline="",
            )


class ScrollArea(tk.Frame):
    """Vertically scrollable page body."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scroll = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=BG)

        self.body.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width)
        )
        self.canvas.configure(yscrollcommand=self.scroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        # add="+" keeps every page's handler; each ignores the wheel unless visible.
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event: tk.Event) -> None:
        try:
            if self.canvas.winfo_ismapped():
                self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass
