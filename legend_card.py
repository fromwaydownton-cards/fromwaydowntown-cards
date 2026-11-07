"""Guess the Player series card (1080x1350), one theme per post.

A "subject" describes what to draw, so the same card serves both the legends
(a famous season as a heat map, or a famous game as dots) and the current
player picked from last night's games:
  {"mode": "season"|"game", "shots": [...], "n": series number,
   "sub": "LEGENDS EDITION · 1990s", "chips": [(label, value, highlighted)],
   "hints": ["...", "..."], "reveal": "yesterday's answer" or None, "theme": {...}}

python3 legend_card.py SLUG [N] [out.jpg]    render a legends entry (for previews)
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from night_card import BOLD, HANDLE, NUM, F, centered, fit
from themes import background, theme

W, H = 1080, 1350
HOOP = 5.25        # hoop distance from the baseline, feet
DEPTH = 33.0       # feet of court shown
SS = 3


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def is_three(s):
    if "three" in s:
        return s["three"]
    return math.hypot(s["x"] - 25, s["y"]) >= 23.6 or (s["y"] <= 8.8 and (s["x"] <= 3 or s["x"] >= 47))


def court_base(w_px, th):
    """Empty themed court, w_px wide, DEPTH feet deep."""
    scale = w_px / 50.0
    k = scale * SS
    w, h = w_px * SS, int(DEPTH * scale) * SS
    img = Image.new("RGBA", (w, h), th["floor"] + (255,))
    d = ImageDraw.Draw(img)
    lw = 2 * SS
    line = th["line"]

    def P(x, y):
        return x * k, (y + HOOP) * k

    d.rectangle((0, 0, w - 1, h - 1), outline=line, width=lw)
    x0, y0 = P(17, -HOOP); x1, y1 = P(33, 19 - HOOP)
    d.rectangle((x0, y0, x1, y1), fill=th["paint"], outline=line, width=lw)
    cx, cy = P(25, 19 - HOOP)
    d.ellipse((cx - 6 * k, cy - 6 * k, cx + 6 * k, cy + 6 * k), outline=line, width=lw)
    corner_y = 14 - HOOP
    for xc in (3, 47):
        a, b = P(xc, -HOOP); c, e = P(xc, corner_y)
        d.line((a, b, c, e), fill=line, width=lw)
    hx, hy = P(25, 0)
    r3 = 23.75 * k
    start = math.degrees(math.asin(corner_y / 23.75))
    d.arc((hx - r3, hy - r3, hx + r3, hy + r3), start=start, end=180 - start, fill=line, width=lw)
    ra = 4 * k
    d.arc((hx - ra, hy - ra, hx + ra, hy + ra), start=0, end=180, fill=line, width=lw)
    bx0, by = P(22, -1.25); bx1, _ = P(28, -1.25)
    d.line((bx0, by, bx1, by), fill=line, width=3 * SS)
    rr = 0.75 * k
    d.ellipse((hx - rr, hy - rr, hx + rr, hy + rr), outline=(232, 98, 34), width=lw)
    return img.resize((w_px, int(DEPTH * scale)), Image.LANCZOS)


def on_court(s):
    return -HOOP < s["y"] < DEPTH - HOOP - 0.3 and 0 < s["x"] < 50


def shot_px(s, scale):
    x = max(0.6, min(49.4, s["x"]))
    y = min(DEPTH - HOOP - 0.6, max(-4.5, s["y"]))
    return x * scale, (y + HOOP) * scale


def dot_sprites(th, size):
    s = size * 4
    mk = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(mk).ellipse((6, 6, s - 6, s - 6), fill=th["make"] + (255,), outline=(255, 255, 255, 255),
                               width=max(6, s // 10))
    ms = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    q = s * 0.22
    dm = ImageDraw.Draw(ms)
    dm.line((q, q, s - q, s - q), fill=th["miss"] + (255,), width=s // 7)
    dm.line((q, s - q, s - q, q), fill=th["miss"] + (255,), width=s // 7)
    return {True: mk.resize((size, size), Image.LANCZOS), False: ms.resize((size, size), Image.LANCZOS)}


def hexbins(shots, hex_ft=1.6):
    """[(cx_ft, cy_ft_from_hoop, attempts, points_per_shot)] on a pointy-top hex grid."""
    r = hex_ft
    dx, dy = math.sqrt(3) * r, 1.5 * r
    bins = {}
    for s in shots:
        if not on_court(s):
            continue
        X, Y = s["x"], s["y"] + HOOP
        row = round(Y / dy)
        col = round((X - (row % 2) * dx / 2) / dx)
        best = None
        for rr in (row - 1, row, row + 1):
            for cc in (col - 1, col, col + 1):
                cx, cy = cc * dx + (rr % 2) * dx / 2, rr * dy
                dd = (X - cx) ** 2 + (Y - cy) ** 2
                if best is None or dd < best[0]:
                    best = (dd, rr, cc, cx, cy)
        _, rr, cc, cx, cy = best
        b = bins.setdefault((rr, cc), [cx, cy - HOOP, 0, 0])
        b[2] += 1
        b[3] += (3 if is_three(s) else 2) if s["made"] else 0
    return [(cx, cy, n, pts / n) for cx, cy, n, pts in bins.values()]


def heat_layer(shots, w_px, th, reveal=1.0):
    """Season heat map: hex size = how often he shot there, color = points per shot."""
    scale = w_px / 50.0
    h_px = int(DEPTH * scale)
    big = Image.new("RGBA", (w_px * SS, h_px * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    bins = hexbins(shots)
    if not bins:
        return big.resize((w_px, h_px), Image.LANCZOS)
    top = sorted(n for *_, n, _ in bins)[int(len(bins) * 0.97) - 1] if len(bins) > 30 else max(n for *_, n, _ in bins)
    cold, mid, hot = th["miss"], mix(th["miss"], th["make"], 0.5), th["make"]
    r_ft = 1.6
    for cx, cy, n, pps in sorted(bins, key=lambda b: b[2]):
        f = min(1.0, n / max(top, 1))
        if f < 0.04:
            continue
        rad = r_ft * (0.35 + 0.65 * math.sqrt(f)) * reveal * scale * SS * 0.98
        t = (pps - 0.7) / 0.7           # 0.7 PPS = cold, 1.4 PPS = hot
        col = mix(cold, mid, t * 2) if t < 0.5 else mix(mid, hot, (t - 0.5) * 2)
        px, py = cx * scale * SS, (cy + HOOP) * scale * SS
        pts = [(px + rad * math.cos(math.radians(30 + 60 * i)), py + rad * math.sin(math.radians(30 + 60 * i)))
               for i in range(6)]
        d.polygon(pts, fill=col + (235,))
    return big.resize((w_px, h_px), Image.LANCZOS)


def court_image(subject, w_px, shown=None, reveal=1.0):
    th = subject["theme"]
    img = court_base(w_px, th)
    shots = subject["shots"]
    if subject["mode"] == "season":
        sub = shots if shown is None else shots[:shown]
        img.alpha_composite(heat_layer(sub, w_px, th, reveal))
    else:
        scale = w_px / 50.0
        spr = dot_sprites(th, max(14, int(w_px / 62)))
        sub = shots if shown is None else shots[:shown]
        for s in sorted(sub, key=lambda s: s["made"]):
            x, y = shot_px(s, scale)
            sp = spr[s["made"]]
            img.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))
    return img


def legend_key(d, x, y, subject, size=16):
    th = subject["theme"]
    ink = th["ink"]
    f = F(BOLD, size)
    if subject["mode"] == "season":
        cold, hot = th["miss"], th["make"]
        d.text((x, y), "COLD", font=f, fill=ink)
        bx = x + d.textlength("COLD ", font=f)
        for i in range(5):
            t = i / 4
            c = mix(cold, mix(cold, hot, 0.5), t * 2) if t < 0.5 else mix(mix(cold, hot, 0.5), hot, (t - 0.5) * 2)
            d.regular_polygon((bx + 11 + i * 24, y + size * 0.6, 10), 6, rotation=30, fill=c)
        hx = bx + 5 * 24 + 6
        d.text((hx, y), "HOT", font=f, fill=ink)
        d.text((hx + d.textlength("HOT  ·  ", font=f) - d.textlength("  ·  ", font=f), y), "  ·  BIGGER = MORE SHOTS",
               font=f, fill=th["muted"])
    else:
        d.ellipse((x, y + 2, x + size, y + size + 2), fill=th["make"], outline=(255, 255, 255), width=2)
        d.text((x + size + 8, y), "MADE", font=f, fill=ink)
        mx = x + size + 8 + d.textlength("MADE", font=f) + 24
        d.line((mx + 2, y + 4, mx + size - 2, y + size), fill=th["miss"], width=4)
        d.line((mx + 2, y + size, mx + size - 2, y + 4), fill=th["miss"], width=4)
        d.text((mx + size + 8, y), "MISSED", font=f, fill=ink)


def chip_bar(d, x, y, w, items, th, h=86, vsize=34):
    d.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=th["chip"])
    col = (w - 16) / len(items)
    for i, (lab, val, hot) in enumerate(items):
        c = x + 8 + col * i + col / 2
        vf = fit(d, str(val), NUM, vsize, col - 8)
        centered(d, c, y + 10, str(val), vf, th["accent"] if hot else (255, 255, 255))
        centered(d, c, y + h - 28, lab, F(BOLD, 14), th["accent"] if hot else (200, 204, 214))


def pill(d, x, y, text, th, size=19, max_w=None):
    f = F(BOLD, size)
    if max_w:
        f = fit(d, text, BOLD, size, max_w - 34)
    w = d.textlength(text, font=f) + 34
    d.rounded_rectangle((x, y, x + w, y + 38), radius=19, fill=th["chip"])
    d.text((x + 17, y + (38 - f.size) / 2 - 2), text, font=f, fill=th["accent"])
    return w


def mystery(img, cx, cy, r, th):
    d = ImageDraw.Draw(img)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=th["accent"] + (120,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=th["chip"], outline=th["accent"], width=6)
    qf = F(NUM, int(r * 1.3))
    l, t, rr, b = d.textbbox((0, 0), "?", font=qf)
    d.text((cx - (rr - l) / 2 - l, cy - (b - t) / 2 - t), "?", font=qf, fill=th["accent"])


def header(img, subject):
    th = subject["theme"]
    d = ImageDraw.Draw(img)
    tf = F(NUM, 54)
    d.text((36, 22), "GUESS THE PLAYER", font=tf, fill=th["ink"])
    tw = d.textlength("GUESS THE PLAYER", font=tf)
    num = f"#{subject['n']}"
    nf = F(NUM, 30)
    nw = d.textlength(num, font=nf) + 30
    d.rounded_rectangle((36 + tw + 18, 34, 36 + tw + 18 + nw, 78), radius=22, fill=th["accent"])
    d.text((36 + tw + 33, 36), num, font=nf, fill=th["chip"])
    d.text((38, 92), subject["sub"], font=F(BOLD, 19), fill=th["muted"])
    hf = F(BOLD, 18)
    d.text((W - 36 - d.textlength(HANDLE, font=hf), 98), HANDLE, font=hf, fill=th["muted"])


def render(subject, out):
    th = subject["theme"]
    img = background(W, H, th, seed=subject["n"])
    header(img, subject)
    d = ImageDraw.Draw(img)
    cw = W - 72
    cx0, cy0 = 36, 138
    ct = court_image(subject, cw)
    d.rounded_rectangle((cx0 - 6, cy0 - 6, cx0 + cw + 6, cy0 + ct.height + 6), radius=12, fill=th["accent"])
    img.alpha_composite(ct, (cx0, cy0))
    d = ImageDraw.Draw(img)
    legend_key(d, cx0 + 4, cy0 + ct.height + 16, subject)

    r = 96
    top = cy0 + ct.height + 58
    hx, hy = 36 + r + 10, top + r + 4
    mystery(img, hx, hy, r, th)
    d = ImageDraw.Draw(img)
    px = hx + r + 34
    pw = W - 36 - px
    chip_bar(d, px, top, pw, subject["chips"], th)
    y = top + 100
    for h in subject["hints"][:2]:
        pill(d, px, y, "HINT: " + h, th, max_w=pw)
        y += 46

    cta_y = max(hy + r + 28, y + 14)
    if subject.get("reveal"):
        rf = fit(d, "LAST ANSWER: " + subject["reveal"], BOLD, 20, W - 72)
        centered(d, W / 2, cta_y, "LAST ANSWER: " + subject["reveal"], rf, th["ink"])
        cta_y += 36
    d.rounded_rectangle((36, cta_y, W - 36, H - 30), radius=16, fill=th["chip"])
    mid = (cta_y + H - 30) / 2
    centered(d, W / 2, mid - 40, "DROP YOUR GUESS IN THE COMMENTS", F(NUM, 38), (255, 255, 255))
    centered(d, W / 2, mid + 12, "ANSWER IN TOMORROW'S POST", F(BOLD, 20), th["accent"])
    img.convert("RGB").save(out, "JPEG", quality=93, subsampling=0)
    return out


# ---------- subjects ---------------------------------------------------------

def profile(shots):
    """Share of his shots at the rim (within 6 ft), from midrange and from three."""
    n = len(shots) or 1
    three = sum(is_three(s) for s in shots)
    rim = sum(not is_three(s) and math.hypot(s["x"] - 25, s["y"]) <= 6 for s in shots)
    pct = lambda k: f"{round(100 * k / n)}%"
    return {"rim": pct(rim), "mid": pct(n - three - rim), "three": pct(three)}


def legend_subject(rec, n, reveal=None):
    e, st = rec["entry"], rec["stats"]
    from legends import decade
    shots = sorted(rec["shots"], key=lambda s: (s["date"], not s["made"]))
    if e["mode"] == "season":
        pr = profile(shots)
        chips = [("PPG", f"{e['ppg']:.1f}", True), ("AT THE RIM", pr["rim"], False),
                 ("MIDRANGE", pr["mid"], False), ("THREES", pr["three"], False)]
        sub = f"LEGENDS EDITION  ·  HIS {e['season']} SEASON SHOT CHART"
    else:
        chips = [("PTS", e["pts"], True), ("FG", f"{st['fgm']}-{st['fga']}", False),
                 ("3PT", f"{st['tpm']}-{st['tpa']}", False), ("FT MADE", st["ftm"], False)]
        sub = f"LEGENDS EDITION  ·  ONE GAME IN THE {decade(e).upper()}"
    return {"mode": e["mode"], "shots": shots, "n": n, "sub": sub, "chips": chips,
            "hints": list(e["hints"]), "reveal": reveal, "theme": theme(n)}


if __name__ == "__main__":
    from legends import load
    slug = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(f"{slug}.jpg")
    render(legend_subject(load(slug), n, reveal="KOBE BRYANT, 81 PTS (JAN 22, 2006)"), out)
    print(out)
