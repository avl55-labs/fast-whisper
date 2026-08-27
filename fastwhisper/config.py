"""User settings, stored as JSON in %APPDATA%/FastWhisper/config.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "FastWhisper"


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_PATH = app_dir() / "config.json"
HISTORY_PATH = app_dir() / "history.jsonl"
LOG_PATH = app_dir() / "fastwhisper.log"


@dataclass
class Config:
    # Hotkey in the syntax of the `keyboard` package: "ctrl+alt+space", "f9", "right ctrl".
    hotkey: str = "ctrl+alt+space"
    # "hold": record while the hotkey is held. "toggle": press to start, press again to stop.
    mode: str = "hold"
    # faster-whisper model: tiny, base, small, medium, large-v3, large-v3-turbo.
    model: str = "large-v3-turbo"
    # "cpu" or "cuda". CUDA needs an NVIDIA card.
    device: str = "cpu"
    # int8 is the fastest on CPU; float16 only makes sense on CUDA.
    compute_type: str = "int8"
    # Recognition language: "ru", "en", ... or "auto" to detect per recording.
    language: str = "ru"
    # What to do with the text: "paste" into the focused window, "type" it, or "clipboard" only.
    output: str = "paste"
    # Short beeps when recording starts and stops.
    beep: bool = True
    # Tray balloon notifications with the recognized text.
    notifications: bool = False
    # Trim silence around speech before transcribing.
    vad: bool = True
    # Recordings shorter than this are discarded as accidental key presses.
    min_seconds: float = 0.4
    # Hard cap on one recording so a stuck key cannot eat all memory.
    max_seconds: float = 300.0
    # Microphone index; null means the system default device.
    input_device: int | None = None
    # CPU threads for the model; 0 means half of the logical cores.
    cpu_threads: int = 0
    # Append every result to history.jsonl.
    save_history: bool = True
    # Optional prompt that biases the model towards your terms and names.
    prompt: str = ""

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
            known = {f.name for f in fields(cls)}
            for key, value in raw.items():
                if key in known:
                    setattr(cfg, key, value)
        cfg.save()
        return cfg

    def save(self) -> None:
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def threads(self) -> int:
        if self.cpu_threads > 0:
            return self.cpu_threads
        return max(2, (os.cpu_count() or 4) // 2)
