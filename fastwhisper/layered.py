"""Per-pixel transparent window.

Tk can only key out one flat colour, which leaves a coloured fringe around anything
antialiased. A layered window takes an image with a real alpha channel instead, so the
grains can fade into whatever is behind them with no panel underneath.

The bitmap is pushed straight to the compositor with UpdateLayeredWindow; Tk still owns
the window handle, its position and the event loop, but paints nothing.
"""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020

BI_RGB = 0
DIB_RGB_COLORS = 0
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
ULW_ALPHA = 0x02


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


def window_handle(widget) -> int:  # noqa: ANN001 - a Tk widget
    """HWND of the top-level window behind a Tk widget."""
    handle = widget.winfo_id()
    return user32.GetParent(handle) or handle


def make_click_through(hwnd: int) -> None:
    """Layered, never focused, and transparent to the mouse."""
    current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        current | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT,
    )


class LayeredSurface:
    """Reusable device context and bitmap for one window size."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._screen_dc = user32.GetDC(0)
        self._mem_dc = gdi32.CreateCompatibleDC(self._screen_dc)

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # negative: rows run top to bottom
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB

        self._bits = ctypes.c_void_p()
        self._bitmap = gdi32.CreateDIBSection(
            self._mem_dc, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(self._bits), None, 0
        )
        self._previous = gdi32.SelectObject(self._mem_dc, self._bitmap)
        self._blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

    def update(self, hwnd: int, image: Image.Image, x: int, y: int, opacity: float = 1.0) -> None:
        """Draws an RGBA image as the whole window."""
        pixels = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        alpha = pixels[:, :, 3].astype(np.uint16)
        if opacity < 1.0:
            alpha = (alpha * max(0.0, min(1.0, opacity))).astype(np.uint16)

        # UpdateLayeredWindow expects premultiplied BGRA.
        buffer = np.empty_like(pixels)
        buffer[:, :, 0] = (pixels[:, :, 2].astype(np.uint16) * alpha // 255).astype(np.uint8)
        buffer[:, :, 1] = (pixels[:, :, 1].astype(np.uint16) * alpha // 255).astype(np.uint8)
        buffer[:, :, 2] = (pixels[:, :, 0].astype(np.uint16) * alpha // 255).astype(np.uint8)
        buffer[:, :, 3] = alpha.astype(np.uint8)

        raw = buffer.tobytes()
        ctypes.memmove(self._bits, raw, len(raw))

        size = wintypes.SIZE(self.width, self.height)
        source = wintypes.POINT(0, 0)
        destination = wintypes.POINT(x, y)
        ok = user32.UpdateLayeredWindow(
            wintypes.HWND(hwnd),
            self._screen_dc,
            ctypes.byref(destination),
            ctypes.byref(size),
            self._mem_dc,
            ctypes.byref(source),
            0,
            ctypes.byref(self._blend),
            ULW_ALPHA,
        )
        if not ok:
            log.debug("UpdateLayeredWindow failed: %s", ctypes.get_last_error())

    def close(self) -> None:
        try:
            gdi32.SelectObject(self._mem_dc, self._previous)
            gdi32.DeleteObject(self._bitmap)
            gdi32.DeleteDC(self._mem_dc)
            user32.ReleaseDC(0, self._screen_dc)
        except Exception:
            log.debug("releasing the layered surface failed", exc_info=True)
