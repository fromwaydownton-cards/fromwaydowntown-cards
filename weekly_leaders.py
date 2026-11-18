"""Weekly per-game leaders (Mon-Sun), in the house style (1080x1350).

Categories: PPG, RPG, APG, SPG, BPG, 3PM per game. Minimum MIN_GP games that
week. Ties go to the higher total, then fewer games. Shows the top 3 in each.

python3 weekly_leaders.py START END [out.jpg] [slides]     (needs data/nights/*.json)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from night_card import (BAR, BAR_EDGE, BG, BOLD, HANDLE, HIGHLIGHT, INK, LIGHT, MUTED, NUM, PANEL, ROOT,
                        F, centered, fit, headshot_circle, ring_color)

W, H = 1080, 1350
MIN_GP = 2
CATS = [("pts", "PPG", "POINTS"), ("reb", "RPG", "REBOUNDS"), ("ast", "APG", "ASSISTS"),
        ("stl", "SPG", "STEALS"), ("blk", "BPG", "BLOCKS"), ("tpm", "3PM", "THREES MADE")]


def nights_between(start, end):
    out = []
    for f in sorted((ROOT / "data" / "nights").glob("*.json")):
        if start <= f.stem <= end:
            out.append(json.loads(f.read_text()))
    return out


def averages(nights):
    final = {g["id"] for n in nights for g in n["games"] if g["final"]}
    agg = {}
    for n in nights:
        for p in n["players"]:
            if p["game"] not in final:
                continue
            a = agg.setdefault(p["id"], {"id": p["id"], "name": p["name"], "team": p["team"],
                                         "headshot": p["headshot"], "gp": 0,
                                         **{k: 0 for k, *_ in CATS}})
            a["team"] = p["team"]
            a["gp"] += 1
            for k, *_ in CATS:
                a[k] += p.get(k, 0)
    return [a for a in agg.values() if a["gp"] >= MIN_GP]


def leaders(nights, top=3):
    rows = averages(nights)
    out = {}
    for k, *_ in CATS:
        ranked = sorted(rows, key=lambda a: (-a[k] / a["gp"], -a[k], a["gp"]))[:top]
        out[k] = [dict(a, avg=a[k] / a["gp"]) for a in ranked]
    return out


def week_label(start, end):
    s, e = datetime.strptime(start, "%Y%m%d"), datetime.strptime(end, "%Y%m%d")
    return f"{s.strftime('%b %-d')}-{e.strftime('%-d') if s.month == e.month else e.strftime('%b %-d')}"


def render(start, end, out):
    L = leaders(nights_between(start, end))
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    d.text((36, 22), "WEEKLY LEADERS", font=F(NUM, 50), fill=INK)
    d.text((38, 88), f"WEEK OF {week_label(start, end).upper()}  ·  PER GAME  ·  MIN {MIN_GP} GAMES",
           font=F(BOLD, 18), fill=MUTED)
    hf = F(BOLD, 20)
    d.text((W - 36 - d.textlength(HANDLE, font=hf), 34), HANDLE, font=hf, fill=MUTED)
    top, row_h = 128, 200
    for i, (k, unit, label) in enumerate(CATS):
        y = top + i * row_h
        if not L.get(k):
            continue
        p = L[k][0]
        if i % 2 == 0:
            d.rounded_rectangle((24, y + 4, W - 24, y + row_h - 6), radius=14, fill=PANEL)
        color = ring_color(p["team"])
        r = 72
        hx, hy = 44 + r, y + row_h // 2
        img.alpha_composite(headshot_circle(p, r), (hx - r, hy - r))
        big = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
        ImageDraw.Draw(big).ellipse((2 * (hx - r), 2 * (hy - r), 2 * (hx + r), 2 * (hy + r)),
                                    outline=color + (255,), width=12)
        img.alpha_composite(big.resize((W, H), Image.LANCZOS))
        d = ImageDraw.Draw(img)
        nx = hx + r + 26
        d.text((nx, y + 22), label, font=F(BOLD, 17), fill=HIGHLIGHT)
        logo_f = ROOT / "data" / "logos" / f"{p['team']}.png"
        lx = nx
        if logo_f.exists():
            lg = Image.open(logo_f).convert("RGBA")
            lg.thumbnail((36, 36), Image.LANCZOS)
            img.alpha_composite(lg, (int(nx), int(y + 52)))
            d = ImageDraw.Draw(img)
            lx = nx + 44
        # big average box on the right
        bw = 210
        bx = W - 44 - bw
        nf = fit(d, p["name"].upper(), NUM, 36, bx - lx - 16)
        d.text((lx, y + 48), p["name"].upper(), font=nf, fill=INK)
        d.text((nx, y + 100), f"{p['gp']} GAMES  ·  {p[k]} TOTAL", font=F(BOLD, 16), fill=MUTED)
        rest = "   ".join(f"{j}. {q['name'].split()[-1].upper()} {q['avg']:.1f}" for j, q in enumerate(L[k][1:], 2))
        if rest:
            rf = fit(d, rest, BOLD, 16, bx - nx - 16)
            d.text((nx, y + 132), rest, font=rf, fill=LIGHT)
        d.rounded_rectangle((bx, y + 30, bx + bw, y + row_h - 36), radius=10, fill=BAR, outline=BAR_EDGE, width=3)
        centered(d, bx + bw / 2, y + 36, f"{p['avg']:.1f}", F(NUM, 64), HIGHLIGHT)
        centered(d, bx + bw / 2, y + row_h - 66, unit, F(BOLD, 18), LIGHT)
    img.convert("RGB").save(out, "JPEG", quality=93, subsampling=0)
    return L


# ---------- carousel (Nov 2026): one 1080x1350 slide per stat ---------------
# Instagram/Facebook get these as a swipeable carousel; TikTok gets the video.

def render_slides(start, end, out_dir, stem):
    """Write stem-1.jpg ... stem-6.jpg (one per category); returns the paths."""
    from video_common import ring_img
    L = leaders(nights_between(start, end), top=5)
    cats = [c for c in CATS if L.get(c[0])]
    wk = "WEEK OF " + week_label(start, end).upper()
    out_dir = Path(out_dir)
    paths = []
    for i, (k, unit, label) in enumerate(cats):
        p = L[k][0]
        img = Image.new("RGBA", (W, H), BG + (255,))
        d = ImageDraw.Draw(img)
        # header: series name, week, handle, page dots
        d.text((48, 40), "WEEKLY LEADERS", font=F(NUM, 34), fill=HIGHLIGHT)
        d.text((48, 86), f"{wk}  ·  PER GAME  ·  MIN {MIN_GP} GAMES", font=F(BOLD, 20), fill=MUTED)
        hf = F(BOLD, 20)
        d.text((W - 48 - d.textlength(HANDLE, font=hf), 50), HANDLE, font=hf, fill=MUTED)
        n, gap, wd = len(cats), 10, 34
        x = W - 48 - (n * wd + (n - 1) * gap)
        for j in range(n):
            d.rounded_rectangle((x, 92, x + wd, 100), radius=4, fill=HIGHLIGHT if j == i else BAR_EDGE)
            x += wd + gap
        centered(d, W / 2, 150, label, F(NUM, 88), INK)
        # leader
        r = 175
        cx, cy = W / 2, 455
        img.alpha_composite(headshot_circle(p, r), (int(cx - r), int(cy - r)))
        rg = ring_img(r, ring_color(p["team"]), 10)
        img.alpha_composite(rg, (int(cx - rg.width / 2), int(cy - rg.height / 2)))
        d = ImageDraw.Draw(img)
        name = p["name"].upper()
        nf = fit(d, name, NUM, 60, W - 200)
        logo = None
        lf = ROOT / "data" / "logos" / f"{p['team']}.png"
        if lf.exists():
            logo = Image.open(lf).convert("RGBA")
            logo.thumbnail((58, 58), Image.LANCZOS)
        tw = (logo.width + 14 if logo else 0) + d.textlength(name, font=nf)
        nx = W / 2 - tw / 2
        if logo:
            img.alpha_composite(logo, (int(nx), 668))
            nx += logo.width + 14
        d.text((nx, 656), name, font=nf, fill=INK)
        bf, uf = F(NUM, 150), F(NUM, 46)
        num = f"{p['avg']:.1f}"
        nw, uw = d.textlength(num, font=bf), d.textlength(unit, font=uf)
        x0 = W / 2 - (nw + 16 + uw) / 2
        d.text((x0, 712), num, font=bf, fill=HIGHLIGHT)
        d.text((x0 + nw + 16, 712 + 150 - 46 - 26), unit, font=uf, fill=LIGHT)
        centered(d, W / 2, 920, f"{p['gp']} GAMES  ·  {p[k]} TOTAL", F(BOLD, 26), MUTED)
        # 2-5
        y = 985
        for j, q in enumerate(L[k][1:5], 2):
            d.rounded_rectangle((70, y, W - 70, y + 58), radius=12, fill=PANEL)
            rf = F(NUM, 30)
            d.text((96, y + 9), str(j), font=rf, fill=MUTED)
            nm = f"{q['name'].upper()}  ({q['team']})"
            d.text((146, y + 14), nm, font=fit(d, nm, BOLD, 26, W - 70 - 146 - 140), fill=INK)
            val = f"{q['avg']:.1f}"
            d.text((W - 96 - d.textlength(val, font=rf), y + 9), val, font=rf, fill=INK)
            y += 66
        foot = "SWIPE FOR EVERY STAT  »" if i == 0 else ("WHO HAD THE BEST WEEK? COMMENT BELOW" if i == n - 1 else "")
        if foot:
            centered(d, W / 2, H - 58, foot, F(BOLD, 24), HIGHLIGHT if i == 0 else INK)
        f = out_dir / f"{stem}-{i + 1}.jpg"
        img.convert("RGB").save(f, "JPEG", quality=93, subsampling=0)
        paths.append(f)
    return paths


if __name__ == "__main__":
    start, end = sys.argv[1], sys.argv[2]
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "cards" / "weekly" / f"{start}-{end}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 4 and sys.argv[4] == "slides":
        print(render_slides(start, end, out.parent, out.stem))
        sys.exit()
    L = render(start, end, out)
    for k, rows in L.items():
        print(k, [(r["name"], round(r["avg"], 1), r["gp"]) for r in rows])
    print(out)
