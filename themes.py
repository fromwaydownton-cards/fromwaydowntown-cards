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
    T("90s teal", "#0B6E79", "#3B1F6B", "confetti", "#0F2D3A", "#5FD4D9", "#163B4B",
      "#FFCB2E", "#FFFFFF", "#BFE9EC", "#2EE59D", "#FF4F7B", "#14354A", "#1E1033"),
    T("hardwood", "#F3E6CF", "#E2C9A0", "planks", "#C98F55", "#FFF6E5", "#B97C43",
      "#B3261E", "#2A1A0E", "#6E5236", "#1E7B3A", "#C0281C", "#FFF6E5", "#2A1A0E"),
    T("neon night", "#0A0A23", "#1B0B3A", "grid", "#11112E", "#7A5CFF", "#1A1745",
      "#FF2BD6", "#FFFFFF", "#A9A4D9", "#21F7C4", "#FF3B6B", "#17163B", "#2A0E4A"),
    T("chalkboard", "#1F3A2E", "#13261E", "chalk", "#22422F", "#E8F1E8", "#2B5139",
      "#FFE07A", "#F4F7F2", "#A9C2AF", "#9CFF8A", "#FF8A8A", "#2B4A38", "#0E1C15"),
    T("sunset", "#FF7A3D", "#B4236E", "rays", "#2B1133", "#FFC59E", "#3B1744",
      "#FFE45C", "#FFFFFF", "#FFD9C2", "#5CFFB0", "#FF5A5A", "#3A1240", "#2B0A26"),
    T("arcade", "#050505", "#101010", "pixels", "#0B0F0B", "#39FF14", "#122012",
      "#39FF14", "#E9FFE3", "#8FBF85", "#39FF14", "#FF2E63", "#102010", "#0B160B"),
    T("blueprint", "#0F4C9C", "#0A3570", "blueprint", "#0D4189", "#DDEBFF", "#11509F",
      "#FFD23F", "#FFFFFF", "#B5CDF2", "#7CFFB2", "#FF7A7A", "#0C3B7C", "#08285A"),
    T("vintage", "#F6EEDC", "#EAD9B5", "halftone", "#1D2F5C", "#F6EEDC", "#273C70",
      "#C8102E", "#1D2F5C", "#6F6A5C", "#2AAE5C", "#E0412B", "#FFF8E8", "#1D2F5C"),
    T("miami", "#FF71CE", "#01CDFE", "waves", "#1A0F2E", "#FFB3E6", "#26173F",
      "#FFFB96", "#FFFFFF", "#FFE0F4", "#05FFA1", "#FF3864", "#2A1745", "#2A1745"),
    T("gold room", "#0D0B07", "#1E180C", "diamonds", "#15120B", "#C9A54A", "#201A0F",
      "#F2C94C", "#FFF6DC", "#BFAE85", "#F2C94C", "#E5533D", "#1E1A10", "#2A2214"),
    T("ice", "#E9F6FF", "#BFE3FA", "frost", "#0E2A47", "#CDEBFF", "#143557",
      "#0077C8", "#0B2340", "#4D6E8C", "#33E3A0", "#FF5C7A", "#FFFFFF", "#0B2340"),
    T("lava", "#2A0705", "#5A1206", "embers", "#1E0B08", "#FF8A4C", "#2C110C",
      "#FFB000", "#FFF1E6", "#E6B8A2", "#FFD166", "#FF3D2E", "#2E120C", "#3D140A"),
]


def theme(n):
    return THEMES[n % len(THEMES)]


def background(W, H, th, seed=0):
    """Gradient plus the theme's pattern."""
    a, b = th["bg"]
    img = Image.new("RGBA", (W, H))
    grad = Image.linear_gradient("L").resize((W, H))
    img = Image.composite(Image.new("RGBA", (W, H), b + (255,)), Image.new("RGBA", (W, H), a + (255,)), grad)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(seed)
    p = th["pattern"]
    acc, line = th["accent"], th["line"]
    if p == "confetti":
        for _ in range(70):
            x, y, s = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(14, 34)
            c = rnd.choice([acc, th["make"], th["miss"], (255, 255, 255)])
            if rnd.random() < 0.5:
                pts = [(x + i * s / 4, y + (s / 3 if i % 2 else 0)) for i in range(5)]
                d.line(pts, fill=c + (90,), width=5, joint="curve")
            else:
                d.polygon([(x, y), (x + s, y + s / 3), (x + s / 3, y + s)], fill=c + (70,))
    elif p == "planks":
        for y in range(0, H, 54):
            d.line((0, y, W, y), fill=(120, 80, 40, 40), width=2)
            off = rnd.randint(0, 300)
            for x in range(-off, W, 300):
                d.line((x, y, x, y + 54), fill=(120, 80, 40, 30), width=2)
    elif p == "grid":
        for x in range(0, W, 60):
            d.line((x, 0, x, H), fill=line + (40,), width=1)
        for y in range(0, H, 60):
            d.line((0, y, W, y), fill=line + (40,), width=1)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((W * 0.55, -H * 0.15, W * 1.25, H * 0.35), fill=acc + (70,))
        layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    elif p == "chalk":
        for _ in range(26):
            x, y = rnd.randint(0, W), rnd.randint(0, H)
            if rnd.random() < 0.5:
                d.text((x, y), rnd.choice("XO"), fill=(255, 255, 255, 26))
                d.ellipse((x, y, x + 34, y + 34), outline=(255, 255, 255, 28), width=3)
            else:
                d.line((x, y, x + 30, y + 30), fill=(255, 255, 255, 28), width=3)
                d.line((x, y + 30, x + 30, y), fill=(255, 255, 255, 28), width=3)
        for _ in range(4):
            x0, y0 = rnd.randint(0, W), rnd.randint(0, H)
            d.arc((x0, y0, x0 + 260, y0 + 160), 200, 340, fill=(255, 255, 255, 24), width=3)
    elif p == "rays":
        cx, cy = W / 2, H * 1.05
        for i in range(24):
            a0 = math.pi + i * math.pi / 24
            a1 = a0 + math.pi / 48
            d.polygon([(cx, cy), (cx + 2400 * math.cos(a0), cy + 2400 * math.sin(a0)),
                       (cx + 2400 * math.cos(a1), cy + 2400 * math.sin(a1))], fill=(255, 255, 255, 20))
    elif p == "pixels":
        for _ in range(240):
            x, y = rnd.randrange(0, W, 20), rnd.randrange(0, H, 20)
            d.rectangle((x, y, x + 16, y + 16), fill=acc + (rnd.randint(10, 40),))
    elif p == "blueprint":
        for x in range(0, W, 30):
            d.line((x, 0, x, H), fill=(255, 255, 255, 40 if x % 150 == 0 else 16), width=1)
        for y in range(0, H, 30):
            d.line((0, y, W, y), fill=(255, 255, 255, 40 if y % 150 == 0 else 16), width=1)
    elif p == "halftone":
        for y in range(0, H, 26):
            for x in range(0, W, 26):
                r = 2 + 6 * (y / H)
                d.ellipse((x - r, y - r, x + r, y + r), fill=(29, 47, 92, 22))
    elif p == "waves":
        for k in range(14):
            y0 = k * 110 - 40
            pts = [(x, y0 + 26 * math.sin(x / 90 + k)) for x in range(0, W + 20, 20)]
            d.line(pts, fill=(255, 255, 255, 40), width=6)
    elif p == "diamonds":
        for y in range(0, H + 80, 80):
            for x in range(0, W + 80, 80):
                d.polygon([(x, y - 30), (x + 30, y), (x, y + 30), (x - 30, y)], outline=acc + (34,), width=2)
    elif p == "frost":
        for _ in range(40):
            x, y, s = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(12, 30)
            for k in range(3):
                a = k * math.pi / 3
                d.line((x - s * math.cos(a), y - s * math.sin(a), x + s * math.cos(a), y + s * math.sin(a)),
                       fill=(0, 119, 200, 40), width=3)
    elif p == "embers":
        for _ in range(120):
            x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(2, 7)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, rnd.randint(90, 180), 0, rnd.randint(40, 120)))
        layer = layer.filter(ImageFilter.GaussianBlur(1.2))
    img.alpha_composite(layer)
    return img
