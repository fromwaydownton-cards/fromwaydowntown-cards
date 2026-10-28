"""Vertical 60+ second videos for the shot charts, Guess the Player and the
weekly MVP ladder. Same look as the leaders video (video_common).

python3 video_more.py shots YYYYMMDD [out.mp4]
python3 video_more.py guess YYYYMMDD [out.mp4]
python3 video_more.py mvp START END [out.mp4]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from mvp import ladder
from night_card import (BAR, BAR_EDGE, BOLD, HANDLE, HIGHLIGHT, INK, LIGHT, MUTED, NUM, ROOT, F,
                        fit, headshot_circle, ring_color)
from shot_card import DEPTH, HOOP_FROM_BASELINE, MAKE, MISS, court, splits, tag_threes
from shot_card import render as render_shot_card
from video_common import (H, W, alpha_text, back, ctext, draw_result, ease, encode, game_result,
                          ring_img, scaled)
from weekly_cards import guess as render_guess_card
from weekly_cards import mvp as render_mvp_card

COURT_W = 960
COURT_X = (W - COURT_W) // 2


# ---------- shared bits ----------------------------------------------------

def sprite(made, size):
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if made:
        d.ellipse((6, 6, s - 6, s - 6), fill=MAKE + (255,), outline=(255, 255, 255, 255), width=10)
    else:
        q = s * 0.22
        d.line((q, q, s - q, s - q), fill=MISS + (255,), width=s // 7)
        d.line((q, s - q, s - q, q), fill=MISS + (255,), width=s // 7)
    return im.resize((size, size), Image.LANCZOS)


SPR = {True: sprite(True, 34), False: sprite(False, 34)}


def shot_xy(s, y0):
    scale = COURT_W / 50.0
    x = max(0.6, min(49.4, s["x"]))
    y = min(DEPTH - HOOP_FROM_BASELINE - 0.6, max(-4.5, s["y"]))
    return COURT_X + x * scale, y0 + (y + HOOP_FROM_BASELINE) * scale


class Court:
    """Empty court once; shots drawn on top as they appear."""
    def __init__(self, frame_color):
        self.base = court([], COURT_W, dot=0)
        self.frame_color = frame_color

    def draw(self, img, y0, shots, shown, t_since_last, a=1.0):
        if a <= 0:
            return
        d = ImageDraw.Draw(img)
        h = self.base.height
        d.rounded_rectangle((COURT_X - 7, y0 - 7, COURT_X + COURT_W + 7, y0 + h + 7), radius=12,
                            fill=self.frame_color)
        base = self.base.copy()
        if a < 1:
            base.putalpha(int(255 * a))
        img.alpha_composite(base, (COURT_X, y0))
        order = sorted(range(shown), key=lambda i: shots[i]["made"])  # misses under makes
        for i in order:
            s = shots[i]
            x, y = shot_xy(s, y0)
            sp = SPR[s["made"]]
            if i == shown - 1 and t_since_last < 0.25:
                sp = scaled(sp, 0.4 + 0.6 * back(t_since_last / 0.25) * 1.15)
            img.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))


def live_counter(img, y, shots, shown, a=1.0):
    seen = shots[:shown]
    made = sum(s["made"] for s in seen)
    t3 = [s for s in seen if s.get("three")]
    txt = f"FG {made}-{len(seen)}     3PT {sum(s['made'] for s in t3)}-{len(t3)}"
    alpha_text(img, W / 2, y, txt, F(NUM, 54), INK, a)


def stat_bar(d, y, items, a=1.0):
    if a <= 0:
        return
    x0, w, h = 60, W - 120, 150
    d.rounded_rectangle((x0, y, x0 + w, y + h), radius=10, fill=BAR, outline=BAR_EDGE, width=6)
    col = (w - 20) / len(items)
    for i, (lab, val, hot) in enumerate(items):
        c = x0 + 10 + col * i + col / 2
        ctext(d, c, y + 14, str(val), F(NUM, 64), HIGHLIGHT if hot else (255, 255, 255))
        ctext(d, c, y + 104, lab, F(BOLD, 24), HIGHLIGHT if hot else LIGHT)


def zone_chips(d, y, sp):
    w = (W - 120 - 24) / 3
    for j, z in enumerate(("PAINT", "MID", "3PT")):
        m, at = sp[z]
        x = 60 + j * (w + 12)
        d.rounded_rectangle((x, y, x + w, y + 104), radius=10, fill=(244, 245, 247))
        ctext(d, x + w / 2, y + 10, f"{m}-{at}  {round(100 * m / at) if at else 0}%", F(NUM, 40), INK)
        ctext(d, x + w / 2, y + 64, "MIDRANGE" if z == "MID" else z, F(BOLD, 22), MUTED)


def player_header(img, y, p, color, label, result, t, logo=True):
    """Small headshot + rank label + name + opponent/score."""
    a = ease(t / 0.5)
    r = 105
    cx, cy = 60 + r, y + r
    disc, rg = headshot_circle(p, r), ring_img(r, color, 9)
    s = 0.6 + 0.4 * back(t / 0.5)
    disc, rg = scaled(disc, s), scaled(rg, s)
    img.alpha_composite(disc, (int(cx - disc.width / 2), int(cy - disc.height / 2)))
    img.alpha_composite(rg, (int(cx - rg.width / 2), int(cy - rg.height / 2)))
    tx = cx + r + 30
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    al = int(255 * a)
    ld.text((tx, y + 6), label, font=F(BOLD, 30), fill=color + (al,))
    lf = ROOT / "data" / "logos" / f"{p['team']}.png"
    nx = tx
    if logo and lf.exists():
        lg = Image.open(lf).convert("RGBA")
        lg.thumbnail((56, 56), Image.LANCZOS)
        lg.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
        layer.alpha_composite(lg, (int(tx), int(y + 52)))
        nx = tx + 66
    nf = fit(ld, p["name"].upper(), NUM, 58, W - 50 - nx)
    ld.text((nx, y + 46), p["name"].upper(), font=nf, fill=INK + (al,))
    img.alpha_composite(layer)
    if result:
        res_w = W - 50 - tx
        # left-aligned result line under the name
        draw_result(img, tx + res_w / 2 - 40, y + 128, result, a, size=36)


def outro_card(img, t, card, line):
    a = ease(t / 0.6)
    c = card.copy()
    c.putalpha(int(255 * a))
    img.alpha_composite(c, ((W - c.width) // 2, 260))
    alpha_text(img, W / 2, 1520, line, F(NUM, 44), INK, ease((t - 0.6) / 0.5))


def title_intro(img, t, kicker, big1, big2, sub):
    d = ImageDraw.Draw(img)
    alpha_text(img, W / 2 - (1 - ease(t / 0.5)) * 200, 560, kicker, F(NUM, 60), MUTED, ease(t / 0.5))
    s = back((t - 0.3) / 0.6)
    if s > 0:
        tf = F(NUM, max(10, int(140 * s)))
        ctext(d, W / 2, 680 + (140 - tf.size) / 2, big1, tf, INK)
        ctext(d, W / 2, 830 + (140 - tf.size) / 2, big2, tf, INK)
    alpha_text(img, W / 2, 1040, sub, F(BOLD, 40), INK, ease((t - 1.0) / 0.5))
    alpha_text(img, W / 2, 1130, HANDLE, F(BOLD, 34), MUTED, ease((t - 1.3) / 0.5))


# ---------- shot charts (top 3 scorers) ------------------------------------

def shots_video(date, out):
    night = json.loads((ROOT / "data" / "nights" / f"{date}.json").read_text())
    data = json.loads((ROOT / "data" / "shots" / f"{date}.json").read_text())
    rows = sorted(data.values(), key=lambda v: (-v["player"]["pts"], v["player"]["fga"]))[:3]
    for v in rows:
        tag_threes(v["shots"], v["player"]["tpm"], v["player"]["tpa"])
    card_f = Path(out).with_suffix(".card.jpg")
    render_shot_card(data, date, card_f)
    card = Image.open(card_f).convert("RGBA").resize((1000, 1250), Image.LANCZOS)
    card_f.unlink(missing_ok=True)
    segs = []
    for i, v in enumerate(rows):
        p = v["player"]
        nf = next((x for x in night["players"] if x["id"] == p["id"]), p)
        color = ring_color(p["team"])
        segs.append(dict(v=v, p=p, color=color, court=Court(color), res=game_result(night, nf),
                         label=f"#{i + 1} SCORER", sp=splits(v["shots"])))
    INTRO, SEG, OUTRO = 3.0, 18.0, 6.0
    SHOW0, SHOW1 = 1.2, 12.0
    total = INTRO + SEG * len(segs) + OUTRO
    dstr = datetime.strptime(date, "%Y%m%d").strftime("%b %-d, %Y").upper()

    def frame(img, t):
        if t < INTRO:
            title_intro(img, t, dstr, "SHOT", "CHARTS", "THE NIGHT'S TOP 3 SCORERS")
            return
        if t >= INTRO + SEG * len(segs):
            outro_card(img, t - INTRO - SEG * len(segs), card, "FOLLOW FOR THE LEADERS EVERY NIGHT")
            return
        k = int((t - INTRO) // SEG)
        st = t - INTRO - k * SEG
        sg = segs[k]
        shots = sg["v"]["shots"]
        n = len(shots)
        player_header(img, 300, sg["p"], sg["color"], sg["label"], sg["res"], st)
        prog = (st - SHOW0) / (SHOW1 - SHOW0)
        shown = 0 if st < SHOW0 else min(n, int(prog * n) + 1)
        since = ((st - SHOW0) - (shown - 1) * (SHOW1 - SHOW0) / max(n, 1)) if shown else 9
        sg["court"].draw(img, 560, shots, shown, since, ease((st - 0.6) / 0.5))
        y_after = 560 + sg["court"].base.height + 30
        d = ImageDraw.Draw(img)
        if st < SHOW1 + 0.6:
            live_counter(img, y_after + 10, shots, shown, ease((st - SHOW0) / 0.4))
        else:
            v, p, sp = sg["v"], sg["p"], sg["sp"]
            made = sum(s["made"] for s in shots)
            stat_bar(d, y_after, [("PTS", p["pts"], True), ("FG", f"{made}-{n}", False),
                                  ("3PT", f"{sp['3PT'][0]}-{sp['3PT'][1]}", False),
                                  ("FT", f"{v['ft_made']}-{v['ft_att']}", False)])
            if st > SHOW1 + 1.4:
                zone_chips(d, y_after + 168, sp)
        if st > SEG - 0.35:
            img.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, int(255 * (st - (SEG - 0.35)) / 0.35))))

    return encode(out, total, frame, seed=2)


# ---------- guess the player ------------------------------------------------

def guess_video(date, out):
    saved = json.loads((ROOT / "data" / "guess" / f"{date}.json").read_text())
    night = json.loads((ROOT / "data" / "nights" / f"{date}.json").read_text())
    p, v = saved["pick"], saved["shots"]
    shots = v["shots"]
    tag_threes(shots, p["tpm"], p["tpa"])
    sp = splits(shots)
    res = game_result(night, p)
    hints = []
    if p.get("normal_src") == "last season":
        hints.append(f"AVERAGED {p['normal']:g} PPG LAST SEASON")
    elif p.get("normal_src") == "rookie":
        hints.append("HE'S A ROOKIE")
    else:
        hints.append(f"AVERAGING {p['normal']:g} PPG THIS SEASON")
    if res:
        hints.append(f"HIS TEAM {'WON' if res[2] else 'LOST'} BY {abs(res[3] - res[4])}")
    ct = Court(INK)
    n = len(shots)
    INTRO, SHOW0, SHOW1, HINTS, COUNT, END = 3.0, 4.0, 34.0, 35.0, 46.0, 56.0
    total = 62.0
    dstr = datetime.strptime(date, "%Y%m%d").strftime("%b %-d, %Y").upper()

    def mystery(img, t, y=300):
        r = 105
        cx, cy = 60 + r, y + r
        d = ImageDraw.Draw(img)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(150, 154, 160))
        rg = ring_img(r, INK, 9)
        img.alpha_composite(rg, (int(cx - rg.width / 2), int(cy - rg.height / 2)))
        qf = F(NUM, 150)
        l, tp, rr, b = d.textbbox((0, 0), "?", font=qf)
        d.text((cx - (rr - l) / 2 - l, cy - (b - tp) / 2 - tp), "?", font=qf, fill=(255, 255, 255))
        d.text((cx + r + 30, y + 10), "GUESS THE PLAYER", font=F(NUM, 56), fill=INK)
        d.text((cx + r + 30, y + 86), f"{dstr}  ·  {p['pts']} POINTS", font=F(BOLD, 32), fill=MUTED)

    def frame(img, t):
        if t < INTRO:
            title_intro(img, t, dstr, "GUESS THE", "PLAYER", "WHO PUT UP THIS SHOT CHART?")
            return
        mystery(img, t)
        st = t - INTRO
        prog = (t - SHOW0) / (SHOW1 - SHOW0)
        shown = 0 if t < SHOW0 else min(n, int(prog * n) + 1)
        since = ((t - SHOW0) - (shown - 1) * (SHOW1 - SHOW0) / max(n, 1)) if shown else 9
        ct.draw(img, 560, shots, shown, since, ease(st / 0.5))
        y_after = 560 + ct.base.height + 30
        d = ImageDraw.Draw(img)
        if t < SHOW1 + 0.6:
            live_counter(img, y_after + 10, shots, shown, ease((t - SHOW0) / 0.4))
            return
        made = sum(s["made"] for s in shots)
        stat_bar(d, y_after, [("PTS", p["pts"], True), ("FG", f"{made}-{n}", False),
                              ("3PT", f"{sp['3PT'][0]}-{sp['3PT'][1]}", False),
                              ("FT", f"{v['ft_made']}-{v['ft_att']}", False)])
        hy = y_after + 175
        for i, h in enumerate(hints):
            a = ease((t - HINTS - i * 3) / 0.5)
            if a <= 0:
                continue
            txt = "HINT: " + h
            hf = F(BOLD, 34)
            hw = d.textlength(txt, font=hf) + 60
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.rounded_rectangle((W / 2 - hw / 2, hy, W / 2 + hw / 2, hy + 62), radius=31,
                                 fill=INK + (int(255 * a),))
            ld.text((W / 2 - hw / 2 + 30, hy + 12), txt, font=hf, fill=HIGHLIGHT + (int(255 * a),))
            img.alpha_composite(layer)
            hy += 76
        if t >= COUNT and t < END:
            left = int(END - t) + 1 if END - t > 0 else 0
            frac = (t - COUNT) % 1
            s = 1.25 - 0.25 * ease(frac / 0.3)
            d = ImageDraw.Draw(img)
            ctext(d, W / 2, hy + 6, "LOCK IN YOUR GUESS", F(NUM, 44), INK)
            nf = F(NUM, int(120 * s))
            ctext(d, W / 2, hy + 60 + (120 - nf.size) / 2, str(min(left, 10)), nf, HIGHLIGHT if left <= 3 else INK)
        elif t >= END:
            a = ease((t - END) / 0.5)
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.rounded_rectangle((60, hy, W - 60, hy + 170), radius=18, fill=BAR + (int(255 * a),))
            img.alpha_composite(layer)
            alpha_text(img, W / 2, hy + 22, "DROP YOUR GUESS IN THE COMMENTS", F(NUM, 46), (255, 255, 255), a)
            alpha_text(img, W / 2, hy + 100, "ANSWER IN TONIGHT'S POST", F(BOLD, 34), HIGHLIGHT, a)

    return encode(out, total, frame, seed=3)


# ---------- MVP ladder countdown -------------------------------------------

def mvp_video(start, end, out):
    st_f = ROOT / "data" / "standings.json"
    standings = json.loads(st_f.read_text()) if st_f.exists() else {}
    nights = [json.loads(f.read_text()) for f in sorted((ROOT / "data" / "nights").glob("*.json"))
              if start <= f.stem <= end]
    rows = ladder(nights, 5, standings)
    card_f = Path(out).with_suffix(".card.jpg")
    render_mvp_card(start, end, card_f, standings)
    card = Image.open(card_f).convert("RGBA").resize((1000, 1250), Image.LANCZOS)
    card_f.unlink(missing_ok=True)
    s0, e0 = datetime.strptime(start, "%Y%m%d"), datetime.strptime(end, "%Y%m%d")
    wk = f"WEEK OF {s0.strftime('%b %-d').upper()}–{e0.strftime('%b %-d').upper()}"
    order = list(reversed(list(enumerate(rows, 1))))       # count down 5 -> 1
    pre = []
    for rank, r in order:
        pre.append(dict(rank=rank, r=r, color=ring_color(r["team"]), disc=headshot_circle(r, 260),
                        ring=ring_img(260, ring_color(r["team"]))))
    INTRO, SEG, OUTRO = 3.0, 11.0, 5.0
    total = INTRO + SEG * len(pre) + OUTRO

    def ordinal(n):
        return f"{n}{'TH' if 10 <= n % 100 <= 20 else {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH')}"

    def frame(img, t):
        if t < INTRO:
            title_intro(img, t, wk, "MVP", "LADDER", "COUNTING DOWN THE TOP 5")
            return
        if t >= INTRO + SEG * len(pre):
            outro_card(img, t - INTRO - SEG * len(pre), card, "WHO'S TOO HIGH? WHO'S MISSING?")
            return
        k = int((t - INTRO) // SEG)
        st = t - INTRO - k * SEG
        s = pre[k]
        r = s["r"]
        d = ImageDraw.Draw(img)
        # big rank
        rs = back(st / 0.5)
        rf = F(NUM, max(10, int(150 * rs)))
        d.rounded_rectangle((W / 2 - 110, 270, W / 2 + 110, 470), radius=24, fill=BAR)
        ctext(d, W / 2, 285 + (150 - rf.size) / 2, str(s["rank"]), rf, HIGHLIGHT if s["rank"] == 1 else (255, 255, 255))
        # headshot
        sc = (0.6 + 0.4 * back((st - 0.3) / 0.6)) * (1 + 0.05 * max(0, st - 0.9) / SEG)
        if st > 0.3:
            disc, rg = scaled(s["disc"], sc), scaled(s["ring"], sc)
            img.alpha_composite(disc, (int(W / 2 - disc.width / 2), int(790 - disc.height / 2)))
            img.alpha_composite(rg, (int(W / 2 - rg.width / 2), int(790 - rg.height / 2)))
        d = ImageDraw.Draw(img)
        a = ease((st - 0.8) / 0.5)
        name = r["name"].upper()
        nf = fit(d, name, NUM, 74, W - 200)
        lf = ROOT / "data" / "logos" / f"{r['team']}.png"
        logo = None
        if lf.exists():
            logo = Image.open(lf).convert("RGBA")
            logo.thumbnail((70, 70), Image.LANCZOS)
        total_w = (logo.width + 18 if logo else 0) + d.textlength(name, font=nf)
        nx = W / 2 - total_w / 2
        if a > 0:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            if logo:
                lg = logo.copy()
                lg.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
                layer.alpha_composite(lg, (int(nx), 1090))
                nx += logo.width + 18
            ld.text((nx, 1080 + (1 - a) * 30), name, font=nf, fill=INK + (int(255 * a),))
            img.alpha_composite(layer)
        rec = (f"TEAM {r['team_w']}-{r['team_l']}, {ordinal(r['seed'])} IN {r['conf'].upper()}"
               if r.get("seed") else f"{r['w']}-{r['l']} THIS WEEK")
        alpha_text(img, W / 2, 1175, f"{r['gp']} GAMES  ·  {rec}", F(BOLD, 36), s["color"], ease((st - 1.2) / 0.5))
        d = ImageDraw.Draw(img)
        if st > 1.6:
            k2 = ease((st - 1.8) / 1.5)
            pulse = 1 + 0.15 * __import__("math").sin(3.14159 * min(1, max(0, (st - 3.4) / 0.5)))
            x0, y0, w, h = 60, 1245, W - 120, 160
            d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=10, fill=BAR, outline=BAR_EDGE, width=6)
            items = [("PPG", r["ppg"], "{:.1f}"), ("RPG", r["rpg"], "{:.1f}"), ("APG", r["apg"], "{:.1f}"),
                     ("ON/OFF", r["onoff"], "{:+.0f}"), ("MVP SCORE", r["score"], "{:.1f}")]
            col = (w - 20) / 5
            for i, (lab, val, fmt) in enumerate(items):
                c = x0 + 10 + col * i + col / 2
                hot = lab == "MVP SCORE"
                vf = F(NUM, int(58 * (pulse if hot else 1)))
                ctext(d, c, y0 + 18 - (vf.size - 58) / 2, fmt.format(val * k2), vf, HIGHLIGHT if hot else (255, 255, 255))
                ctext(d, c, y0 + 108, lab, F(BOLD, 22), HIGHLIGHT if hot else LIGHT)
        alpha_text(img, W / 2, 1440, f"BEST GAME THIS WEEK: {r['best']} PTS", F(BOLD, 34), INK, ease((st - 4.0) / 0.5))
        if st > SEG - 0.35:
            img.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, int(255 * (st - (SEG - 0.35)) / 0.35))))

    return encode(out, total, frame, seed=4)


if __name__ == "__main__":
    kind = sys.argv[1]
    if kind == "mvp":
        out = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / "media" / f"{sys.argv[2]}-{sys.argv[3]}-mvp.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"{mvp_video(sys.argv[2], sys.argv[3], out):.0f}s", out)
    else:
        out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "media" / f"{sys.argv[2]}-{kind}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        fn = shots_video if kind == "shots" else guess_video
        print(f"{fn(sys.argv[2], out):.0f}s", out)
