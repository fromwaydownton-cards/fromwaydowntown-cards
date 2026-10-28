"""Animated 62-second vertical video (1080x1920) of the nightly leaders, for
TikTok / Reels / Shorts. Built from the same data and style as the graphic.

  0-3s    intro: date + NIGHT LEADERS
  3-48s   five leaders, 9s each: tag, headshot, name, stats counting up,
          the winning stat pulses yellow
  48-58s  final scores build row by row
  58-62s  the full leaders graphic + follow prompt

Key content stays inside the area apps leave clear (top ~170px and bottom
~380px are covered by app UI).

Usage: python3 video_leaders.py YYYYMMDD [out.mp4]
"""
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from video_common import draw_result, encode, game_result
from leaders import pick
from night_card import (BAR, BAR_EDGE, BG, BOLD, HANDLE, HIGHLIGHT, INK, LIGHT, MUTED, NUM,
                        ROOT, F, fit, headshot_circle, ring_color, text_color)
from night_card import render as render_card

W, H, FPS = 1080, 1920, 30
INTRO, SEG, SCORES, OUTRO = 3.0, 9.0, 10.0, 4.0
ORDER = ["pts", "reb", "ast", "three", "worst_pm"]
TAGS = {"pts": "MOST POINTS", "reb": "MOST REBOUNDS", "ast": "MOST ASSISTS",
        "three": "BEST 3PT%", "worst_pm": "WORST +/-"}
HOT = {"pts": "PTS", "reb": "REB", "ast": "AST"}


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def back(t):  # slight overshoot
    t = max(0.0, min(1.0, t))
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def ctext(d, cx, y, s, font, fill):
    d.text((cx - d.textlength(s, font=font) / 2, y), s, font=font, fill=fill)


def alpha_text(img, cx, y, s, font, fill, a):
    if a <= 0:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((cx - ImageDraw.Draw(layer).textlength(s, font=font) / 2, y), s,
                               font=font, fill=fill + (int(255 * min(1, a)),))
    img.alpha_composite(layer)


def ring_img(r, color, width=12):
    s = 2 * r + 2 * width
    big = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((width, width, s * 2 - width, s * 2 - width),
                                outline=color + (255,), width=width * 2)
    return big.resize((s, s), Image.LANCZOS)


def detail(p, cat):
    if cat == "three":
        return f"{p['tpm']}-{p['tpa']} FROM THREE  ·  {round(100 * p['tpm'] / p['tpa'])}%"
    if cat == "worst_pm":
        return f"{p['pm']:+d} WHILE ON THE FLOOR"
    return f"{p['fgm']}-{p['fga']} FG  ·  {p['tpm']}-{p['tpa']} 3PT  ·  {p['pm']:+d}"


class Leader:
    """Pre-rendered pieces for one leader segment."""
    def __init__(self, p, cat, night):
        self.p, self.cat = p, cat
        self.result = game_result(night, p)
        self.color = ring_color(p["team"])
        self.r = 300
        self.disc = headshot_circle(p, self.r)
        self.ring = ring_img(self.r, self.color)
        lf = ROOT / "data" / "logos" / f"{p['team']}.png"
        self.logo = None
        if lf.exists():
            self.logo = Image.open(lf).convert("RGBA")
            self.logo.thumbnail((70, 70), Image.LANCZOS)
        self.stats = [("PTS", p["pts"]), ("REB", p["reb"]), ("AST", p["ast"]),
                      ("TO", p["tov"]), ("STOCKS", p["stl"] + p["blk"])]

    def draw(self, img, t, idx):
        d = ImageDraw.Draw(img)
        fade = 1.0 if t < SEG - 0.35 else max(0.0, (SEG - t) / 0.35)
        # tag pill
        ty = 210 + (1 - ease(t / 0.4)) * -80
        tf = F(BOLD, 34)
        label = TAGS[self.cat]
        tw = d.textlength(label, font=tf) + 60
        d.rounded_rectangle((W / 2 - tw / 2, ty, W / 2 + tw / 2, ty + 64), radius=32, fill=self.color)
        ctext(d, W / 2, ty + 12, label, tf, (255, 255, 255))
        # headshot with ring, scaling in
        s = (0.6 + 0.4 * back(t / 0.6)) * (1 + 0.07 * max(0.0, t - 0.6) / SEG)   # pop in, then slow push
        cx, cy = W // 2, 640
        disc = self.disc.resize((max(1, int(self.disc.width * s)), max(1, int(self.disc.height * s))), Image.LANCZOS)
        rng = self.ring.resize((max(1, int(self.ring.width * s)), max(1, int(self.ring.height * s))), Image.LANCZOS)
        img.alpha_composite(disc, (cx - disc.width // 2, cy - disc.height // 2))
        img.alpha_composite(rng, (cx - rng.width // 2, cy - rng.height // 2))
        d = ImageDraw.Draw(img)
        # name + logo
        a = ease((t - 0.4) / 0.5)
        name = self.p["name"].upper()
        nf = fit(d, name, NUM, 74, W - 200)
        logo_w = (self.logo.width + 18) if self.logo else 0
        total = logo_w + d.textlength(name, font=nf)
        nx = W / 2 - total / 2
        ny = 990 + (1 - a) * 40
        if a > 0:
            if self.logo:
                lg = self.logo.copy()
                lg.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
                img.alpha_composite(lg, (int(nx), int(ny + 10)))
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((nx + logo_w, ny), name, font=nf, fill=INK + (int(255 * a),))
            img.alpha_composite(layer)
            d = ImageDraw.Draw(img)
        # stat bar with counting numbers
        bx0, by0, bw, bh = 70, 1110, W - 140, 170
        if t > 0.6:
            d.rounded_rectangle((bx0, by0, bx0 + bw, by0 + bh), radius=10, fill=BAR, outline=BAR_EDGE, width=6)
            col = (bw - 20) / 5
            k = ease((t - 0.8) / 1.5)
            pulse = 1 + 0.18 * math.sin(math.pi * min(1, max(0, (t - 2.4) / 0.5)))
            for i, (lab, val) in enumerate(self.stats):
                c = bx0 + 10 + col * i + col / 2
                hot = HOT.get(self.cat) == lab
                shown = round(val * k)
                vf = F(NUM, int(70 * (pulse if hot else 1)))
                color = HIGHLIGHT if hot else (255, 255, 255)
                ctext(d, c, by0 + 18 - (vf.size - 70) / 2, str(shown), vf, color)
                ctext(d, c, by0 + 116, lab, F(BOLD, 24), HIGHLIGHT if hot else LIGHT)
        # detail line (yellow strip for the 3PT / +/- leaders)
        da = ease((t - 2.6) / 0.5)
        if da > 0:
            txt = detail(self.p, self.cat)
            df = F(BOLD, 34)
            if self.cat in ("three", "worst_pm"):
                dw = d.textlength(txt, font=df) + 60
                d.rounded_rectangle((W / 2 - dw / 2, 1305, W / 2 + dw / 2, 1365), radius=10, fill=BAR)
                alpha_text(img, W / 2, 1314, txt, df, HIGHLIGHT, da)
            else:
                alpha_text(img, W / 2, 1312, txt, df, INK, da)
        # opponent + final score
        draw_result(img, W / 2, 1392, self.result, ease((t - 3.0) / 0.5), size=42)
        # progress dots
        d = ImageDraw.Draw(img)
        for j in range(5):
            x = W / 2 + (j - 2) * 44
            fill = self.color if j == idx else (210, 213, 219)
            rr = 11 if j == idx else 8
            d.ellipse((x - rr, 1480 - rr, x + rr, 1480 + rr), fill=fill)
        if fade < 1:
            veil = Image.new("RGBA", img.size, BG + (int(255 * (1 - fade)),))
            img.alpha_composite(veil)


def intro(img, t, night):
    d = ImageDraw.Draw(img)
    date = datetime.strptime(night["date"], "%Y%m%d").strftime("%b %-d, %Y").upper()
    a = ease(t / 0.5)
    alpha_text(img, W / 2 - (1 - a) * 200, 560, date, F(NUM, 64), MUTED, a)
    s = back((t - 0.3) / 0.6)
    if s > 0:
        tf = F(NUM, max(10, int(150 * s)))
        ctext(d, W / 2, 680 + (150 - tf.size) / 2, "NIGHT", tf, INK)
        ctext(d, W / 2, 840 + (150 - tf.size) / 2, "LEADERS", tf, INK)
    n = sum(g["final"] for g in night["games"])
    alpha_text(img, W / 2, 1060, f"{n} GAMES  ·  5 STAT LEADERS", F(BOLD, 40), INK, ease((t - 1.0) / 0.5))
    hf = F(BOLD, 34)
    alpha_text(img, W / 2, 1160, HANDLE, hf, MUTED, ease((t - 1.3) / 0.5))


def scores(img, t, night):
    d = ImageDraw.Draw(img)
    games = [g for g in night["games"] if g["final"]]
    ctext(d, W / 2, 270 + (1 - ease(t / 0.4)) * -60, "FINAL SCORES", F(NUM, 80), INK)
    cols = 1 if len(games) <= 11 else 2
    rows = -(-len(games) // cols)
    top, bottom = 400, 1490
    rh = min(100, (bottom - top) / rows)
    cw = (W - 120) / cols
    f = F(NUM, int(rh * 0.5))
    for i, g in enumerate(games):
        a = ease((t - 0.5 - i * 0.35) / 0.35)
        if a <= 0:
            continue
        r, c = i % rows, i // rows
        x = 60 + c * cw + (1 - a) * 120
        y = top + r * rh
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        if r % 2 == 0:
            ld.rounded_rectangle((x, y + 4, x + cw - 10, y + rh - 4), radius=12, fill=(244, 245, 247, int(255 * a)))
        aw = g["away_score"] > g["home_score"]
        half = (cw - 10) / 2
        for j, (ab, sc, won) in enumerate(((g["away"], g["away_score"], aw), (g["home"], g["home_score"], not aw))):
            sx = x + j * half
            ty = y + (rh - f.size) / 2 - f.size * 0.1
            ld.text((sx + 30, ty), ab, font=f, fill=text_color(ab) + (int(255 * a),))
            s = str(sc)
            ld.text((sx + half - 30 - ld.textlength(s, font=f), ty), s, font=f,
                    fill=(INK if won else MUTED) + (int(255 * a),))
        ld.line((x + half, y + rh * 0.25, x + half, y + rh * 0.75), fill=LIGHT + (int(255 * a),), width=3)
        img.alpha_composite(layer)


def outro(img, t, card):
    a = ease(t / 0.6)
    c = card.copy()
    c.putalpha(int(255 * a))
    img.alpha_composite(c, ((W - c.width) // 2, 200))
    d = ImageDraw.Draw(img)
    alpha_text(img, W / 2, 1460, "FOLLOW FOR THE LEADERS EVERY NIGHT", F(NUM, 46), INK, ease((t - 0.6) / 0.5))


def build(date, out, keep_frames=False):
    night = json.loads((ROOT / "data" / "nights" / f"{date}.json").read_text())
    L = pick(night["players"])
    leaders = [Leader(L[k], k, night) for k in ORDER if k in L]
    card_path = Path(out).with_suffix(".card.jpg")
    render_card(night, card_path)
    card = Image.open(card_path).convert("RGBA").resize((1000, 1250), Image.LANCZOS)
    total = INTRO + SEG * len(leaders) + SCORES + OUTRO

    def frame(img, t):
        if t < INTRO:
            intro(img, t, night)
        elif t < INTRO + SEG * len(leaders):
            k = int((t - INTRO) // SEG)
            leaders[k].draw(img, (t - INTRO) - k * SEG, k)
        elif t < INTRO + SEG * len(leaders) + SCORES:
            scores(img, t - INTRO - SEG * len(leaders), night)
        else:
            outro(img, t - INTRO - SEG * len(leaders) - SCORES, card)

    encode(out, total, frame, seed=1)
    card_path.unlink(missing_ok=True)
    return total


if __name__ == "__main__":
    date = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "media" / f"{date}-leaders.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"{build(date, out):.0f}s ->", out)
