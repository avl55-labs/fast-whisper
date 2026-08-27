"""What speech models are available, which are downloaded, and how big they are.

Numbers in `CATALOGUE` come from measurements on this project's reference machine - an
8-core Ryzen 9 8945HS running int8 on 16 threads. Latency is per phrase rather than per
second of speech: Whisper's encoder always processes a 30-second window, so a three-second
phrase costs nearly as much as a nine-second one.
"""
from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelInfo:
    name: str          # what goes into the config and into WhisperModel()
    title: str         # the model's own name, as its authors call it
    author: str        # who trained the weights
    packager: str      # who converted them to the CTranslate2 format we run
    repo: str          # Hugging Face repository backing it
    size_gb: float     # download size, approximate
    wait_seconds: float  # measured wall time per phrase on CPU
    speed: int         # 1..5, for the gauge
    accuracy: int      # 1..5, for the gauge
    languages: str
    # Shown in the first-run picker. Empty for the models it does not offer.
    tier: str = ""     # the one-word verdict
    purpose: str = ""  # what this model is the right choice for

    @property
    def latency(self) -> str:
        """Wait per phrase, in the reader's own notation."""
        from .i18n import _, current

        value = f"{self.wait_seconds:g}"
        if current() == "ru":
            value = value.replace(".", ",")
        return _("~{value} s").format(value=value)

    @property
    def credit(self) -> str:
        if self.packager and self.packager != self.author:
            return f"{self.author}, converted by {self.packager}"
        return self.author


# Colour and monogram per author. These are plain badges rather than the companies'
# marks: the models are used under their own licences, and nothing here is endorsed by
# or affiliated with the people who trained them.
BADGES = {
    "OpenAI": ("#0f9d7d", "AI"),
    "Hugging Face": ("#ffab00", "HF"),
    "Systran": ("#2f6fe0", "SY"),
    "Mobius Labs": ("#7b5cf0", "ML"),
    "Distil-Whisper": ("#e0533d", "DW"),
}


CATALOGUE: list[ModelInfo] = [
    ModelInfo("tiny", "Whisper Tiny", "OpenAI", "Systran",
              "Systran/faster-whisper-tiny", 0.08, 0.3, 5, 1, "99 languages",
              tier="Instant",
              purpose="As fast as it gets. Expect to fix words afterwards."),
    ModelInfo("base", "Whisper Base", "OpenAI", "Systran",
              "Systran/faster-whisper-base", 0.15, 0.6, 5, 2, "99 languages",
              tier="Quick",
              purpose="Short notes and search boxes, where a wrong word costs nothing."),
    ModelInfo("small", "Whisper Small", "OpenAI", "Systran",
              "Systran/faster-whisper-small", 0.50, 1.6, 4, 3, "99 languages",
              tier="Balanced",
              purpose="Answers in a second and a half. Fine for English, rougher on Russian."),
    ModelInfo("medium", "Whisper Medium", "OpenAI", "Systran",
              "Systran/faster-whisper-medium", 1.50, 4.3, 3, 4, "99 languages",
              tier="Accurate",
              purpose="Everyday dictation when you would rather not reread every line."),
    ModelInfo("large-v3-turbo", "Whisper Large v3 Turbo", "OpenAI", "Mobius Labs",
              "mobiuslabsgmbh/faster-whisper-large-v3-turbo", 1.60, 5.5, 2, 5,
              "99 languages",
              tier="Recommended",
              purpose="The most accurate one that is still comfortable to wait for. "
                      "Handles Russian names and endings the smaller ones mangle."),
    ModelInfo("large-v3", "Whisper Large v3", "OpenAI", "Systran",
              "Systran/faster-whisper-large-v3", 3.00, 15, 1, 5, "99 languages"),
    ModelInfo("large-v2", "Whisper Large v2", "OpenAI", "Systran",
              "Systran/faster-whisper-large-v2", 3.00, 15, 1, 5, "99 languages"),
    ModelInfo("distil-large-v3.5", "Distil-Whisper Large v3.5", "Hugging Face", "Distil-Whisper",
              "distil-whisper/distil-large-v3.5-ct2", 1.50, 3.5, 3, 4, "English"),
    ModelInfo("distil-large-v3", "Distil-Whisper Large v3", "Hugging Face", "Systran",
              "Systran/faster-distil-whisper-large-v3", 1.50, 4, 3, 4, "English"),
    ModelInfo("small.en", "Whisper Small English", "OpenAI", "Systran",
              "Systran/faster-whisper-small.en", 0.50, 1.6, 4, 3, "English"),
]

BY_NAME = {model.name: model for model in CATALOGUE}

# What the first-run picker offers, best first. The rest of the catalogue stays one click
# away in the settings window.
FEATURED = [BY_NAME[name] for name in
            ("large-v3-turbo", "medium", "small", "base", "tiny")]


def cache_root() -> Path:
    """Where huggingface_hub keeps downloaded repositories."""
    for variable in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"):
        value = os.environ.get(variable)
        if value:
            return Path(value)
    home = os.environ.get("HF_HOME")
    if home:
        return Path(home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def cache_dir(model: ModelInfo) -> Path:
    return cache_root() / ("models--" + model.repo.replace("/", "--"))


def _tree_size(path: Path) -> int:
    """Bytes under `path`, counting each physical file once.

    The cache stores a file's data once and exposes it under both `blobs` and `snapshots`,
    historically as a symlink or a copy and, with the newer Xet backend, only under
    `snapshots`. Deduplicating on the inode covers every one of those layouts.
    """
    total = 0
    seen: set[tuple[int, int]] = set()
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                stat = (Path(root) / name).stat()
            except OSError:
                continue
            if stat.st_ino:
                key = (stat.st_dev, stat.st_ino)
                if key in seen:
                    continue
                seen.add(key)
            total += stat.st_size
    return total


def disk_size(model: ModelInfo) -> int:
    """Bytes this model occupies on disk."""
    directory = cache_dir(model)
    return _tree_size(directory) if directory.exists() else 0


def is_downloaded(model: ModelInfo) -> bool:
    """True when the repository has a snapshot with the model weights in it."""
    snapshots = cache_dir(model) / "snapshots"
    if not snapshots.is_dir():
        return False
    for snapshot in snapshots.iterdir():
        if (snapshot / "model.bin").exists():
            return True
    return False


def delete(model: ModelInfo) -> None:
    directory = cache_dir(model)
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)
        log.info("removed %s", directory)


def human_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "-"
    if num_bytes >= 1 << 30:
        return f"{num_bytes / (1 << 30):.1f} GB"
    return f"{num_bytes / (1 << 20):.0f} MB"


def badge(model: ModelInfo, size: int = 26):  # noqa: ANN201 - returns a PIL image
    """Small monogram tile standing in for the author, drawn rather than shipped."""
    from PIL import Image, ImageDraw, ImageFont

    colour, letters = BADGES.get(model.author, ("#6d7079", model.author[:2].upper()))
    image = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), radius=size, fill=colour)
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(size * 1.9))
    except OSError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), letters, font=font)
    draw.text(
        ((size * 4 - box[2] + box[0]) / 2, (size * 4 - box[3] + box[1]) / 2 - box[1]),
        letters, font=font, fill="white",
    )
    return image.resize((size, size), Image.LANCZOS)


def download(model: ModelInfo, on_done=None) -> None:  # noqa: ANN001
    """Fetches the repository without loading it into memory."""
    from huggingface_hub import snapshot_download

    try:
        snapshot_download(model.repo, allow_patterns=["*.bin", "*.json", "*.txt", "*.model"])
        error = None
    except Exception as exc:  # network, disk, permissions
        log.exception("download of %s failed", model.name)
        error = exc
    if on_done is not None:
        on_done(error)
