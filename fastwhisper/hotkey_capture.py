"""Dialog that records the key combination you want to use.

Keys are identified by their virtual key code, which the low-level hook reports with the
side already resolved: Right Ctrl arrives as 0xA3 and nothing else. Holding Right Alt
therefore records as Right Alt rather than as a plain Alt that the left one would also
trigger.
"""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable

from . import keys
from .config import Config
from .hotkey import HotkeyError
from .i18n import _

log = logging.getLogger(__name__)

MODIFIER_NAMES = {
    0xA2: "left ctrl", 0xA3: "right ctrl",
    0xA0: "left shift", 0xA1: "right shift",
    0xA4: "left alt", 0xA5: "right alt",
    0x5B: "left windows", 0x5C: "right windows",
}
GENERIC = {
    "left ctrl": "ctrl", "right ctrl": "ctrl",
    "left alt": "alt", "right alt": "alt",
    "left shift": "shift", "right shift": "shift",
    "left windows": "windows", "right windows": "windows",
}
ORDER = ["ctrl", "alt", "shift", "windows"]

BACKGROUND = "#1b1c20"
FOREGROUND = "#e8e9ec"
MUTED = "#8b8f9a"
ACCENT = "#5b8def"


def build_combo(pressed: list[str]) -> str:
    """Turns the set of held keys into a hotkey string."""
    modifiers = [key for key in pressed if key in GENERIC]
    others = [key for key in pressed if key not in GENERIC]

    if not others:
        if len(modifiers) == 1:
            # A single modifier keeps its side: "right ctrl" is a useful push-to-talk key.
            return modifiers[0]
        names = sorted({GENERIC[key] for key in modifiers}, key=ORDER.index)
        return "+".join(names)

    names = sorted({GENERIC[key] for key in modifiers}, key=ORDER.index)
    return "+".join(names + others[:1])


class HotkeyCapture:
    """Modal-ish window that listens for the next key combination."""

    def __init__(
        self,
        root: tk.Tk,
        cfg: Config,
        on_save: Callable[[str], None],
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.on_save = on_save
        self.on_close = on_close
        self._saving = False
        self.pressed: list[str] = []
        self.captured = ""
        self._handle = None

        self.win = tk.Toplevel(root)
        self.win.title(_("FastWhisper - set hotkey"))
        self.win.configure(bg=BACKGROUND)
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        tk.Label(
            self.win,
            text=_("Press the key or combination you want to use"),
            bg=BACKGROUND, fg=FOREGROUND, font=("Segoe UI", 11),
        ).pack(padx=28, pady=(22, 6))

        self.value = tk.Label(
            self.win,
            text=cfg.hotkey.upper(),
            bg=BACKGROUND, fg=ACCENT, font=("Segoe UI Semibold", 20),
        )
        self.value.pack(padx=28, pady=6)

        self.hint = tk.Label(
            self.win,
            text=_(
                "A single key such as Right Ctrl is the easiest to hold.\n"
                "A combination is swallowed while FastWhisper runs, a single key is not.\n"
                "Escape closes this window without changing anything."
            ),
            bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9), justify="center",
        )
        self.hint.pack(padx=28, pady=(6, 14))

        buttons = tk.Frame(self.win, bg=BACKGROUND)
        buttons.pack(pady=(0, 20))
        self.save_button = tk.Button(
            buttons, text=_("Save"), width=12, command=self.save, state="disabled",
            relief="flat", bg=ACCENT, fg="white", activebackground="#4a76cc",
        )
        self.save_button.pack(side="left", padx=6)
        tk.Button(
            buttons, text=_("Cancel"), width=12, command=self.close,
            relief="flat", bg="#2a2c33", fg=FOREGROUND, activebackground="#35373f",
        ).pack(side="left", padx=6)

        self._centre()
        self.win.focus_force()
        keys.start()
        self._handle = keys.listen(self._on_event)

    def _centre(self) -> None:
        self.win.update_idletasks()
        width, height = self.win.winfo_width(), self.win.winfo_height()
        x = int((self.win.winfo_screenwidth() - width) / 2)
        y = int((self.win.winfo_screenheight() - height) / 2)
        self.win.geometry(f"+{x}+{y}")

    # ---------- capture ----------

    def _name_of(self, event: keys.KeyEvent) -> str:
        return MODIFIER_NAMES.get(event.vk) or event.name

    def _on_event(self, event: keys.KeyEvent) -> None:  # runs on the hook's worker thread
        name = self._name_of(event)
        if not name:
            return
        if name == "esc":
            if event.down:
                self.win.after(0, self.close)
            return

        if event.down:
            if name not in self.pressed:
                self.pressed.append(name)
            combo = build_combo(self.pressed)
            if combo:
                self.captured = combo
                self.win.after(0, self._show, combo)
        elif name in self.pressed:
            self.pressed.remove(name)

    def _show(self, combo: str) -> None:
        self.value.configure(text=combo.upper())
        self.save_button.configure(state="normal")

    # ---------- actions ----------

    def save(self) -> None:
        combo = self.captured
        if not combo:
            return
        try:
            keys.parse(combo)
        except keys.UnknownKey as exc:
            self.hint.configure(
                text=_("{combo} cannot be used: {error}").format(combo=combo, error=exc)
            )
            return
        self._saving = True
        self.close()
        try:
            self.on_save(combo)
        except HotkeyError as exc:
            log.error("%s", exc)

    def close(self) -> None:
        if self._handle is not None:
            keys.unlisten(self._handle)
            self._handle = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        # The caller re-arms the hotkey it paused while this window was open.
        if self.on_close is not None and not self._saving:
            self.on_close()
