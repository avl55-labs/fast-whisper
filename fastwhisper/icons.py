"""Tray and window icons, drawn at runtime so the app ships without image assets.

The shape is the one from the logo - a grain with two quiet ones beside it - and it
changes with what the app is doing, not only in colour: recording swells the middle
grain, transcribing evens the three out into a row. Colour alone is a weak signal at
sixteen pixels, and it is no signal at all to a colour-blind reader.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

SIZE = 64
SS = 4  # supersampled, then downscaled: PIL does not antialias polygons

# The same two hues as the floating panel, plus the resting and failure states.
COLORS = {
    "idle": (150, 155, 165),
    "loading": (84, 160, 226),
    "recording": (232, 184, 88),
    "working": (84, 160, 226),
    "error": (208, 88, 78),
}

INK = (14, 15, 18)


def _diamond(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, colour) -> None:  # noqa: ANN001
    points = [
        (x + math.cos(i * math.pi / 2) * size, y + math.sin(i * math.pi / 2) * size)
        for i in range(4)
    ]
    draw.polygon(points, fill=colour)


def _dim(colour: tuple[int, int, int], factor: float) -> tuple[int, int, int, int]:
    return (*colour, int(255 * factor))


def _draw_mark(draw: ImageDraw.ImageDraw, box: float, colour, state: str) -> None:  # noqa: ANN001
    """Draws the three grains inside a square of side `box`."""
    centre = box / 2
    if state in ("working", "loading"):
        # Three even grains in a row: the model is chewing, nothing is being heard.
        for offset in (-0.31, 0.0, 0.31):
            _diamond(draw, centre + box * offset, centre, box * 0.145,
                     _dim(colour, 1.0 if offset == 0 else 0.72))
    else:
        # One grain lifted out of the field, the way the logo has it.
        _diamond(draw, centre, centre, box * 0.27, _dim(colour, 1.0))
        for offset in (-0.35, 0.35):
            _diamond(draw, centre + box * offset, centre, box * 0.105, _dim(colour, 0.6))


def make_icon(state: str = "idle") -> Image.Image:
    """Tray icon: grains on a transparent background, so it suits any taskbar colour."""
    colour = COLORS.get(state, COLORS["idle"])
    canvas = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    _draw_mark(ImageDraw.Draw(canvas), SIZE * SS, colour, state)
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def window_icon(size: int = 64) -> Image.Image:
    """Title-bar icon: the full mark, dark tile and all."""
    canvas = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (0, 0, size * SS - 1, size * SS - 1), radius=size * SS * 0.22, fill=INK
    )
    _draw_mark(draw, size * SS, COLORS["recording"], "recording")
    return canvas.resize((size, size), Image.LANCZOS)
