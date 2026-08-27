"""Speech-to-text through faster-whisper (CTranslate2)."""
from __future__ import annotations

import logging
import threading

import numpy as np

from .config import Config

log = logging.getLogger(__name__)


class Transcriber:
    """Lazily loads the Whisper model and keeps it warm between recordings."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._model = None
        self._lock = threading.Lock()
        self._loaded_key: tuple[str, str, str] | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _key(self) -> tuple[str, str, str]:
        return (self.cfg.model, self.cfg.device, self.cfg.compute_type)

    def load(self) -> None:
        """Downloads (first run only) and loads the model. Safe to call repeatedly."""
        with self._lock:
            if self._model is not None and self._loaded_key == self._key():
                return
            from faster_whisper import WhisperModel

            log.info(
                "loading model %s on %s (%s)",
                self.cfg.model,
                self.cfg.device,
                self.cfg.compute_type,
            )
            self._model = WhisperModel(
                self.cfg.model,
                device=self.cfg.device,
                compute_type=self.cfg.compute_type,
                cpu_threads=self.cfg.threads(),
            )
            self._loaded_key = self._key()
            log.info("model ready")

    def unload(self) -> None:
        with self._lock:
            self._model = None
            self._loaded_key = None

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        language = None if self.cfg.language == "auto" else self.cfg.language
        segments, _info = self._model.transcribe(
            audio,
            language=language,
            beam_size=self.cfg.beam_size,
            vad_filter=self.cfg.vad,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=self.cfg.initial_prompt(),
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
