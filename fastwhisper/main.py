"""Entry point: wires the config, the core app and the tray together."""
from __future__ import annotations

import ctypes
import logging
import logging.handlers
import sys

from .config import LOG_PATH, Config
from .single_instance import acquire


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
        message_box("FastWhisper is already running - look for the microphone icon in the tray.")
        return 0

    cfg = Config.load()
    log.info("starting FastWhisper (model=%s, hotkey=%s)", cfg.model, cfg.hotkey)

    from .app import FastWhisperApp
    from .tray import Tray

    app = FastWhisperApp(cfg)
    tray = Tray(app, cfg)
    app.on_state = tray.on_state
    app.start()
    try:
        tray.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()
    log.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
