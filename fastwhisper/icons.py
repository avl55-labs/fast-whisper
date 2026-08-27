"""Tray icons drawn at runtime, so the app ships without image assets."""
from __future__ import annotations

from PIL import Image, ImageDraw

SIZE = 64

COLORS = {
    # The same two hues the floating panel uses: gold while the microphone is open, its
    # opposite while the model works, so the tray and the panel say the same thing.
    "idle": (110, 118, 129),      # grey: waiting for the hotkey
    "loading": (84, 160, 226),    # blue: model is loading
    "recording": (226, 178, 84),  # gold: microphone is open
    "working": (84, 160, 226),    # blue: transcribing
    "error": (196, 72, 62),       # red: something failed
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
