"""The animated artwork inside the floating panel.

A lattice of small diamonds - grains - that ripple and shimmer between near-black and
gold. One behaviour while recording, where the ripple is driven by your voice, and a
different one while transcribing, where a wave travels through the lattice on its own.

Frames are rendered with PIL rather than drawn as canvas items: the shapes are supersampled
and downscaled, which is what gives them smooth edges, and one image per frame is cheaper
for Tk than moving a few hundred polygons.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter

WIDTH, HEIGHT = 420, 88
SUPERSAMPLE = 3

# The shimmer runs along this ramp, from cold ash to lit gold.
DARK = (34, 32, 28)
EMBER = (104, 78, 34)
GOLD = (226, 178, 84)
BRIGHT = (255, 233, 176)

COLUMNS = 30
ROWS = 3


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _shade(t: float) -> tuple[int, int, int, int]:
    """Colour and opacity for a grain, from resting to fully lit.

    Without a panel behind them the quiet grains must not simply go dark - on a light
    desktop that reads as dirt. They fade out instead, so the field dissolves rather
    than turning grey.
    """
    t = max(0.0, min(1.0, t))
    if t < 0.45:
        colour = _mix(DARK, EMBER, t / 0.45)
    elif t < 0.8:
        colour = _mix(EMBER, GOLD, (t - 0.45) / 0.35)
    else:
        colour = _mix(GOLD, BRIGHT, (t - 0.8) / 0.2)
    alpha = int(70 + 185 * (t ** 0.7))
    return (*colour, min(255, alpha))


def _diamond(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, angle: float,
             colour: tuple[int, int, int, int]) -> None:
    points = []
    for corner in range(4):
        theta = angle + corner * math.pi / 2
        points.append((x + math.cos(theta) * size, y + math.sin(theta) * size))
    draw.polygon(points, fill=colour)


class GrainField:
    """Renders one frame of the lattice for a given state.

    The result is RGBA with a fully transparent background: the grains float over the
    desktop with nothing behind them, so the window has to carry real per-pixel alpha.
    """

    def render(self, state: str, phase: float, levels: list[float]) -> Image.Image:
        scale = SUPERSAMPLE
        canvas = Image.new("RGBA", (WIDTH * scale, HEIGHT * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        margin_x, margin_y = 26, 20
        span_x = WIDTH - margin_x * 2
        step_x = span_x / (COLUMNS - 1)
        centre_y = HEIGHT / 2

        for row in range(ROWS):
            # Rows sit above and below the centre line and lag behind each other.
            row_offset = (row - (ROWS - 1) / 2) * 13
            row_phase = row * 0.9
            row_fade = 1.0 - abs(row - (ROWS - 1) / 2) / ROWS

            for column in range(COLUMNS):
                x = margin_x + column * step_x
                position = column / (COLUMNS - 1)

                if state == "recording":
                    # The lattice breathes with your voice: loud speech lifts the grains
                    # off the centre line and pushes them up the colour ramp.
                    level = levels[column] if column < len(levels) else 0.0
                    wave = math.sin(phase * 2.2 + column * 0.42 + row_phase)
                    lift = wave * (2.5 + level * 15.0)
                    heat = 0.18 + level * 0.9 + 0.08 * wave
                    size = 1.7 + level * 2.6
                    angle = phase * 0.5 + column * 0.2
                else:
                    # A crest travels along the lattice, so the panel keeps moving while
                    # the model works even though there is nothing to react to.
                    travel = (position * 3.4 - phase * 1.5) % (math.pi * 2)
                    # Two crests half a cycle apart, so the lattice is never fully dark
                    # while one of them is off the end of the panel.
                    trailing = (travel + math.pi) % (math.pi * 2)
                    crest = max(
                        math.exp(-((travel - math.pi) ** 2) * 1.6),
                        math.exp(-((trailing - math.pi) ** 2) * 1.6) * 0.55,
                    )
                    lift = math.sin(phase * 1.4 + column * 0.5 + row_phase) * 4.5
                    heat = 0.17 + crest * 0.9
                    size = 1.8 + crest * 2.1
                    angle = phase * 0.9 + column * 0.15

                y = centre_y + row_offset + lift
                if not (margin_y * 0.3 < y < HEIGHT - margin_y * 0.3):
                    continue

                _diamond(
                    draw, x * scale, y * scale, max(1.0, size) * scale, angle,
                    _shade(heat * row_fade + 0.05),
                )

        frame = canvas.resize((WIDTH, HEIGHT), Image.LANCZOS)
        return _with_halo(frame)


def _with_halo(frame: Image.Image) -> Image.Image:
    """Puts a soft dark glow under the grains so they read on a light desktop too."""
    halo = frame.split()[3].filter(ImageFilter.GaussianBlur(4))
    halo = halo.point(lambda value: int(value * 0.32))
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    shadow.putalpha(halo)
    return Image.alpha_composite(shadow, frame)
