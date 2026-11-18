"""Color themes and backgrounds for the Guess the Player series.

Since Nov 2026 every post uses the house black + gold look (one theme), on a
plain gradient. Themes never use a team's colors, so the colors are never a hint.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def T(name, bg1, bg2, pattern, floor, line, paint, accent, ink, muted, make, miss, panel, chip):
    return {"name": name, "bg": (rgb(bg1), rgb(bg2)), "pattern": pattern, "floor": rgb(floor),
            "line": rgb(line), "paint": rgb(paint), "accent": rgb(accent), "ink": rgb(ink),
            "muted": rgb(muted), "make": rgb(make), "miss": rgb(miss), "panel": rgb(panel),
            "chip": rgb(chip)}


THEMES = [
    # House look (Nov 2026): black + gold, plain smooth background, no patterns.
    T("black gold", "#141311", "#0A0A0A", "plain", "#1A1815", "#B8A27A", "#24211C",
      "#D6AF40", "#F6F3EC", "#A0968A", "#D6AF40", "#E0533D", "#1F1C17", "#1C1A16"),
]


def theme(n):
    return THEMES[n % len(THEMES)]


def background(W, H, th, seed=0):
    """Smooth two-color gradient (no patterns)."""
    a, b = th["bg"]
    img = Image.new("RGBA", (W, H))
    grad = Image.linear_gradient("L").resize((W, H))
    img = Image.composite(Image.new("RGBA", (W, H), b + (255,)), Image.new("RGBA", (W, H), a + (255,)), grad)
    return img          # patterns retired Nov 2026: plain smooth gradient only

