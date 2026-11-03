"""Render the nightly leaders graphic (1080x1920, 9:16, dark).

One row per leader (points, rebounds, assists, best 3PT%, worst +/-): the
team color bleeds in behind the headshot and the stat that earned the spot
is huge (gold, red for worst +/-). Final scores go in the caption, not the
graphic. Nothing important sits in the bottom ~20%, which TikTok/Reels cover.

This module also holds the shared dark palette used by every card and video.

Usage: python3 night_card.py YYYYMMDD [outfile]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from leaders import pick
from team_colors import TEAM_COLORS, _rgb, contrast

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
NUM = str(FONTS / "NotoSansBlack-Latin.otf")     # numbers and big labels
BOLD = str(FONTS / "DejaVuSans-Bold.ttf")         # names (full accent coverage)

W, H = 1080, 1920
BG = (11, 12, 16)             # near-black
PANEL = (24, 26, 32)          # cards / zebra rows on BG
CIRCLE_FILL = (150, 154, 160)   # gray so hair and skin stand out
BAR = (34, 36, 44)
BAR_EDGE = (64, 68, 80)
INK = (245, 246, 250)
MUTED = (140, 146, 160)
LIGHT = (150, 156, 170)
RED = (255, 59, 59)
HANDLE = "@FROMWAYDOWNTOWN"
HIGHLIGHT = (255, 214, 10)   # yellow for the stat that earned the spot
HIGHLIGHT_STAT = {"pts": "PTS", "reb": "REB", "ast": "AST"}

ROWS = [("pts", "MOST POINTS"), ("reb", "MOST REBOUNDS"), ("ast", "MOST ASSISTS"),
        ("three", "BEST 3PT%"), ("worst_pm", "WORST +/-")]
TAGS = dict(ROWS)
ROW_TOP, ROW_H, ROW_GAP = 200, 240, 22
IMG = [None]   # current canvas, so the bar can paste logos


def F(path, size):
    return ImageFont.truetype(path, size)


def fit(d, text, path, size, max_w, min_size=14):
    while size > min_size and d.textlength(text, font=F(path, size)) > max_w:
        size -= 1
    return F(path, size)


def ring_color(abbr):
    """Team primary color, or the secondary if the primary vanishes on the dark background."""
    for h in TEAM_COLORS.get(abbr, ()):
        c = _rgb(h)
        if contrast(c, BG) >= 1.6:
            return c
    return INK


def text_color(abbr):
    for h in TEAM_COLORS.get(abbr, ()):
        c = _rgb(h)
        if contrast(c, BG) >= 2.5:
            return c
    return INK


def vivid(abbr):
    """Team color for glows/gradients on near-black (skips blacks and navies)."""
    for h in TEAM_COLORS.get(abbr, ()):
        c = _rgb(h)
        if sum(c) > 200:
            return c
    return (150, 150, 160)


def centered(d, cx, y, text, font, fill):
    d.text((cx - d.textlength(text, font=font) / 2, y), text, font=font, fill=fill)


def headshot_circle(p, r):
    """Black disc with the player's cutout headshot, framed head-and-shoulders."""
    size = 2 * r
    disc = Image.new("RGBA", (size, size), CIRCLE_FILL + (255,))
    f = ROOT / "data" / "headshots" / f"{p['id']}.png"
    if f.exists():
        hs = Image.open(f).convert("RGBA")
        scale = (size * 1.42) / hs.width
        hs = hs.resize((int(hs.width * scale), int(hs.height * scale)), Image.LANCZOS)
        x = (size - hs.width) // 2
        y = int(size * 0.02)
        disc.alpha_composite(hs, (x, y)) if x >= 0 else disc.paste(hs, (x, y), hs)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(disc, (0, 0), mask)
    return out


def ring(img, cx, cy, r, color, width=7):
    big = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((2 * (cx - r), 2 * (cy - r), 2 * (cx + r), 2 * (cy + r)),
                                outline=color + (255,), width=width * 2)
    img.alpha_composite(big.resize((W, H), Image.LANCZOS))


def glow_text(img, xy, text, font, fill, glow, blur=16):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=font, fill=glow + (230,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).text(xy, text, font=font, fill=fill)


def cutout(p, width):
    f = ROOT / "data" / "headshots" / f"{p['id']}.png"
    if not f.exists():
        return None
    hs = Image.open(f).convert("RGBA")
    s = width / hs.width
    return hs.resize((int(hs.width * s), int(hs.height * s)), Image.LANCZOS)


def hero(p, cat):
    """(big number, line beside it, small line under it) for a leader row."""
    if cat == "three":
        return f"{p['tpm']}-{p['tpa']}", f"FROM 3  ·  {round(100 * p['tpm'] / p['tpa'])}%", ""
    if cat == "worst_pm":
        return f"{p['pm']:+d}", f"{p['pts']} PTS  ·  {p['fgm']}-{p['fga']} FG", ""
    unit = HIGHLIGHT_STAT[cat]
    rest = [f"{v} {l}" for v, l in ((p["pts"], "PTS"), (p["reb"], "REB"), (p["ast"], "AST")) if l != unit]
    return str(p[cat]), unit, "  ·  ".join(rest)


def leader_row(img, y, p, cat):
    h, x0, x1 = ROW_H, 50, W - 50
    col = vivid(p["team"])
    accent = RED if cat == "worst_pm" else HIGHLIGHT
    card = Image.new("RGBA", (x1 - x0, h), PANEL + (255,))
    grad = Image.new("RGBA", card.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for i in range(card.width):
        gd.line((i, 0, i, h), fill=col + (max(0, int(150 * (1 - i / (card.width * 0.6)))),))
    card.alpha_composite(grad)
    m = Image.new("L", card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, card.width - 1, h - 1), radius=28, fill=255)
    img.paste(card, (x0, y), m)
    hs = cutout(p, int(h * 1.55))
    if hs:
        hs = hs.crop((0, 0, hs.width, min(hs.height, h - 6)))
        img.alpha_composite(hs, (x0 + 10, y + h - hs.height))
    d = ImageDraw.Draw(img)
    tx = x0 + 360
    d.text((tx, y + 26), TAGS[cat], font=F(BOLD, 24), fill=accent)
    name = p["name"].upper()
    d.text((tx, y + 58), name, font=fit(d, name, NUM, 40, x1 - tx - 90), fill=INK)
    big, side, under = hero(p, cat)
    bf = F(NUM, 108)
    glow_text(img, (tx - 4, y + 92), big, bf, accent, accent)
    d = ImageDraw.Draw(img)
    bw = d.textlength(big, font=bf)
    d.text((tx + bw + 18, y + 150), side, font=F(NUM, 34), fill=accent if under else MUTED)
    if under:
        d.text((tx + bw + 18, y + 192), under, font=F(BOLD, 22), fill=MUTED)
    lf = ROOT / "data" / "logos" / f"{p['team']}.png"
    if lf.exists():
        lg = Image.open(lf).convert("RGBA")
        lg.thumbnail((56, 56), Image.LANCZOS)
        img.alpha_composite(lg, (x1 - 30 - lg.width, y + 22))


def render(night, out, upto=5):
    leaders = pick(night["players"])
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    date = datetime.strptime(night["date"], "%Y%m%d")
    n = sum(g["final"] for g in night["games"])
    d.text((60, 70), date.strftime("%b %-d").upper(), font=F(NUM, 44), fill=INK)
    d.text((60, 128), f"NIGHT LEADERS  ·  {n} GAMES", font=F(BOLD, 22), fill=MUTED)
    hf = F(BOLD, 22)
    d.text((W - 60 - d.textlength(HANDLE, font=hf), 84), HANDLE, font=hf, fill=MUTED)
    shown = [(c, leaders[c]) for c, _ in ROWS if c in leaders][:upto]
    for i, (cat, p) in enumerate(shown):
        leader_row(img, ROW_TOP + i * (ROW_H + ROW_GAP), p, cat)
    d = ImageDraw.Draw(img)
    centered(d, W / 2, ROW_TOP + 5 * (ROW_H + ROW_GAP) + 4, f"All {n} final scores in the caption",
             F(BOLD, 24), MUTED)
    img.convert("RGB").save(out, "JPEG", quality=93, subsampling=0)
    return leaders

if __name__ == "__main__":
    date = sys.argv[1]
    night = json.loads((ROOT / "data" / "nights" / f"{date}.json").read_text())
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "cards" / "nights" / f"{date}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    for k, p in render(night, out).items():
        print(k, p["name"], p["team"])
    print(out)
