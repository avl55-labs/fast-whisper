"""Short feedback beeps. Windows only, and never fatal if the device is busy."""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

try:
    import winsound
except ImportError:  # non-Windows, used during development only
    winsound = None  # type: ignore[assignment]


def _beep(frequency: int, duration_ms: int) -> None:
    if winsound is None:
        return

    def run() -> None:
        try:
            winsound.Beep(frequency, duration_ms)
        except Exception:
            log.debug("beep failed")

    threading.Thread(target=run, daemon=True).start()


def start() -> None:
    _beep(880, 70)


def stop() -> None:
    _beep(620, 70)


def error() -> None:
    _beep(300, 160)
