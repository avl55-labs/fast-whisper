"""Microphone capture into an in-memory buffer."""
from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000  # what Whisper expects
CHANNELS = 1


class RecordingError(RuntimeError):
    pass


class Recorder:
    """Records mono 16 kHz audio while `start()`/`stop()` bracket the session."""

    def __init__(self, device: int | None = None, max_seconds: float = 300.0) -> None:
        self.device = device
        self.max_seconds = max_seconds
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._samples = 0
        self._limit = int(max_seconds * SAMPLE_RATE)
        self._overflowed = False

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            log.debug("audio status: %s", status)
        with self._lock:
            if self._samples >= self._limit:
                self._overflowed = True
                return
            self._chunks.append(indata[:, 0].copy())
            self._samples += frames

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
            self._samples = 0
            self._overflowed = False
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                device=self.device,
                callback=self._callback,
                blocksize=0,
            )
            self._stream.start()
        except Exception as exc:  # sounddevice raises several unrelated types
            self._stream = None
            raise RecordingError(f"Cannot open the microphone: {exc}") from exc

    def stop(self) -> np.ndarray:
        """Stops the stream and returns everything captured, as float32 in [-1, 1]."""
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:  # closing must never break the caller
                log.exception("failed to close the audio stream")
        with self._lock:
            chunks, self._chunks = self._chunks, []
            self._samples = 0
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32, copy=False)

    @property
    def overflowed(self) -> bool:
        return self._overflowed


def list_input_devices() -> list[tuple[int, str]]:
    devices = []
    try:
        for index, info in enumerate(sd.query_devices()):
            if info.get("max_input_channels", 0) > 0:
                devices.append((index, info.get("name", f"device {index}")))
    except Exception:
        log.exception("failed to enumerate input devices")
    return devices


def duration(audio: np.ndarray) -> float:
    return len(audio) / SAMPLE_RATE
