"""Draws the project artwork: a README banner and a square mark.

The motif is the same lattice of grains the app shows while you dictate, so the picture
on the page and the thing on screen are recognisably one product.

Run:  .venv\\Scripts\\python.exe packaging\\make_logo.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

INK = (13, 14, 17)
INK_SOFT = (22, 24, 29)
TEXT = (245, 243, 238)
MUTED = (150, 150, 158)

DARK = (46, 42, 34)
EMBER = (120, 88, 36)
GOLD = (226, 178, 84)
BRIGHT = (255, 233, 176)

SS = 3  # supersampling factor


def mix(a, b, t):  # noqa: ANN001, ANN201
    t = max(0.0, min(1.0, t))
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def shade(t: float):  # noqa: ANN201
    t = max(0.0, min(1.0, t))
    if t < 0.45:
        return mix(DARK, EMBER, t / 0.45)
    if t < 0.8:
        return mix(EMBER, GOLD, (t - 0.45) / 0.35)
    return mix(GOLD, BRIGHT, (t - 0.8) / 0.2)


def diamond(draw, x, y, size, angle, colour):  # noqa: ANN001
    points = [
        (x + math.cos(angle + i * math.pi / 2) * size,
         y + math.sin(angle + i * math.pi / 2) * size)
        for i in range(4)
    ]
    draw.polygon(points, fill=colour)


def font(size: int, bold: bool = True):  # noqa: ANN201
    for name in (("segoeuib.ttf", "segoeui.ttf") if bold else ("segoeui.ttf",)):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def lattice(draw, box, columns, rows, amplitude, spacing, phase=0.0, scale=1.0):  # noqa: ANN001
    """Draws the grain wave inside `box` = (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    centre_y = (y0 + y1) / 2
    step = (x1 - x0) / (columns - 1)
    for row in range(rows):
        offset = (row - (rows - 1) / 2) * spacing
        fade = 1.0 - abs(row - (rows - 1) / 2) / (rows + 0.5)
        for column in range(columns):
            position = column / (columns - 1)
            wave = math.sin(position * 6.4 + phase + row * 0.8)
            # Loudest in the middle, tapering to the ends, like a spoken phrase.
            envelope = math.sin(math.pi * position) ** 0.7
            heat = (0.22 + 0.9 * envelope * (0.6 + 0.4 * wave)) * fade
            size = (1.6 + 2.6 * envelope * (0.5 + 0.5 * wave)) * scale
            x = x0 + column * step
            y = centre_y + offset + wave * amplitude * envelope
            diamond(draw, x, y, max(1.0, size), phase * 0.6 + column * 0.2, shade(heat))


def glow(image: Image.Image, radius: int, strength: float) -> Image.Image:
    """Adds a warm bloom under the artwork."""
    blurred = image.filter(ImageFilter.GaussianBlur(radius))
    return Image.blend(image, blurred, strength)


def banner() -> Image.Image:
    width, height = 1280, 400
    canvas = Image.new("RGB", (width * SS, height * SS), INK)
    draw = ImageDraw.Draw(canvas)

    # A soft vertical lift so the panel is not flat black.
    for y in range(height * SS):
        t = y / (height * SS)
        draw.line(
            [(0, y), (width * SS, y)],
            fill=mix(INK_SOFT, INK, abs(t - 0.35) * 1.6),
        )

    lattice(
        draw,
        (170 * SS, 105 * SS, (width - 170) * SS, 205 * SS),
        columns=34, rows=3, amplitude=30 * SS, spacing=22 * SS, scale=SS * 1.9,
    )

    canvas = glow(canvas, radius=6 * SS, strength=0.35)
    draw = ImageDraw.Draw(canvas)

    title = "FastWhisper"
    title_font = font(74 * SS)
    box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(
        ((width * SS - box[2] + box[0]) / 2 - box[0], 218 * SS),
        title, font=title_font, fill=TEXT,
    )

    subtitle = "Press a key, speak, get text.  Offline, free, no account."
    subtitle_font = font(25 * SS, bold=False)
    box = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    draw.text(
        ((width * SS - box[2] + box[0]) / 2 - box[0], 312 * SS),
        subtitle, font=subtitle_font, fill=MUTED,
    )

    return canvas.resize((width, height), Image.LANCZOS)


def mark(size: int = 512) -> Image.Image:
    """The application icon.

    The banner can afford the whole lattice; an icon cannot. Tried at 16 pixels, three
    rows of small grains turn to mush, and so do columns of them - the shapes merge into
    a smudge rather than into bars. What survives is a single grain lifted out of the
    field with two quiet ones beside it: the same motif, one element instead of ninety.
    """
    canvas = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (0, 0, size * SS - 1, size * SS - 1), radius=size * SS * 0.22, fill=INK
    )

    centre = size * SS * 0.5
    diamond(draw, centre, centre, size * SS * 0.20, 0.0, shade(1.0))
    for offset in (-0.27, 0.27):
        diamond(draw, centre + size * SS * offset, centre, size * SS * 0.075, 0.0, shade(0.45))

    canvas = glow(canvas, radius=int(size * SS * 0.02), strength=0.4)
    return canvas.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    banner().save(ASSETS / "banner.png")
    icon = mark()
    icon.save(ASSETS / "icon.png")
    icon.resize((128, 128), Image.LANCZOS).save(ASSETS / "icon-128.png")
    icon.save(
        ROOT / "packaging" / "app.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("wrote", ASSETS / "banner.png", ASSETS / "icon.png", ROOT / "packaging" / "app.ico")


if __name__ == "__main__":
    main()
