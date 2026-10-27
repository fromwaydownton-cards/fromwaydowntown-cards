"""Guess-the-player shot chart and weekly MVP ladder, in the house style.

python3 weekly_cards.py guess YYYYMMDD [out]          (top scorer of that night, name hidden)
python3 weekly_cards.py mvp START END [out]           (week ladder, top 5)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from mvp import ladder
from night_card import (BAR, BAR_EDGE, BG, BOLD, HANDLE, HIGHLIGHT, INK, LIGHT, MUTED, NUM,
                        ROOT, F, centered, fit, headshot_circle, ring_color)
from shot_card import DEPTH, MAKE, MISS, court, splits, tag_threes

W, H = 1080, 1350


def header(d, title, sub):
    d.text((36, 26), title, font=F(NUM, 44), fill=INK)
    d.text((38, 86), sub, font=F(BOLD, 18), fill=MUTED)
    hf = F(BOLD, 20)
    d.text((W - 36 - d.textlength(HANDLE, font=hf), 34), HANDLE, font=hf, fill=MUTED)


def bar(d, x, y, w, items, h=82, vsize=32):
    d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=BAR, outline=BAR_EDGE, width=4)
    col = (w - 16) / len(items)
    vf, lf = F(NUM, vsize), F(BOLD, 12)
    for i, (lab, val, hot) in enumerate(items):
        c = x + 8 + col * i + col / 2
        centered(d, c, y + 10, str(val), vf, HIGHLIGHT if hot else (255, 255, 255))
        centered(d, c, y + h - 26, lab, lf, HIGHLIGHT if hot else LIGHT)


def ring(img, cx, cy, r, color, width=7):
    big = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((2 * (cx - r), 2 * (cy - r), 2 * (cx + r), 2 * (cy + r)),
                                outline=color + (255,), width=width * 2)
    img.alpha_composite(big.resize((W, H), Image.LANCZOS))


def guess(date, out):
    saved = json.loads((ROOT / "data" / "guess" / f"{date}.json").read_text())
    night = json.loads((ROOT / "data" / "nights" / f"{date}.json").read_text())
    v = saved["shots"]
    p, shots = saved["pick"], v["shots"]
    tag_threes(shots, p["tpm"], p["tpa"])
    g = next(g for g in night["games"] if g["id"] == p["game"])
    mine, theirs = ((g["home_score"], g["away_score"]) if g["home"] == p["team"]
                    else (g["away_score"], g["home_score"]))
    hints = [f"HIS TEAM {'WON' if mine > theirs else 'LOST'} BY {abs(mine - theirs)}"]
    if p.get("normal_src") == "last season":
        hints.insert(0, f"AVERAGED {p['normal']:g} PPG LAST SEASON")
    elif p.get("normal_src") == "rookie":
        hints.insert(0, "ROOKIE")
    else:
        hints.insert(0, f"AVERAGING {p['normal']:g} PPG THIS SEASON")

    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    header(d, "GUESS THE PLAYER", datetime.strptime(date, "%Y%m%d").strftime("%b %-d, %Y").upper()
           + "  ·  WHO PUT UP THIS SHOT CHART?")
    cw = W - 72
    cx0, cy0 = 36, 132
    ch = int(DEPTH * cw / 50)
    d.rounded_rectangle((cx0 - 6, cy0 - 6, cx0 + cw + 6, cy0 + ch + 6), radius=10, fill=INK)
    img.alpha_composite(court(shots, cw, dot=15), (cx0, cy0))
    d = ImageDraw.Draw(img)
    # legend on the court frame
    lx, ly = cx0 + cw - 230, cy0 + ch + 14
    d.ellipse((lx, ly + 3, lx + 16, ly + 19), fill=MAKE, outline=(255, 255, 255), width=2)
    d.text((lx + 24, ly), "MADE", font=F(BOLD, 16), fill=INK)
    mx = lx + 105
    d.line((mx + 2, ly + 5, mx + 14, ly + 17), fill=MISS, width=4)
    d.line((mx + 2, ly + 17, mx + 14, ly + 5), fill=MISS, width=4)
    d.text((mx + 24, ly), "MISSED", font=F(BOLD, 16), fill=INK)

    # mystery player
    r = 100
    hx, hy = 36 + r + 8, cy0 + ch + 70 + r
    d.ellipse((hx - r, hy - r, hx + r, hy + r), fill=(150, 154, 160))
    ring(img, hx, hy, r, INK)
    d = ImageDraw.Draw(img)
    qf = F(NUM, 130)
    l, t, rr, b = d.textbbox((0, 0), "?", font=qf)
    d.text((hx - (rr - l) / 2 - l, hy - (b - t) / 2 - t), "?", font=qf, fill=(255, 255, 255))
    px = hx + r + 30
    pw = W - 36 - px
    made = sum(s["made"] for s in shots)
    sp = splits(shots)
    top = hy - r + 4
    bar(d, px, top, pw, [("PTS", p["pts"], True), ("FG", f"{made}-{len(shots)}", False),
                         ("3PT", f"{sp['3PT'][0]}-{sp['3PT'][1]}", False),
                         ("FT", f"{v['ft_made']}-{v['ft_att']}", False)])
    zy = top + 94
    zw = (pw - 16) / 3
    for j, z in enumerate(("PAINT", "MID", "3PT")):
        m, a = sp[z]
        zx = px + j * (zw + 8)
        d.rounded_rectangle((zx, zy, zx + zw, zy + 58), radius=6, fill=(244, 245, 247))
        centered(d, zx + zw / 2, zy + 6, f"{m}-{a}  {round(100 * m / a) if a else 0}%", F(NUM, 22), INK)
        centered(d, zx + zw / 2, zy + 36, "MIDRANGE" if z == "MID" else z, F(BOLD, 13), MUTED)
    # hint + call to action
    hf = F(BOLD, 19)
    hy2 = zy + 72
    for hint in hints:
        txt = "HINT: " + hint
        hw = d.textlength(txt, font=hf) + 34
        d.rounded_rectangle((px, hy2, px + hw, hy2 + 34), radius=17, fill=INK)
        d.text((px + 17, hy2 + 6), txt, font=hf, fill=HIGHLIGHT)
        hy2 += 42
    cta_y = max(hy + r + 70, hy2 + 40)
    d.rounded_rectangle((36, cta_y - 18, W - 36, cta_y + 96), radius=14, fill=BAR)
    centered(d, W / 2, cta_y - 2, "DROP YOUR GUESS IN THE COMMENTS", F(NUM, 40), (255, 255, 255))
    centered(d, W / 2, cta_y + 56, "ANSWER IN TONIGHT'S POST", F(BOLD, 20), HIGHLIGHT)
    img.convert("RGB").save(out, "JPEG", quality=93, subsampling=0)
    return p


def ordinal(n):
    return f"{n}{'TH' if 10 <= n % 100 <= 20 else {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH')}"


def mvp(start, end, out, standings=None):
    if standings is None:
        f = ROOT / "data" / "standings.json"
        standings = json.loads(f.read_text()) if f.exists() else {}
    nights = []
    for f in sorted((ROOT / "data" / "nights").glob("*.json")):
        if start <= f.stem <= end:
            nights.append(json.loads(f.read_text()))
    rows = ladder(nights, 5, standings)
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    s = datetime.strptime(start, "%Y%m%d"); e = datetime.strptime(end, "%Y%m%d")
    header(d, "MVP LADDER", f"WEEK OF {s.strftime('%b %-d').upper()}–{e.strftime('%-d') if s.month == e.month else e.strftime('%b %-d').upper()}"
           "  ·  GAME SCORE + ON/OFF IMPACT + TEAM RECORD")
    top, row_h = 132, 228
    for i, rw in enumerate(rows):
        y = top + i * row_h
        color = ring_color(rw["team"])
        if i % 2 == 0:
            d.rounded_rectangle((24, y + 4, W - 24, y + row_h - 8), radius=14, fill=(246, 247, 249))
        # rank
        d.rounded_rectangle((44, y + 54, 134, y + 154), radius=12, fill=BAR)
        centered(d, 89, y + 60, str(i + 1), F(NUM, 66), HIGHLIGHT if i == 0 else (255, 255, 255))
        # headshot
        r = 88
        hx, hy = 154 + r + 10, y + row_h // 2 - 2
        img.alpha_composite(headshot_circle(rw, r), (hx - r, hy - r))
        ring(img, hx, hy, r, color)
        d = ImageDraw.Draw(img)
        # name line with logo
        nx = hx + r + 30
        nw = W - 48 - nx
        logo_f = ROOT / "data" / "logos" / f"{rw['team']}.png"
        lx = nx
        if logo_f.exists():
            lg = Image.open(logo_f).convert("RGBA"); lg.thumbnail((40, 40), Image.LANCZOS)
            img.alpha_composite(lg, (int(nx), int(y + 34)))
            d = ImageDraw.Draw(img)
            lx = nx + 50
        nf = fit(d, rw["name"].upper(), NUM, 38, W - 48 - lx)
        d.text((lx, y + 26), rw["name"].upper(), font=nf, fill=INK)
        rec = (f"{rw['team_w']}-{rw['team_l']}, {ordinal(rw['seed'])} IN {rw['conf'].upper()}"
               if rw.get("seed") else f"{rw['w']}-{rw['l']} THIS WEEK")
        meta = f"{rw['gp']} GAMES  ·  TEAM {rec}  ·  BEST {rw['best']} PTS"
        d.text((nx, y + 78), meta, font=F(BOLD, 16), fill=color if color != INK else MUTED)
        bar(d, nx, y + 110, nw, [("PPG", f"{rw['ppg']:.1f}", False), ("RPG", f"{rw['rpg']:.1f}", False),
                                 ("APG", f"{rw['apg']:.1f}", False),
                                 ("ON/OFF", f"{rw['onoff']:+.0f}", False),
                                 ("MVP SCORE", f"{rw['score']:.1f}", True)], h=78, vsize=30)
    centered(d, W / 2, H - 62, "WHO'S TOO HIGH? WHO'S MISSING? TELL US BELOW", F(BOLD, 22), INK)
    img.convert("RGB").save(out, "JPEG", quality=93, subsampling=0)
    return rows


if __name__ == "__main__":
    kind = sys.argv[1]
    if kind == "guess":
        out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "cards" / "guess" / f"{sys.argv[2]}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        print("answer:", guess(sys.argv[2], out)["name"], out)
    else:
        out = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / "cards" / "mvp" / f"{sys.argv[2]}-{sys.argv[3]}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        print([r["name"] for r in mvp(sys.argv[2], sys.argv[3], out)], out)
