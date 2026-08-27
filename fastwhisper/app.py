"""Application core: hotkey -> recording -> transcription -> text output."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from . import history, sounds
from .audio import SILENCE_PEAK, Recorder, RecordingError, duration, normalize, peak
from .config import Config
from .hotkey import HotkeyError, HotkeyListener
from .output import deliver
from .transcriber import Transcriber

log = logging.getLogger(__name__)

StateCallback = Callable[[str, str], None]  # (state, human readable detail)


class FastWhisperApp:
    def __init__(self, cfg: Config, on_state: StateCallback | None = None) -> None:
        self.cfg = cfg
        self.recorder = Recorder(cfg.input_device, cfg.max_seconds)
        self.transcriber = Transcriber(cfg)
        self.listener: HotkeyListener | None = None
        self.on_state = on_state or (lambda state, detail: None)
        self.last_text = ""
        self._busy = threading.Lock()
        self._state = "idle"

    # ---------- lifecycle ----------

    def start(self) -> None:
        self._set_state("loading", "Loading the model...")
        threading.Thread(target=self._preload, daemon=True).start()
        self._register_hotkey()

    def _preload(self) -> None:
        try:
            self.transcriber.load()
        except Exception as exc:
            log.exception("model failed to load")
            self._set_state("error", f"Model error: {exc}")
            return
        self._set_state("idle", self.ready_hint())

    def _register_hotkey(self) -> None:
        if self.listener is not None:
            self.listener.stop()
        self.listener = HotkeyListener(
            self.cfg.hotkey,
            self.cfg.mode,
            on_start=self.start_recording,
            on_stop=self.stop_recording,
            on_cancel=self.cancel_recording,
        )
        try:
            self.listener.start()
        except HotkeyError as exc:
            log.error("%s", exc)
            self._set_state("error", str(exc))

    def shutdown(self) -> None:
        if self.listener is not None:
            self.listener.stop()
        if self.recorder.is_recording:
            self.recorder.stop()

    def reload_hotkey(self) -> None:
        self._register_hotkey()
        if self._state in ("idle", "error"):
            self._set_state("idle", self.ready_hint())

    def ready_hint(self) -> str:
        action = "Hold" if self.cfg.mode == "hold" else "Press"
        return f"{action} {self.cfg.hotkey.upper()} and speak"

    # ---------- recording ----------

    def start_recording(self) -> None:
        if self.recorder.is_recording:
            return
        if not self._busy.acquire(blocking=False):
            # A previous recording is still being transcribed.
            log.debug("busy, ignoring the hotkey")
            return
        try:
            self.recorder.start()
        except RecordingError as exc:
            self._busy.release()
            log.error("%s", exc)
            sounds.error()
            self._set_state("error", str(exc))
            return
        if self.cfg.beep:
            sounds.start()
        self._set_state("recording", "Recording...")

    def cancel_recording(self) -> None:
        if not self.recorder.is_recording:
            return
        self.recorder.stop()
        self._release()
        if self.cfg.beep:
            sounds.error()
        self._set_state("idle", "Cancelled. " + self.ready_hint())

    def stop_recording(self) -> None:
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        if self.cfg.beep:
            sounds.stop()
        seconds = duration(audio)
        if seconds < self.cfg.min_seconds:
            self._release()
            self._set_state("idle", self.ready_hint())
            return

        level = peak(audio)
        if level <= SILENCE_PEAK:
            # Silence this complete means the device is muted or blocked, not a quiet room.
            log.warning("captured %.1fs at peak %.5f - the microphone gave nothing", seconds, level)
            self._release()
            sounds.error()
            self._set_state("error", "Microphone is silent - check the input device")
            return
        if self.cfg.auto_gain:
            audio = normalize(audio)
        self._set_state("working", f"Transcribing {seconds:.1f}s...")
        threading.Thread(target=self._transcribe, args=(audio, seconds), daemon=True).start()

    def _transcribe(self, audio, seconds: float) -> None:  # noqa: ANN001
        started = time.perf_counter()
        try:
            text = self.transcriber.transcribe(audio)
        except Exception as exc:
            log.exception("transcription failed")
            sounds.error()
            self._set_state("error", f"Transcription failed: {exc}")
            self._release()
            return
        elapsed = time.perf_counter() - started
        log.info("%.1fs audio -> %d chars in %.1fs", seconds, len(text), elapsed)

        if text:
            self.last_text = text
            try:
                deliver(text, self.cfg.output)
            except Exception as exc:
                log.exception("could not deliver the text")
                self._set_state("error", f"Output failed: {exc}")
                self._release()
                return
            if self.cfg.save_history:
                history.append(text, seconds, elapsed, self.cfg.model)
            detail = text if len(text) <= 60 else text[:57] + "..."
            self._set_state("idle", detail)
        else:
            self._set_state("idle", "Nothing recognized. " + self.ready_hint())
        self._release()

    def _release(self) -> None:
        if self._busy.locked():
            try:
                self._busy.release()
            except RuntimeError:
                pass

    # ---------- state ----------

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str, detail: str) -> None:
        self._state = state
        try:
            self.on_state(state, detail)
        except Exception:
            log.exception("state callback failed")
