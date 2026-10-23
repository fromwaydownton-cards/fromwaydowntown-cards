"""Render the nightly leaders graphic (1080x1350, 4:5 for feeds).

Layout follows Zach's template: five headshot circles with team-color rings
and a dark stat bar under each, then every final score at the bottom.
  top:          most points
  left / right: most rebounds / most assists
  bottom row:   best 3PT% / worst plus-minus

Usage: python3 night_card.py YYYYMMDD [outfile]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from leaders import pick
from team_colors import TEAM_COLORS, _rgb, contrast

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
NUM = str(FONTS / "NotoSansBlack-Latin.otf")     # numbers and big labels
BOLD = str(FONTS / "DejaVuSans-Bold.ttf")         # names (full accent coverage)

W, H = 1080, 1350
BG = (255, 255, 255)
CIRCLE_FILL = (0, 0, 0)
BAR = (60, 60, 60)
BAR_EDGE = (10, 10, 10)
INK = (20, 20, 24)
MUTED = (120, 124, 132)
LIGHT = (205, 208, 214)
HANDLE = "@FROMWAYDOWNTOWN"

# (category, circle center, radius) from the template
SLOTS = [
    ("pts", (540, 205), 150),
    ("reb", (190, 345), 145),
    ("ast", (890, 345), 145),
    ("three", (320, 705), 148),
    ("worst_pm", (760, 705), 148),
]
TAGS = {"pts": "MOST POINTS", "reb": "MOST REBOUNDS", "ast": "MOST ASSISTS",
        "three": "BEST 3PT%", "worst_pm": "WORST +/-"}
BAR_W, BAR_H = 350, 96


def F(path, size):
    return ImageFont.truetype(path, size)


def fit(d, text, path, size, max_w, min_size=14):
    while size > min_size and d.textlength(text, font=F(path, size)) > max_w:
        size -= 1
    return F(path, size)


def ring_color(abbr):
    """Team primary color; a darker fallback only if it vanishes on white."""
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


def stat_bar(d, cx, top, p, category):
    x0 = cx - BAR_W // 2
    d.rounded_rectangle((x0, top, x0 + BAR_W, top + BAR_H), radius=6, fill=BAR,
                        outline=BAR_EDGE, width=4)
    name_f = fit(d, p["name"].upper(), BOLD, 24, BAR_W - 28)
    centered(d, cx, top + 9, p["name"].upper(), name_f, (255, 255, 255))
    stats = [("PTS", p["pts"]), ("REB", p["reb"]), ("AST", p["ast"]),
             ("TO", p["tov"]), ("STOCKS", p["stl"] + p["blk"])]
    col = (BAR_W - 20) / len(stats)
    vf, lf = F(NUM, 30), F(BOLD, 12)
    for i, (lab, val) in enumerate(stats):
        c = x0 + 10 + col * i + col / 2
        centered(d, c, top + 36, str(val), vf, (255, 255, 255))
        centered(d, c, top + 76, lab, lf, LIGHT)


def tag(d, cx, y, text, color):
    f = F(BOLD, 17)
    w = d.textlength(text, font=f) + 26
    d.rounded_rectangle((cx - w / 2, y - 15, cx + w / 2, y + 15), radius=15, fill=color)
    centered(d, cx, y - 11, text, f, (255, 255, 255))


def detail(p, category):
    if category == "three":
        return f"{p['tpm']}-{p['tpa']} 3PT  ·  {round(100 * p['tpm'] / p['tpa'])}%"
    if category == "worst_pm":
        return f"{p['pm']:+d} PLUS/MINUS"
    return None


def scoreboard(d, games, top):
    games = [g for g in games if g["final"]]
    centered(d, W / 2, top, "FINAL SCORES", F(NUM, 30), INK)
    d.line((60, top + 50, W - 60, top + 50), fill=LIGHT, width=2)
    cols = 2 if len(games) <= 12 else 3
    rows = -(-len(games) // cols)
    area_top, area_bot = top + 66, H - 70
    row_h = min(64, (area_bot - area_top) / max(rows, 1))
    col_w = (W - 120) / cols
    abbr_f, score_f = F(NUM, int(row_h * 0.46)), F(NUM, int(row_h * 0.46))
    for i, g in enumerate(games):
        r, c = i % rows, i // rows
        x = 60 + c * col_w
        y = area_top + r * row_h
        if r % 2 == 0:
            d.rounded_rectangle((x + 6, y + 2, x + col_w - 6, y + row_h - 2), radius=8,
                                fill=(244, 245, 247))
        aw = g["away_score"] > g["home_score"]
        parts = [(g["away"], g["away_score"], aw), (g["home"], g["home_score"], not aw)]
        half = (col_w - 12) / 2
        for j, (abbr, score, won) in enumerate(parts):
            sx = x + 6 + j * half
            ty = y + (row_h - abbr_f.size) / 2 - abbr_f.size * 0.12
            d.text((sx + 18, ty), abbr, font=abbr_f, fill=text_color(abbr))
            s = str(score)
            d.text((sx + half - 18 - d.textlength(s, font=score_f), ty), s, font=score_f,
                   fill=INK if won else MUTED)
        mid = x + 6 + half
        d.line((mid, y + row_h * 0.25, mid, y + row_h * 0.75), fill=LIGHT, width=2)


def render(night, out):
    leaders = pick(night["players"])
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)

    date = datetime.strptime(night["date"], "%Y%m%d")
    d.text((36, 28), date.strftime("%b %-d, %Y").upper(), font=F(NUM, 30), fill=INK)
    d.text((36, 70), "NIGHT LEADERS", font=F(BOLD, 18), fill=MUTED)
    hf = F(BOLD, 20)
    d.text((W - 36 - d.textlength(HANDLE, font=hf), 34), HANDLE, font=hf, fill=MUTED)

    for cat, (cx, cy), r in SLOTS:
        p = leaders.get(cat)
        if not p:
            continue
        img.alpha_composite(headshot_circle(p, r), (cx - r, cy - r))
        color = ring_color(p["team"])
        ring(img, cx, cy, r, color)
        d = ImageDraw.Draw(img)
        bar_top = int(cy + r * 0.42)
        stat_bar(d, cx, bar_top, p, cat)
        tag(d, cx, cy - r, TAGS[cat], color)
        extra = detail(p, cat)
        if extra:
            centered(d, cx, bar_top + BAR_H + 8, extra, F(BOLD, 17), INK)

    scoreboard(d, night["games"], 905)
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
