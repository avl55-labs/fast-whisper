"""Named-mutex guard so only one copy of the app runs per user session."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = r"Local\FastWhisper.SingleInstance"

_handle = None


def acquire() -> bool:
    """Returns True if this process is the only instance."""
    global _handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        _handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
    except (AttributeError, OSError):
        # Not on Windows: do not block startup over this.
        return True
