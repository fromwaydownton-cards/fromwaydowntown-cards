"""Guess the Player series card (1080x1350), one theme per post.

A "subject" describes what to draw, so the same card serves both the legends
(a famous season as a zone chart, or a famous game as dots) and the current
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


# ---------- season zone chart (replaced the hex heat map, Nov 2026) ----------
# 8 big zones; shade = share of his shots, label = FG% there. Label spots are
# in feet (x across, y from the hoop).
ZONES = ["RIM", "PAINT", "MID L", "MID C", "MID R", "3 L", "3 C", "3 R"]
ZONE_LABEL_AT = {"RIM": (25, 0.6), "PAINT": (25, 9.4), "MID L": (9.5, 5.5), "MID C": (25, 18.2),
                 "MID R": (40.5, 5.5), "3 L": (6.2, 21.0), "3 C": (25, 25.4), "3 R": (43.8, 21.0)}


def zone_of(x, y, three=None):
    """Zone name for a spot (feet; y from the hoop)."""
    if three is None:
        three = math.hypot(x - 25, y) >= 23.75 or (y <= 14 - HOOP and (x <= 3 or x >= 47))
    ang = math.degrees(math.atan2(y, x - 25))     # 0 = right baseline, 180 = left
    side = "R" if ang < 60 else ("L" if ang > 120 or ang < -90 else "C")
    if y < 0:
        side = "R" if x > 25 else "L"
    if three:
        return "3 " + side
    if math.hypot(x - 25, y) < 4:
        return "RIM"
    if 17 <= x <= 33 and y < 19 - HOOP:
        return "PAINT"
    return "MID " + side


def zone_stats(shots):
    st = {z: [0, 0] for z in ZONES}
    for s in shots:
        if not on_court(s):
            continue
        z = zone_of(s["x"], s["y"], is_three(s))
        st[z][0] += 1
        st[z][1] += 1 if s["made"] else 0
    return st


_ZMAP = {}


def zone_map(w_px):
    """Per-pixel zone index (numpy array), cached per width."""
    if w_px not in _ZMAP:
        import numpy as np
        scale = w_px / 50.0
        h_px = int(DEPTH * scale)
        zm = np.zeros((h_px, w_px), dtype=np.int8)
        for py in range(h_px):
            y = (py + 0.5) / scale - HOOP
            for px in range(w_px):
                zm[py, px] = ZONES.index(zone_of((px + 0.5) / scale, y))
        _ZMAP[w_px] = zm
    return _ZMAP[w_px]


def zone_layer(shots, w_px, th, reveal=1.0):
    """Shaded zones with FG% labels. reveal 0..1 fades it in (video)."""
    import numpy as np
    scale = w_px / 50.0
    zm = zone_map(w_px)
    h_px, _ = zm.shape
    st = zone_stats(shots)
    n = sum(a for a, _ in st.values()) or 1
    top = max(a for a, _ in st.values()) or 1
    rgba = np.zeros((h_px, w_px, 4), dtype=np.uint8)
    acc = th["line"]
    for i, z in enumerate(ZONES):
        a = st[z][0]
        if not a:
            continue
        alpha = int((18 + 112 * (a / top) ** 0.9) * reveal)
        m = zm == i
        rgba[m] = (*acc, alpha)
    # thin zone borders
    edge = np.zeros_like(zm, dtype=bool)
    edge[:, 1:] |= zm[:, 1:] != zm[:, :-1]
    edge[1:, :] |= zm[1:, :] != zm[:-1, :]
    rgba[edge] = (*th["line"], int(150 * reveal))
    img = Image.fromarray(rgba, "RGBA")
    if reveal <= 0.05:
        return img
    d = ImageDraw.Draw(img)
    big = F(NUM, max(14, int(scale * 1.9)))
    small = F(BOLD, max(10, int(scale * 0.86)))
    ta = int(255 * min(1.0, reveal * 1.5))
    for z in ZONES:
        a, m = st[z]
        if a / n < 0.015:
            continue
        cx, cy = ZONE_LABEL_AT[z]
        px, py = cx * scale, (cy + HOOP) * scale
        pct = f"{round(100 * m / a)}%"
        sub = f"{round(100 * a / n)}% OF SHOTS"
        l1, t1, r1, b1 = d.textbbox((0, 0), pct, font=big)
        l2, t2, r2, b2 = d.textbbox((0, 0), sub, font=small)
        gap, pad = scale * 0.3, scale * 0.45
        bw = max(r1 - l1, r2 - l2) + 2 * pad
        bh = (b1 - t1) + gap + (b2 - t2) + 2 * pad
        top_y = py - bh / 2
        d.rounded_rectangle((px - bw / 2, top_y, px + bw / 2, top_y + bh), radius=int(scale * 0.45),
                            fill=th["chip"] + (int(225 * min(1.0, reveal * 1.5)),))
        d.text((px - (r1 - l1) / 2 - l1, top_y + pad - t1), pct, font=big, fill=(255, 255, 255, ta))
        d.text((px - (r2 - l2) / 2 - l2, top_y + pad + (b1 - t1) + gap - t2), sub, font=small,
               fill=th["muted"] + (ta,))
    return img


def spread(shots, min_ft=0.9):
    """Shots logged at the same spot (layups are often all at the rim) would hide
    each other; nudge repeats around a small circle so every shot shows."""
    out, placed = [], []
    for s in shots:
        x, y = s["x"], s["y"]
        k = 0
        while any(math.hypot(x - px, y - py) < min_ft for px, py in placed) and k < 24:
            k += 1
            ang = k * 2.4
            rad = min_ft * (0.8 + 0.25 * k)
            x, y = s["x"] + rad * math.cos(ang), max(-4.0, s["y"] + rad * math.sin(ang))
        placed.append((x, y))
        out.append(dict(s, x=x, y=y))
    return out


def court_image(subject, w_px, shown=None, reveal=1.0):
    th = subject["theme"]
    img = court_base(w_px, th)
    shots = subject["shots"]
    if subject["mode"] == "season":
        sub = shots if shown is None else shots[:shown]
        img.alpha_composite(zone_layer(sub, w_px, th, reveal))
    else:
        scale = w_px / 50.0
        spr = dot_sprites(th, max(14, int(w_px / 62)))
        sub = spread(shots)
        sub = sub if shown is None else sub[:shown]
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
        d.rounded_rectangle((x, y + 1, x + size + 4, y + size + 3), radius=4, fill=th["line"])
        d.text((x + size + 14, y), "BRIGHTER = MORE SHOTS", font=f, fill=ink)
        d.text((x + size + 14 + d.textlength("BRIGHTER = MORE SHOTS", font=f), y), "  ·  BIG NUMBER = FG% FROM THERE",
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
    centered(d, W / 2, mid - 46, "DROP YOUR GUESS IN THE COMMENTS", F(NUM, 44), (255, 255, 255))
    centered(d, W / 2, mid + 16, "ANSWER IN TOMORROW'S POST", F(BOLD, 24), th["accent"])
    img.convert("RGB").save(out, "JPEG", quality=93, subsampling=0)
    return out


# ---------- subjects ---------------------------------------------------------

def profile(rec):
    """Share of his shots from 0-3 ft, midrange and three. Uses the official
    split when the source has one (late-90s charts miss some shots)."""
    if rec.get("profile"):
        p = rec["profile"]
        return {k: f"{p[k]}%" for k in ("rim", "mid", "three")}
    shots = rec["shots"]
    n = len(shots) or 1
    three = sum(is_three(s) for s in shots)
    rim = sum(not is_three(s) and math.hypot(s["x"] - 25, s["y"]) < 4 for s in shots)
    pct = lambda k: f"{round(100 * k / n)}%"
    return {"rim": pct(rim), "mid": pct(n - three - rim), "three": pct(three)}


def legend_subject(rec, n, reveal=None):
    e, st = rec["entry"], rec["stats"]
    from legends import decade
    shots = sorted(rec["shots"], key=lambda s: (s["date"], not s["made"]))
    if e["mode"] == "season":
        pr = profile(rec)
        chips = [("PPG", f"{e['ppg']:.1f}", True), ("0-3 FT", pr["rim"], False),
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
