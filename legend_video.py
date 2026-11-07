"""Vertical 60-second Guess the Player video (1080x1920), themed like its card.

0-3 s title, 3-33 s the shots appear (dots for a game, the heat map fills in
for a season), then the stat bar and hints, a 10-second countdown, and the
call to action. Uses the shared encoder and original beat from video_common.
"""
from PIL import Image, ImageDraw

from legend_card import chip_bar, court_image, legend_key, mystery, pill
from night_card import BOLD, HANDLE, NUM, F, fit
from themes import background
from video_common import H, W, alpha_text, ctext, ease, encode

COURT_W = 980
COURT_X = (W - COURT_W) // 2
COURT_Y = 560
INTRO, SHOW0, SHOW1, STATS, COUNT, END, TOTAL = 3.0, 4.0, 32.0, 33.0, 46.0, 56.0, 60.0


def build(subject, out):
    th = subject["theme"]
    bg = background(W, H, th, seed=subject["n"])
    shots = subject["shots"]
    n = len(shots)
    cache = {}

    def court_at(shown):
        # a season redraws the heat map at most 10 times a second
        key = shown if subject["mode"] == "game" else round(shown / max(1, n / 280))
        if key not in cache:
            cache.clear()
            cache[key] = court_image(subject, COURT_W, shown=shown)
        return cache[key]

    def frame(img, t):
        img.alpha_composite(bg)
        d = ImageDraw.Draw(img)
        if t < INTRO:
            a = ease(t / 0.6)
            alpha_text(img, W / 2, 640, "GUESS THE", F(NUM, 120), th["ink"], a)
            alpha_text(img, W / 2, 780, "PLAYER", F(NUM, 160), th["accent"], ease((t - 0.3) / 0.6))
            alpha_text(img, W / 2, 990, f"#{subject['n']}", F(NUM, 90), th["ink"], ease((t - 0.8) / 0.6))
            sub = subject["sub"]
            alpha_text(img, W / 2, 1120, sub, fit(d, sub, BOLD, 30, W - 80), th["muted"], ease((t - 1.2) / 0.6))
            return
        # header
        d.text((50, 300), "GUESS THE PLAYER", font=F(NUM, 64), fill=th["ink"])
        tw = d.textlength("GUESS THE PLAYER", font=F(NUM, 64))
        num = f"#{subject['n']}"
        nw = d.textlength(num, font=F(NUM, 36)) + 34
        d.rounded_rectangle((50 + tw + 20, 314, 50 + tw + 20 + nw, 366), radius=26, fill=th["accent"])
        d.text((50 + tw + 37, 316), num, font=F(NUM, 36), fill=th["chip"])
        d.text((52, 398), subject["sub"], font=fit(d, subject["sub"], BOLD, 26, W - 104), fill=th["muted"])
        d.text((52, 446), HANDLE, font=F(BOLD, 24), fill=th["muted"])
        # court
        prog = (t - SHOW0) / (SHOW1 - SHOW0)
        shown = 0 if t < SHOW0 else min(n, int(max(0.0, prog) * n) + 1)
        ct = court_at(shown)
        d.rounded_rectangle((COURT_X - 7, COURT_Y - 7, COURT_X + COURT_W + 7, COURT_Y + ct.height + 7),
                            radius=14, fill=th["accent"])
        img.alpha_composite(ct, (COURT_X, COURT_Y))
        d = ImageDraw.Draw(img)
        y = COURT_Y + ct.height + 22
        legend_key(d, COURT_X + 4, y, subject, size=24)
        y += 60
        if t < STATS:
            made = sum(s["made"] for s in shots[:shown])
            label = f"{shown} SHOTS  ·  {made} MADE" if subject["mode"] == "game" else f"{shown:,} SHOTS"
            ctext(d, W / 2, y + 20, label, F(NUM, 54), th["ink"])
            return
        r = 110
        mystery(img, COURT_X + r + 6, y + r + 6, r, th)
        d = ImageDraw.Draw(img)
        px = COURT_X + 2 * r + 46
        pw = COURT_X + COURT_W - px
        if t >= STATS:
            chip_bar(d, px, y, pw, subject["chips"], th, h=100, vsize=40)
        hy = y + 120
        for i, h in enumerate(subject["hints"][:2]):
            if t >= STATS + 2 + i * 3:
                pill(d, px, hy, "HINT: " + h, th, size=22, max_w=pw)
            hy += 52
        by = y + 2 * r + 40
        if COUNT <= t < END:
            left = max(1, int(END - t) + 1)
            ctext(d, W / 2, by, "LOCK IN YOUR GUESS", F(NUM, 50), th["ink"])
            ctext(d, W / 2, by + 64, str(min(left, 10)), F(NUM, 120), th["accent"])
        elif t >= END:
            a = ease((t - END) / 0.5)
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle((50, by, W - 50, by + 190), radius=20,
                                                    fill=th["chip"] + (int(255 * a),))
            img.alpha_composite(layer)
            alpha_text(img, W / 2, by + 30, "DROP YOUR GUESS IN THE COMMENTS", F(NUM, 48), (255, 255, 255), a)
            alpha_text(img, W / 2, by + 110, "ANSWER IN TOMORROW'S POST", F(BOLD, 34), th["accent"], a)

    return encode(out, TOTAL, frame, seed=subject["n"] % 9 + 1)
