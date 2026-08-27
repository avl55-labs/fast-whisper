"""Entry point: wires the config, the core app and the tray together."""
from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import sys
import threading

from .config import LOG_PATH, Config
from .single_instance import acquire

# The Xet transfer backend of huggingface_hub stalls behind some networks and there is no
# progress to show the user, so default to plain HTTPS. Set the variable yourself to override.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:
        root.addHandler(logging.StreamHandler(sys.stderr))


def message_box(text: str, title: str = "FastWhisper") -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except Exception:
        print(f"{title}: {text}")


def main() -> int:
    setup_logging()
    log = logging.getLogger("fastwhisper")

    if not acquire():
        # A modal dialog from a tray app is worse than the duplicate launch it reports.
        log.info("another instance is already running, exiting")
        return 0

    cfg = Config.load()
    log.info("starting FastWhisper (model=%s, hotkey=%s)", cfg.model, cfg.hotkey)

    from .app import FastWhisperApp
    from .overlay import UiHost
    from .tray import Tray

    app = FastWhisperApp(cfg)
    # Tk insists on owning the main thread, so the tray runs beside it. On Windows pystray
    # pumps its own message loop, which is happy anywhere.
    ui = UiHost(cfg, lambda: app.recorder.level)
    tray = Tray(app, cfg, ui)

    def on_state(state: str, detail: str) -> None:
        tray.on_state(state, detail)
        ui.on_state(state, detail)

    app.on_state = on_state
    app.start()

    tray_thread = threading.Thread(target=tray.run, name="tray", daemon=True)
    tray_thread.start()
    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()
        try:
            tray.icon.stop()
        except Exception:
            log.debug("tray icon was already gone", exc_info=True)
    log.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
