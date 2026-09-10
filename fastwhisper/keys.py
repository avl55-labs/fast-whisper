"""Low-level keyboard access: one hook this application owns, and key injection.

Why not the `keyboard` package
------------------------------
`keyboard.add_hotkey(combo, suppress=True)` cannot swallow a chord without first
swallowing its modifiers. It holds back every Ctrl press, waits to see whether the rest
of the chord follows, and when it does not, puts the held-back key back with
`keybd_event`. That call carries the scan code in a single byte and has no way to set
the extended flag, so a suppressed *right* Ctrl is put back as a plain, non-extended
Ctrl. The physical key-up that follows a moment later does carry the extended flag, so
it releases the other key, and Ctrl stays down - until some left Ctrl is pressed and
released and cancels it by accident.

Every Ctrl chord typed while the app ran was a chance to hit this. Switching keyboard
layout with the right-hand Ctrl+Shift hit it every time, and the machine was then left
behaving as though Ctrl were glued down: clicks became Ctrl-clicks, Space scrolled, and
the only cure was to press the *left* Ctrl.

So nothing here ever presses a key on the user's behalf to undo a suppression. At most
one key is suppressed - the last key of a registered chord, and only while that chord's
modifiers are physically held. Modifiers themselves always pass through untouched, so
there is never anything to put back.

The hook procedure is also on a deadline. Windows silently unhooks a low-level keyboard
hook whose callback overruns `LowLevelHooksTimeout`, 300 ms by default, and the app then
looks alive while its hotkey has quietly stopped working. Opening a microphone takes
longer than that on its own. So the procedure here records the key, decides whether to
swallow it, and returns; listeners run on a worker thread behind a queue.
"""
from __future__ import annotations

import ctypes
import logging
import queue
import threading
from ctypes import wintypes
from dataclasses import dataclass

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
LLKHF_INJECTED = 0x10

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAPVK_VK_TO_VSC_EX = 4

VK_ESCAPE = 0x1B

# Stamped into every event this application injects, so the hook can tell its own
# keystrokes from the user's and never reacts to a paste it sent itself.
MARKER = 0x46574853  # "FWHS"


# ---------------------------------------------------------------- structures


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    # Never sent, but INPUT is a union and the mouse arm is the widest one. Getting the
    # size wrong makes SendInput reject every call, so it is spelled out rather than
    # approximated with padding.
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


HOOKPROC = ctypes.CFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT)
)

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT)
]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT
]
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


# ---------------------------------------------------------------- key names

# The low-level hook reports the sided virtual key for every modifier, which is the one
# piece of the old scan-code arithmetic that is not needed any more: Right Ctrl is 0xA3
# and nothing else, so it can never be confused with the left one.
SIDED = {
    "left ctrl": 0xA2, "right ctrl": 0xA3,
    "left shift": 0xA0, "right shift": 0xA1,
    "left alt": 0xA4, "right alt": 0xA5,
    "left windows": 0x5B, "right windows": 0x5C,
}
EITHER_SIDE = {
    "ctrl": (0xA2, 0xA3),
    "shift": (0xA0, 0xA1),
    "alt": (0xA4, 0xA5),
    "windows": (0x5B, 0x5C),
}
ALIASES = {
    "control": "ctrl", "ctl": "ctrl",
    "win": "windows", "super": "windows", "cmd": "windows", "meta": "windows",
    "escape": "esc", "return": "enter", "del": "delete", "ins": "insert",
    "pgup": "page up", "pgdn": "page down", "prtsc": "print screen",
    "altgr": "right alt", "alt gr": "right alt",
    "lctrl": "left ctrl", "rctrl": "right ctrl",
    "lshift": "left shift", "rshift": "right shift",
    "lalt": "left alt", "ralt": "right alt",
    "capslock": "caps lock", "numlock": "num lock", "scrolllock": "scroll lock",
}
NAMED = {
    "esc": 0x1B, "tab": 0x09, "enter": 0x0D, "space": 0x20, "backspace": 0x08,
    "caps lock": 0x14, "num lock": 0x90, "scroll lock": 0x91, "pause": 0x13,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "page up": 0x21, "page down": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "print screen": 0x2C, "apps": 0x5D, "menu": 0x5D,
}
NAMED.update({f"f{index}": 0x6F + index for index in range(1, 25)})

# For showing a key back to the user, most specific name first.
_DISPLAY = {vk: name for name, vk in NAMED.items()}
_DISPLAY.update({vk: name for name, vk in SIDED.items()})


class UnknownKey(ValueError):
    pass


def _clean(name: str) -> str:
    name = " ".join(name.lower().split())
    return ALIASES.get(name, name)


def resolve(name: str) -> frozenset[int]:
    """Virtual keys a hotkey component may match.

    A sided name matches exactly one key; a bare ``ctrl`` matches either Ctrl, which is
    what someone writing ``ctrl+space`` means.
    """
    name = _clean(name)
    if not name:
        raise UnknownKey("empty key name")
    if name in SIDED:
        return frozenset({SIDED[name]})
    if name in EITHER_SIDE:
        return frozenset(EITHER_SIDE[name])
    if name in NAMED:
        return frozenset({NAMED[name]})
    if len(name) == 1:
        if name.isalnum():
            return frozenset({ord(name.upper())})
        code = user32.VkKeyScanW(name)
        if code != -1:
            return frozenset({code & 0xFF})
    raise UnknownKey(f"unknown key '{name}'")


def name_of(vk: int) -> str:
    """A name for a virtual key, for showing the user what they just pressed."""
    if vk in _DISPLAY:
        return _DISPLAY[vk]
    if 0x30 <= vk <= 0x5A:  # digits and letters
        return chr(vk).lower()
    scan = user32.MapVirtualKeyW(vk, 2) & 0xFFFF  # MAPVK_VK_TO_CHAR
    if scan:
        return chr(scan).lower()
    return f"0x{vk:02x}"


Chord = tuple[tuple[frozenset[int], ...], frozenset[int]]


def parse(combo: str) -> Chord:
    """Splits ``ctrl+space`` into the modifiers to require and the key that triggers.

    A lone key - ``right ctrl``, ``f9`` - comes back with no modifiers, and is never
    suppressed: it should keep working as itself for everything else on the machine.
    """
    parts = [part for part in (piece.strip() for piece in combo.split("+")) if part]
    if not parts:
        raise UnknownKey(f"empty hotkey '{combo}'")
    resolved = [resolve(part) for part in parts]
    return tuple(resolved[:-1]), resolved[-1]


# ---------------------------------------------------------------- the hook


@dataclass(frozen=True)
class KeyEvent:
    vk: int
    down: bool
    # True when this key completed a registered chord. Decided inside the hook, with the
    # modifier state as it was at that instant, because by the time a listener sees the
    # event the user may already have let go.
    chord: bool = False

    @property
    def name(self) -> str:
        return name_of(self.vk)


_lock = threading.RLock()
_listeners: list = []
_chords: list[Chord] = []
_down: set[int] = set()          # physically held, as seen by this hook
_armed: set[int] = set()         # triggers whose key-down completed a chord
_swallowed: set[int] = set()     # triggers whose key-down we suppressed
_events: "queue.Queue[KeyEvent | None]" = queue.Queue()

_hook_handle = None
_hook_thread: threading.Thread | None = None
_hook_thread_id = 0
_worker: threading.Thread | None = None
_proc = None  # a live reference to the callback: letting it be collected crashes


def _held(spec: frozenset[int]) -> bool:
    return bool(_down & spec)


def _classify(vk: int, down: bool) -> tuple[bool, bool]:
    """Returns (completes a chord, should be suppressed). Runs inside the hook."""
    if down:
        _down.add(vk)
    else:
        _down.discard(vk)

    for modifiers, trigger in _chords:
        if vk not in trigger:
            continue
        if down:
            if all(_held(modifier) for modifier in modifiers):
                _armed.add(vk)
                if modifiers:
                    # Only a real chord is taken away from the window underneath. A lone
                    # key stays usable as itself.
                    _swallowed.add(vk)
                    return True, True
                return True, False
            return False, False
        # Key-up: pair it with whatever the key-down decided, rather than asking again.
        was_chord = vk in _armed
        _armed.discard(vk)
        if vk in _swallowed:
            _swallowed.discard(vk)
            return was_chord, True
        return was_chord, False
    return False, False


def _hook_proc(n_code, w_param, l_param):  # noqa: ANN001, ANN202 - a Windows callback
    suppress = False
    try:
        if n_code == HC_ACTION:
            info = l_param.contents
            if info.dwExtraInfo != MARKER:
                down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                up = w_param in (WM_KEYUP, WM_SYSKEYUP)
                if down or up:
                    chord, suppress = _classify(info.vkCode, down)
                    _events.put_nowait(KeyEvent(info.vkCode, down, chord))
    except Exception:  # a raising hook procedure would take the whole input stack down
        suppress = False
    if suppress:
        return 1
    return user32.CallNextHookEx(None, n_code, w_param, l_param)


def _pump() -> None:
    """Owns the hook. A low-level hook needs a message loop on its own thread."""
    global _hook_handle, _hook_thread_id, _proc
    _hook_thread_id = kernel32.GetCurrentThreadId()
    _proc = HOOKPROC(_hook_proc)
    _hook_handle = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, _proc, kernel32.GetModuleHandleW(None), 0
    )
    if not _hook_handle:
        log.error("could not install the keyboard hook: %s", ctypes.get_last_error())
        return
    log.info("keyboard hook installed")
    message = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))
    user32.UnhookWindowsHookEx(_hook_handle)
    _hook_handle = None
    log.info("keyboard hook removed")


def _deliver() -> None:
    while True:
        event = _events.get()
        if event is None:
            return
        with _lock:
            listeners = list(_listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                log.exception("a key listener failed")


def start() -> None:
    """Installs the hook. Safe to call repeatedly."""
    global _hook_thread, _worker
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_deliver, name="keys-worker", daemon=True)
            _worker.start()
        if _hook_thread is not None and _hook_thread.is_alive():
            return
        _hook_thread = threading.Thread(target=_pump, name="keys-hook", daemon=True)
        _hook_thread.start()


def stop() -> None:
    global _hook_thread
    with _lock:
        thread, _hook_thread = _hook_thread, None
        _chords.clear()
        _listeners.clear()
    _down.clear()
    _armed.clear()
    _swallowed.clear()
    if thread is not None and _hook_thread_id:
        user32.PostThreadMessageW(_hook_thread_id, WM_QUIT, 0, 0)
        thread.join(timeout=2.0)


def listen(callback) -> object:  # noqa: ANN001
    """Registers a listener, called on the worker thread. Returns a handle for `unlisten`."""
    start()
    with _lock:
        _listeners.append(callback)
    return callback


def unlisten(handle) -> None:  # noqa: ANN001
    with _lock:
        if handle in _listeners:
            _listeners.remove(handle)


def suppress(chords: list[Chord]) -> None:
    """Replaces the set of chords taken away from the window underneath."""
    with _lock:
        _chords[:] = chords
    _armed.clear()
    _swallowed.clear()


# ---------------------------------------------------------------- injection


def _scan_of(vk: int) -> tuple[int, bool]:
    code = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX)
    return code & 0xFF, (code >> 8) == 0xE0


def _send(inputs: list[INPUT]) -> None:
    if not inputs:
        return
    array = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise OSError(f"SendInput sent {sent} of {len(inputs)} events: {ctypes.get_last_error()}")


def _key_input(vk: int, up: bool) -> INPUT:
    scan, extended = _scan_of(vk)
    flags = KEYEVENTF_KEYUP if up else 0
    if extended:
        # The flag the `keyboard` package could not set, and the whole reason a right
        # Ctrl used to be released as a left one.
        flags |= KEYEVENTF_EXTENDEDKEY
    event = INPUT(type=INPUT_KEYBOARD)
    event.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=MARKER)
    return event


def tap(*vks: int) -> None:
    """Presses the keys in order and releases them in reverse, as one atomic batch."""
    inputs = [_key_input(vk, False) for vk in vks]
    inputs += [_key_input(vk, True) for vk in reversed(vks)]
    _send(inputs)


def type_unicode(text: str) -> None:
    """Types text as characters rather than keystrokes.

    Every character is delivered as itself, so the result does not depend on the layout
    that happens to be active - which matters here, because the text is often Russian and
    the layout is often not.
    """
    inputs: list[INPUT] = []
    for code in _utf16_codes(text):
        for up in (False, True):
            event = INPUT(type=INPUT_KEYBOARD)
            event.ki = KEYBDINPUT(
                wVk=0,
                wScan=code,
                dwFlags=KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0),
                time=0,
                dwExtraInfo=MARKER,
            )
            inputs.append(event)
        if len(inputs) >= 200:  # SendInput takes a batch; keep the batches sane
            _send(inputs)
            inputs = []
    _send(inputs)


def _utf16_codes(text: str) -> list[int]:
    """UTF-16 code units, because that is the unit `KEYEVENTF_UNICODE` carries."""
    encoded = text.encode("utf-16-le", "surrogatepass")
    return [int.from_bytes(encoded[index:index + 2], "little")
            for index in range(0, len(encoded), 2)]


MODIFIER_VKS = (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C)


def stuck_modifiers() -> list[int]:
    """Modifiers Windows believes are held that were never physically pressed.

    Anything in this list is a key some program injected and failed to release. The app
    no longer creates them, but it has created plenty in the past, and other tools do it
    too, so it is worth clearing before sending a paste that a stray Ctrl or Shift would
    turn into a different command.
    """
    return [
        vk for vk in MODIFIER_VKS
        if (user32.GetAsyncKeyState(vk) & 0x8000) and vk not in _down
    ]


def release_stuck_modifiers() -> list[int]:
    stuck = stuck_modifiers()
    if stuck:
        log.info("releasing stuck modifiers: %s", ", ".join(name_of(vk) for vk in stuck))
        _send([_key_input(vk, True) for vk in stuck])
    return stuck
