"""Append-only log of recognized text."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .config import HISTORY_PATH

log = logging.getLogger(__name__)

MAX_ENTRIES_IN_MEMORY = 20


def append(text: str, seconds: float, elapsed: float, model: str) -> None:
    entry = {
        "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "audio_seconds": round(seconds, 2),
        "transcribe_seconds": round(elapsed, 2),
        "model": model,
        "text": text,
    }
    try:
        with HISTORY_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        log.exception("could not write history")


def recent(limit: int = MAX_ENTRIES_IN_MEMORY) -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries
