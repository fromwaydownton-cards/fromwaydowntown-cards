"""Shot charts for the night's top 3 scorers (1080x1350), matching the
leaders graphic: white background, gray headshot discs with team-color rings,
dark stat bars, yellow highlights.

Coordinates (from ESPN play-by-play): feet, x 0-50 across the court,
y = distance from the basket toward half court (basket at x=25, y=0).

Usage: python3 shot_card.py YYYYMMDD [outfile]   (needs data/shots/YYYYMMDD.json)
"""
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from night_card import (BAR, BAR_EDGE, BG, BOLD, HANDLE, HIGHLIGHT, INK, LIGHT, MUTED, NUM,
                        ROOT, F, centered, fit, headshot_circle, ring_color)

W, H = 1080, 1350
HOOP_FROM_BASELINE = 5.25
DEPTH = 33.0                  # feet of court shown, from the baseline
COURT_W_PX = 470
SCALE = COURT_W_PX / 50.0     # px per foot
COURT_H_PX = int(DEPTH * SCALE)
SS = 3                        # supersampling for smooth lines
FLOOR = (241, 236, 228)
LINE = (178, 168, 152)
MAKE = (34, 166, 82)
MISS = (214, 48, 49)


def shot_distance(s):
    m = re.search(r"(\d+)-foot", s.get("text", ""))
    return int(m.group(1)) if m else math.hypot(s["x"] - 25, s["y"])


def tag_threes(shots, box_tpm, box_tpa):
    """Mark each shot as a three so totals match the official box score.
    Makes: ESPN's point value is exact. Misses: the longest misses (by the
    play text's distance, then court position) fill the box score's missed threes."""
    for s in shots:
        s["three"] = s["made"] and s.get("value") == 3
    misses = [s for s in shots if not s["made"]]
    need = max(0, (box_tpa - box_tpm))
    def key(s):
        t = s.get("text", "").lower()
        corner = s["y"] <= 8.8 and (s["x"] <= 3 or s["x"] >= 47)
        return ("three point" in t, corner, shot_distance(s))
    for s in sorted(misses, key=key, reverse=True)[:need]:
        s["three"] = True
    return shots


def is_three(s):
    if "three" in s:
        return s["three"]
    t = s["text"].lower()
    if "three point" in t or s.get("value") == 3:
        return True
    return math.hypot(s["x"] - 25, s["y"]) >= 23.6 or (s["y"] <= 8.8 and (s["x"] <= 3 or s["x"] >= 47))


def zone(s):
    if is_three(s):
        return "3PT"
    in_paint = 17 <= s["x"] <= 33 and s["y"] + HOOP_FROM_BASELINE <= 19
    return "PAINT" if in_paint else "MID"


def court(shots, w_px=COURT_W_PX, dot=9):
    scale = w_px / 50.0
    w, h = w_px * SS, int(DEPTH * scale) * SS
    k = scale * SS
    img = Image.new("RGBA", (w, h), FLOOR + (255,))
    d = ImageDraw.Draw(img)
    lw = 2 * SS

    def P(x, y):  # court feet (hoop-relative y) -> px
        return x * k, (y + HOOP_FROM_BASELINE) * k

    d.rectangle((0, 0, w - 1, h - 1), outline=LINE, width=lw)
    # paint + free throw circle
    x0, y0 = P(17, -HOOP_FROM_BASELINE); x1, y1 = P(33, 19 - HOOP_FROM_BASELINE)
    d.rectangle((x0, y0, x1, y1), fill=(233, 226, 214), outline=LINE, width=lw)
    cx, cy = P(25, 19 - HOOP_FROM_BASELINE)
    d.ellipse((cx - 6 * k, cy - 6 * k, cx + 6 * k, cy + 6 * k), outline=LINE, width=lw)
    # three-point line: corners then arc
    corner_y = 14 - HOOP_FROM_BASELINE
    for xc in (3, 47):
        a, b = P(xc, -HOOP_FROM_BASELINE); c, e = P(xc, corner_y)
        d.line((a, b, c, e), fill=LINE, width=lw)
    hx, hy = P(25, 0)
    r3 = 23.75 * k
    start = math.degrees(math.asin(corner_y / 23.75))
    d.arc((hx - r3, hy - r3, hx + r3, hy + r3), start=start, end=180 - start, fill=LINE, width=lw)
    # restricted area, backboard, rim
    ra = 4 * k
    d.arc((hx - ra, hy - ra, hx + ra, hy + ra), start=0, end=180, fill=LINE, width=lw)
    bx0, by = P(22, -1.25); bx1, _ = P(28, -1.25)
    d.line((bx0, by, bx1, by), fill=(120, 112, 100), width=3 * SS)
    rr = 0.75 * k
    d.ellipse((hx - rr, hy - rr, hx + rr, hy + rr), outline=(232, 98, 34), width=lw)

    # misses first, makes on top
    r = dot * SS
    for s in sorted(shots, key=lambda s: s["made"]):
        x, y = P(max(0.6, min(49.4, s["x"])), min(DEPTH - HOOP_FROM_BASELINE - 0.6, max(-4.5, s["y"])))
        if s["made"]:
            d.ellipse((x - r, y - r, x + r, y + r), fill=MAKE + (255,), outline=(255, 255, 255), width=2 * SS)
        else:
            q = r * 0.75
            d.line((x - q, y - q, x + q, y + q), fill=MISS, width=4 * SS)
            d.line((x - q, y + q, x + q, y - q), fill=MISS, width=4 * SS)
    return img.resize((w_px, int(DEPTH * scale)), Image.LANCZOS)


def splits(shots):
    out = {}
    for z in ("PAINT", "MID", "3PT"):
        zs = [s for s in shots if zone(s) == z]
        out[z] = (sum(s["made"] for s in zs), len(zs))
    return out


def chip_row(d, x, y, items, width):
    """Dark bar with value-over-label cells; items: [(label, value, highlighted)]."""
    h = 78
    d.rounded_rectangle((x, y, x + width, y + h), radius=6, fill=BAR, outline=BAR_EDGE, width=4)
    col = (width - 16) / len(items)
    vf, lf = F(NUM, 30), F(BOLD, 12)
    for i, (lab, val, hot) in enumerate(items):
        c = x + 8 + col * i + col / 2
        centered(d, c, y + 10, str(val), vf, HIGHLIGHT if hot else (255, 255, 255))
        centered(d, c, y + 53, lab, lf, HIGHLIGHT if hot else LIGHT)
    return y + h


def render(shots_data, date, out):
    rows = sorted(shots_data.values(), key=lambda v: (-v["player"]["pts"], v["player"]["fga"]))[:3]
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    dt = datetime.strptime(date, "%Y%m%d")
    d.text((36, 28), dt.strftime("%b %-d, %Y").upper(), font=F(NUM, 30), fill=INK)
    d.text((36, 70), "TOP SCORERS · SHOT CHARTS", font=F(BOLD, 18), fill=MUTED)
    hf = F(BOLD, 20)
    d.text((W - 36 - d.textlength(HANDLE, font=hf), 34), HANDLE, font=hf, fill=MUTED)
    # legend
    lx, ly = W - 36 - 250, 72
    d.ellipse((lx, ly + 3, lx + 16, ly + 19), fill=MAKE, outline=(255, 255, 255), width=2)
    d.text((lx + 24, ly), "MADE", font=F(BOLD, 16), fill=INK)
    mx = lx + 110
    d.line((mx + 2, ly + 5, mx + 14, ly + 17), fill=MISS, width=4)
    d.line((mx + 2, ly + 17, mx + 14, ly + 5), fill=MISS, width=4)
    d.text((mx + 24, ly), "MISSED", font=F(BOLD, 16), fill=INK)

    top, row_h = 120, 405
    for i, v in enumerate(rows):
        p, shots = v["player"], v["shots"]
        y = top + i * row_h
        color = ring_color(p["team"])
        # court with a team-color frame
        cx0, cy0 = 36, y + 24
        d.rounded_rectangle((cx0 - 5, cy0 - 5, cx0 + COURT_W_PX + 5, cy0 + COURT_H_PX + 5), radius=8, fill=color)
        img.alpha_composite(court(shots), (cx0, cy0))
        d = ImageDraw.Draw(img)
        # player panel
        px = cx0 + COURT_W_PX + 40
        pw = W - 36 - px
        r = 70
        hcx, hcy = px + r + 6, cy0 + r + 6
        img.alpha_composite(headshot_circle(p, r), (hcx - r, hcy - r))
        big = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
        ImageDraw.Draw(big).ellipse((2 * (hcx - r), 2 * (hcy - r), 2 * (hcx + r), 2 * (hcy + r)),
                                    outline=color + (255,), width=12)
        img.alpha_composite(big.resize((W, H), Image.LANCZOS))
        d = ImageDraw.Draw(img)
        nx = hcx + r + 22
        rank = f"#{i + 1} SCORER"
        d.text((nx, hcy - 62), rank, font=F(BOLD, 17), fill=color)
        logo_f = ROOT / "data" / "logos" / f"{p['team']}.png"
        name = p["name"].upper()
        parts = name.split(" ", 1)
        nf = fit(d, max(parts, key=len), NUM, 40, W - 36 - nx - 6)
        d.text((nx, hcy - 38), parts[0], font=nf, fill=INK)
        if len(parts) > 1:
            d.text((nx, hcy - 38 + nf.size), parts[1], font=nf, fill=INK)
        if logo_f.exists():
            lg = Image.open(logo_f).convert("RGBA")
            lg.thumbnail((40, 40), Image.LANCZOS)
            # the light-background logo reads better on white; fall back to what we have
            img.alpha_composite(lg, (int(W - 36 - lg.width), int(hcy - 66)))
            d = ImageDraw.Draw(img)
        tag_threes(shots, p["tpm"], p["tpa"])
        made = sum(s["made"] for s in shots)
        sp = splits(shots)
        tpm, tpa = sp["3PT"]
        by = cy0 + 2 * r + 28
        by = chip_row(d, px, by, [("PTS", p["pts"], True), ("FG", f"{made}-{len(shots)}", False),
                                  ("3PT", f"{tpm}-{tpa}", False), ("FT", f"{v['ft_made']}-{v['ft_att']}", False)], pw)
        by += 12
        zf, zl = F(NUM, 22), F(BOLD, 13)
        zw = (pw - 16) / 3
        for j, z in enumerate(("PAINT", "MID", "3PT")):
            m, a = sp[z]
            zx = px + j * (zw + 8)
            d.rounded_rectangle((zx, by, zx + zw, by + 58), radius=6, fill=(244, 245, 247))
            pct = f"{round(100 * m / a)}%" if a else "–"
            centered(d, zx + zw / 2, by + 6, f"{m}-{a}  {pct}", zf, INK)
            centered(d, zx + zw / 2, by + 36, z if z != "MID" else "MIDRANGE", zl, MUTED)
        if i < len(rows) - 1:
            d.line((36, y + row_h - 6, W - 36, y + row_h - 6), fill=(230, 232, 236), width=2)

    img.convert("RGB").save(out, "JPEG", quality=93, subsampling=0)
    return rows


if __name__ == "__main__":
    date = sys.argv[1]
    data = json.loads((ROOT / "data" / "shots" / f"{date}.json").read_text())
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "cards" / "shots" / f"{date}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    for v in render(data, date, out):
        print(v["player"]["name"], len(v["shots"]), "shots")
    print(out)
