"""Dialog that records the key combination you want to use.

Keys are recognised by scan code rather than by the name the `keyboard` package reports,
so the left and right modifiers stay apart - holding Right Alt should not register as a
plain Alt, otherwise the left one would trigger dictation too.
"""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable

import keyboard

from .config import Config
from .hotkey import HotkeyError, scan_codes_for
from .i18n import _

log = logging.getLogger(__name__)

# Sided names first: a lookup wins on the more specific entry.
MODIFIERS = [
    "left ctrl", "right ctrl",
    "left alt", "right alt",
    "left shift", "right shift",
    "left windows", "right windows",
]
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


def _code_map() -> dict[int, str]:
    mapping: dict[int, str] = {}
    for name in MODIFIERS:
        try:
            for code in scan_codes_for(name):
                mapping[code] = name
        except ValueError:
            continue
    return mapping


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
        self.codes = _code_map()
        self.pressed: list[str] = []
        self.captured = ""
        self._hook = None

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
        self._hook = keyboard.hook(self._on_event)

    def _centre(self) -> None:
        self.win.update_idletasks()
        width, height = self.win.winfo_width(), self.win.winfo_height()
        x = int((self.win.winfo_screenwidth() - width) / 2)
        y = int((self.win.winfo_screenheight() - height) / 2)
        self.win.geometry(f"+{x}+{y}")

    # ---------- capture ----------

    def _name_of(self, event) -> str:  # noqa: ANN001 - keyboard.KeyboardEvent
        return self.codes.get(event.scan_code) or (event.name or "").lower()

    def _on_event(self, event) -> None:  # noqa: ANN001 - runs on the keyboard hook thread
        name = self._name_of(event)
        if not name:
            return
        if name == "esc":
            if event.event_type == keyboard.KEY_DOWN:
                self.win.after(0, self.close)
            return

        if event.event_type == keyboard.KEY_DOWN:
            if name not in self.pressed:
                self.pressed.append(name)
            combo = build_combo(self.pressed)
            if combo:
                self.captured = combo
                self.win.after(0, self._show, combo)
        elif event.event_type == keyboard.KEY_UP and name in self.pressed:
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
            keyboard.parse_hotkey(combo)
        except Exception as exc:
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
        if self._hook is not None:
            try:
                keyboard.unhook(self._hook)
            except (KeyError, ValueError):
                pass
            self._hook = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        # The caller re-arms the hotkey it paused while this window was open.
        if self.on_close is not None and not self._saving:
            self.on_close()
