"""Color themes and backgrounds for the Guess the Player series.

Each post gets its own theme (rotating by series number), so the feed never
shows the same look twice in a row. Themes never use a team's colors, so
the colors are never a hint.
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
    # Calm, dark, no patterns (Nov 2026): easy to read and smooth to watch.
    T("teal", "#0E3B44", "#1D1838", "plain", "#0F2D3A", "#5FD4D9", "#163B4B",
      "#FFCB2E", "#FFFFFF", "#A9D6DA", "#2EE59D", "#FF4F7B", "#14354A", "#121A2B"),
    T("midnight", "#121534", "#1B0F33", "plain", "#11112E", "#8A74FF", "#1A1745",
      "#FF5ACD", "#FFFFFF", "#A9A4D9", "#21F7C4", "#FF3B6B", "#17163B", "#160C2E"),
    T("forest", "#173126", "#0F1E18", "plain", "#1C3829", "#D9E8DC", "#244531",
      "#FFE07A", "#F4F7F2", "#A9C2AF", "#9CFF8A", "#FF8A8A", "#22402F", "#0E1C15"),
    T("navy", "#0F3266", "#0A1F45", "plain", "#0D3570", "#DDEBFF", "#11478F",
      "#FFD23F", "#FFFFFF", "#B5CDF2", "#7CFFB2", "#FF7A7A", "#0C3470", "#08214A"),
    T("gold room", "#16130C", "#0B0A07", "plain", "#15120B", "#C9A54A", "#201A0F",
      "#F2C94C", "#FFF6DC", "#BFAE85", "#F2C94C", "#E5533D", "#1E1A10", "#221B10"),
    T("slate", "#1E2430", "#11141B", "plain", "#161B24", "#9FB3C8", "#1F2733",
      "#4FC3F7", "#FFFFFF", "#A5B1C2", "#4ADE80", "#F87171", "#1B212C", "#0F131A"),
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

