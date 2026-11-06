"""Dusk mountain hero, drawn locally with Tk Canvas. No external image or AI asset."""
from __future__ import annotations
import tkinter as tk


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _rgb(c):
    return "#%02x%02x%02x" % c


class TwilightBanner(tk.Canvas):
    """Responsive illustrated sunset matching the premium-workspace reference."""

    def __init__(self, parent, *, height=296):
        super().__init__(
            parent, height=height, bg="#222840",
            highlightthickness=0, bd=0, relief="flat",
        )
        self.bind("<Configure>", self._draw)

    def _draw(self, _event=None):
        width = max(self.winfo_width(), 360)
        height = max(self.winfo_height(), 220)
        self.delete("all")
        # Twilight sky: deep-blue left, muted pink toward the right horizon.
        top_a = (23, 31, 57)
        top_b = (80, 62, 101)
        low_a = (31, 38, 68)
        low_b = (217, 126, 150)
        rows = 90
        cols = 24
        for y in range(rows):
            yf = y / (rows - 1)
            y0 = round(height * y / rows)
            y1 = round(height * (y + 1) / rows) + 1
            for x in range(cols):
                xf = x / (cols - 1)
                x0 = round(width * x / cols)
                x1 = round(width * (x + 1) / cols) + 1
                top = _mix(top_a, top_b, xf ** 1.25)
                bottom = _mix(low_a, low_b, xf ** 1.15)
                color = _mix(top, bottom, min(1, yf * 1.28))
                self.create_rectangle(x0, y0, x1, y1, fill=_rgb(color),
                                      outline="", tags="sky")
        # Layered mountains are vector paths; no downloaded art or network.
        def mountain(points, color):
            xy = []
            for xf, yf in points:
                xy.extend((round(xf * width), round(yf * height)))
            xy.extend((width, height, 0, height))
            self.create_polygon(*xy, fill=color, outline="", smooth=True)
        mountain([
            (0, .65), (.08, .70), (.18, .59), (.29, .68),
            (.44, .57), (.56, .61), (.72, .41), (.81, .52),
            (.94, .49), (1, .57),
        ], "#504667")
        mountain([
            (0, .72), (.12, .66), (.23, .75), (.39, .64),
            (.52, .71), (.70, .54), (.81, .66), (.92, .60), (1, .65),
        ], "#333755")
        mountain([
            (0, .83), (.12, .76), (.28, .83), (.42, .71),
            (.58, .79), (.73, .67), (.85, .72), (1, .68),
        ], "#202a47")
        mountain([
            (0, .92), (.17, .81), (.36, .89), (.54, .76),
            (.67, .83), (.85, .78), (1, .82),
        ], "#17223c")
        # Left-weighted title is as in the selected design.
        title_size = max(28, min(42, round(width / 22)))
        self.create_text(
            35, height * .27, text="VARYN",
            anchor="w", fill="#f9f9ff",
            font=("Segoe UI", title_size, "bold"),
        )
        self.create_text(
            36, height * .46,
            text="Workspace cerdas untuk berpikir,",
            anchor="w", fill="#f1eaf7",
            font=("Segoe UI", 12),
        )
        self.create_text(
            36, height * .54,
            text="merencanakan, dan menyelesaikan pekerjaan.",
            anchor="w", fill="#f1eaf7",
            font=("Segoe UI", 12),
        )
