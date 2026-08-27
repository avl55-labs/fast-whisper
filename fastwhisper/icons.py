"""Tray icons drawn at runtime, so the app ships without image assets."""
from __future__ import annotations

from PIL import Image, ImageDraw

SIZE = 64

COLORS = {
    "idle": (110, 118, 129),      # grey: waiting for the hotkey
    "loading": (88, 133, 214),    # blue: model is loading
    "recording": (219, 68, 68),   # red: microphone is open
    "working": (222, 158, 54),    # amber: transcribing
    "error": (150, 40, 40),       # dark red: something failed
}


def make_icon(state: str = "idle") -> Image.Image:
    color = COLORS.get(state, COLORS["idle"])
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Microphone capsule.
    draw.rounded_rectangle((23, 10, 41, 40), radius=9, fill=color)
    # Stand arc and post.
    draw.arc((15, 24, 49, 50), start=0, end=180, fill=color, width=5)
    draw.rectangle((30, 46, 34, 54), fill=color)
    draw.rectangle((22, 52, 42, 56), fill=color)
    return image
