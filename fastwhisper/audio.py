"""Microphone capture into an in-memory buffer.

Whisper wants 16 kHz mono, but Windows sound devices rarely offer it. The MME host API
in particular rejects any rate the device does not natively support, so recording is done
at whatever the device provides and resampled here.
"""
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


def _device_info(device: int | None) -> dict:
    return sd.query_devices(device if device is not None else None, kind="input")


def _candidates(device: int | None) -> list[tuple[int | None, int, int]]:
    """Device, sample rate and channel count combinations to try, best first."""
    options: list[tuple[int | None, int, int]] = []
    try:
        info = _device_info(device)
        rate = int(info["default_samplerate"])
        channels = max(1, int(info["max_input_channels"]))
        options.append((device, rate, 1))
        if channels > 1:
            options.append((device, rate, channels))
        if rate != SAMPLE_RATE:
            options.append((device, SAMPLE_RATE, 1))
    except Exception:
        log.debug("cannot query the input device", exc_info=True)

    if device is None:
        # Last resort: WASAPI usually opens when MME refuses the format.
        try:
            for index, api in enumerate(sd.query_hostapis()):
                if "WASAPI" not in api["name"]:
                    continue
                wasapi_device = api["default_input_device"]
                if wasapi_device is None or wasapi_device < 0:
                    continue
                info = sd.query_devices(wasapi_device)
                options.append((wasapi_device, int(info["default_samplerate"]), 1))
                break
        except Exception:
            log.debug("cannot enumerate host APIs", exc_info=True)

    if not options:
        options.append((device, SAMPLE_RATE, 1))
    return options


def resample(audio: np.ndarray, rate: int) -> np.ndarray:
    """Converts float32 mono audio to 16 kHz."""
    if rate == SAMPLE_RATE or len(audio) == 0:
        return audio
    try:
        import av

        frame = av.AudioFrame.from_ndarray(
            audio.reshape(1, -1).astype(np.float32, copy=False), format="flt", layout="mono"
        )
        frame.sample_rate = rate
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        frames = resampler.resample(frame) + resampler.resample(None)
        chunks = [f.to_ndarray().reshape(-1) for f in frames]
        if chunks:
            return np.concatenate(chunks).astype(np.float32, copy=False)
        log.warning("resampler returned nothing, falling back to interpolation")
    except Exception:
        log.exception("libswresample failed, falling back to interpolation")

    # Linear interpolation: worse than a filtered resample, but better than failing.
    count = int(round(len(audio) * SAMPLE_RATE / rate))
    if count <= 0:
        return np.zeros(0, dtype=np.float32)
    source = np.linspace(0, len(audio) - 1, count, dtype=np.float64)
    return np.interp(source, np.arange(len(audio)), audio).astype(np.float32)


class Recorder:
    """Records mono audio while `start()`/`stop()` bracket the session."""

    def __init__(self, device: int | None = None, max_seconds: float = 300.0) -> None:
        self.device = device
        self.max_seconds = max_seconds
        self.rate = SAMPLE_RATE
        self.channels = CHANNELS
        # Loudness of the latest block, 0..1, read by the on-screen overlay.
        self.level = 0.0
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._samples = 0
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
            block = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0]
            self._chunks.append(block.copy())
            self._samples += frames
        # Root mean square, outside the lock: the overlay only needs a recent value.
        if len(block):
            self.level = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
            self._samples = 0
            self._overflowed = False
        self.level = 0.0

        errors = []
        for device, rate, channels in _candidates(self.device):
            self.rate, self.channels = rate, channels
            self._limit = int(self.max_seconds * rate)
            try:
                stream = sd.InputStream(
                    samplerate=rate,
                    channels=channels,
                    dtype="float32",
                    device=device,
                    callback=self._callback,
                    blocksize=0,
                )
                stream.start()
            except Exception as exc:  # sounddevice raises several unrelated types
                errors.append(f"{device}@{rate}Hz/{channels}ch: {exc}")
                continue
            self._stream = stream
            log.info("recording from device %s at %d Hz, %d channel(s)", device, rate, channels)
            return

        raise RecordingError("Cannot open the microphone. Tried " + "; ".join(errors))

    def stop(self) -> np.ndarray:
        """Stops the stream and returns 16 kHz float32 audio in [-1, 1]."""
        stream, self._stream = self._stream, None
        self.level = 0.0
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
        audio = np.concatenate(chunks).astype(np.float32, copy=False)
        return resample(audio, self.rate)

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


SILENCE_PEAK = 0.002   # below this the input is muted or blocked, not merely quiet
TARGET_PEAK = 0.35     # what a normalized recording is lifted to
MAX_GAIN = 20.0


def peak(audio: np.ndarray) -> float:
    return float(np.abs(audio).max()) if len(audio) else 0.0


def normalize(audio: np.ndarray) -> np.ndarray:
    """Lifts a quiet recording towards a usable level.

    Whisper's voice activity detector works on absolute loudness, so a microphone running
    at a low system level gets its speech discarded as silence before recognition ever
    sees it. Scaling is capped so hiss in an empty room is not amplified into noise.
    """
    current = peak(audio)
    if current <= SILENCE_PEAK or current >= TARGET_PEAK:
        return audio
    gain = min(TARGET_PEAK / current, MAX_GAIN)
    return (audio * gain).astype(np.float32, copy=False)


def duration(audio: np.ndarray) -> float:
    return len(audio) / SAMPLE_RATE
