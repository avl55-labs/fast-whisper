"""The window shown once, the first time the app runs.

Picking a speech model is the one decision a new user cannot avoid: it costs a download
of between 80 MB and 1.6 GB, and it sets how long every phrase takes and how much of it
comes back wrong. Rather than pick silently and leave people wondering why dictation is
slow, or why it misspells names, the choice is put in front of them once, with what each
option is actually good for.
"""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable

from . import models
from .config import Config
from .widgets import (
    ACCENT,
    BG,
    BORDER,
    CARD,
    FONT,
    FONT_SMALL,
    FONT_TITLE,
    MUTED,
    TEXT,
    Button,
    Gauge,
)

log = logging.getLogger(__name__)

TIER_COLORS = {
    "Recommended": ACCENT,
    "Accurate": "#0f9d7d",
    "Balanced": "#6d7079",
    "Quick": "#c08a1e",
    "Instant": "#b25a3c",
}


class SetupWindow:
    """One-time model picker. `on_choose` is called with the model name."""

    def __init__(self, root: tk.Tk, cfg: Config, on_choose: Callable[[str], None]) -> None:
        self.cfg = cfg
        self.on_choose = on_choose
        self.selected = models.FEATURED[0].name
        self.rows: dict[str, dict] = {}

        self.win = tk.Toplevel(root)
        self.win.title("FastWhisper")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._later)

        self._build()
        self._highlight()
        self._centre()
        self.win.attributes("-topmost", True)
        self.win.after(400, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()

    # ---------- layout ----------

    def _build(self) -> None:
        header = tk.Frame(self.win, bg=BG)
        header.pack(fill="x", padx=32, pady=(26, 4))
        tk.Label(
            header, text="Choose a speech model", bg=BG, fg=TEXT, font=FONT_TITLE, anchor="w"
        ).pack(fill="x")
        tk.Label(
            header,
            text=(
                "It runs on this computer - nothing is uploaded. Bigger models understand "
                "more and make you wait longer. This one is downloaded once."
            ),
            bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=620,
        ).pack(fill="x", pady=(4, 0))

        body = tk.Frame(self.win, bg=BG)
        body.pack(fill="both", expand=True, padx=32, pady=(14, 6))
        for info in models.FEATURED:
            self._option(body, info)

        footer = tk.Frame(self.win, bg=BG)
        footer.pack(fill="x", padx=32, pady=(6, 24))
        tk.Label(
            footer,
            text=(
                "You can change this later in Settings, where five more models are waiting, "
                "including English-only ones that are faster at the same accuracy."
            ),
            bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=430,
        ).pack(side="left", fill="x", expand=True)

        Button(footer, "Use this model", self._confirm, primary=True).pack(side="right")
        Button(footer, "Decide later", self._later).pack(side="right", padx=(0, 8))

    def _option(self, parent: tk.Frame, info: models.ModelInfo) -> None:
        frame = tk.Frame(parent, bg=CARD, highlightthickness=2, highlightbackground=BORDER,
                         cursor="hand2")
        frame.pack(fill="x", pady=3)

        left = tk.Frame(frame, bg=CARD)
        left.pack(side="left", fill="x", expand=True, padx=16, pady=11)

        title_line = tk.Frame(left, bg=CARD)
        title_line.pack(fill="x")
        pill = tk.Label(
            title_line, text=info.tier.upper(), bg=CARD, fg=TIER_COLORS.get(info.tier, MUTED),
            font=("Segoe UI Semibold", 8),
        )
        pill.pack(side="left", padx=(0, 8))
        name = tk.Label(title_line, text=info.title, bg=CARD, fg=TEXT,
                        font=("Segoe UI Semibold", 11))
        name.pack(side="left")

        purpose = tk.Label(
            left, text=info.purpose, bg=CARD, fg=MUTED, font=FONT_SMALL,
            anchor="w", justify="left", wraplength=380,
        )
        purpose.pack(fill="x", pady=(3, 0))

        right = tk.Frame(frame, bg=CARD)
        right.pack(side="right", padx=16, pady=11)
        for label, value in (("Accuracy", info.accuracy), ("Speed", info.speed)):
            line = tk.Frame(right, bg=CARD)
            line.pack(anchor="e", pady=1)
            tk.Label(line, text=label, bg=CARD, fg=MUTED, font=FONT_SMALL, width=8,
                     anchor="e").pack(side="left")
            Gauge(line, value).pack(side="left", padx=(6, 0))
        meta = tk.Label(
            right, text=f"{info.size_gb:.2f} GB  -  {info.latency} per phrase",
            bg=CARD, fg=MUTED, font=FONT_SMALL, anchor="e",
        )
        meta.pack(anchor="e", pady=(4, 0))

        self.rows[info.name] = {"frame": frame}
        # The whole card is the target, not just the frame behind the labels.
        for widget in (frame, left, right, title_line, pill, name, purpose, meta):
            widget.bind("<Button-1>", lambda _e, n=info.name: self._select(n))

    def _centre(self) -> None:
        self.win.update_idletasks()
        width, height = self.win.winfo_width(), self.win.winfo_height()
        x = int((self.win.winfo_screenwidth() - width) / 2)
        y = int((self.win.winfo_screenheight() - height) / 2.4)
        self.win.geometry(f"+{max(0, x)}+{max(0, y)}")

    # ---------- selection ----------

    def _select(self, name: str) -> None:
        self.selected = name
        self._highlight()

    def _highlight(self) -> None:
        for name, row in self.rows.items():
            chosen = name == self.selected
            row["frame"].configure(highlightbackground=ACCENT if chosen else BORDER,
                                   highlightcolor=ACCENT if chosen else BORDER)

    # ---------- actions ----------

    def _confirm(self) -> None:
        chosen = self.selected
        self._close()
        self.on_choose(chosen)

    def _later(self) -> None:
        """Keeps the default and stops asking - the picker is a one-time thing."""
        self._close()
        self.on_choose(self.cfg.model)

    def _close(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
