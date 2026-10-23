"""Post-game stat card generator.

Renders a 1080x1920 vertical card (works for TikTok, YouTube Shorts and
Instagram Reels) plus a caption/hooks text file for one player's game.

Usage: python3 make_card.py cards.json outdir
"""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from team_colors import team_color

W, H = 1080, 1920
_FONTS = Path(__file__).resolve().parent / "fonts"
BLACK_FONT = str(_FONTS / "NotoSansBlack-Latin.otf")
BOLD_FONT = str(_FONTS / "DejaVuSans-Bold.ttf")
REG_FONT = str(_FONTS / "DejaVuSans.ttf")

BG_TOP = (26, 29, 38)
BG_BOT = (42, 34, 54)
ACCENT = (255, 184, 28)
WHITE = (245, 245, 245)
GREY = (150, 155, 165)
SAFE_TOP = 220      # keep text clear of app UI at the top
SAFE_BOTTOM = 1500  # captions/buttons cover the bottom ~400px


def font(path, size):
    return ImageFont.truetype(path, size)


def gradient():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    return img


def centered(d, y, text, f, fill):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def fit(d, text, path, start, max_w):
    size = start
    while size > 30 and d.textlength(text, font=font(path, size)) > max_w:
        size -= 4
    return font(path, size)


def stat_row(d, y, stats, max_size=96, span=None):
    span = span or (W - 100)
    x0 = (W - span) / 2
    col_w = span / len(stats)
    # fixed size from the widest realistic value, so every card lines up
    vsize = fit(d, "88-88", BLACK_FONT, max_size, col_w - 24).size
    vf = font(BLACK_FONT, vsize)
    for i, (label, val) in enumerate(stats):
        lf = fit(d, label, BOLD_FONT, 32, col_w - 8)
        cx = x0 + col_w * i + col_w / 2
        d.text((cx - d.textlength(str(val), font=vf) / 2, y), str(val), font=vf, fill=WHITE)
        d.text((cx - d.textlength(label, font=lf) / 2, y + vsize + 28), label, font=lf, fill=GREY)
    return y + vsize + 115


def render(card, out):
    img = gradient()
    d = ImageDraw.Draw(img)
    s = card["box"]

    y = SAFE_TOP - 40
    centered(d, y, card["date"].upper(), font(BOLD_FONT, 40), ACCENT)
    y += 70

    name = card["player"].upper()
    f = fit(d, name, BLACK_FONT, 110, W - 120)
    bg_mid = tuple((BG_TOP[i] + BG_BOT[i]) // 2 for i in range(3))
    centered(d, y + (110 - f.size) * 0.75, name, f, team_color(card['team'], bg_mid))
    y += 110 + 90

    # points: always the big number
    num = str(s["pts"])
    big = font(BLACK_FONT, 340)
    l, t, r, b = d.textbbox((0, 0), num, font=big)
    d.text(((W - (r - l)) / 2 - l, y - t), num, font=big, fill=ACCENT)
    y += (b - t) + 50
    centered(d, y, "POINTS", font(BOLD_FONT, 56), WHITE)
    y += 140

    # row 1: REB, AST, FG, 3PT
    y = stat_row(d, y, [("REB", s["reb"]), ("AST", s["ast"]),
                        ("FG", f"{s['fgm']}-{s['fga']}"), ("3PT", f"{s['3pm']}-{s['3pa']}")])
    y += 20
    # row 2: BLK, STL, TOV, PF, GAME SCORE
    y = stat_row(d, y, [("BLK", s["blk"]), ("STL", s["stl"]), ("TOV", s["tov"]),
                        ("PF", s["pf"]), ("GAME SCORE", s["gmsc"])], max_size=84)

    # final score + handle
    # final score, each team in its own color
    sf = font(BOLD_FONT, 46)
    parts = []
    for i, seg in enumerate(card["matchup"].split(", ")):
        abbr = seg.split()[0]
        if i:
            parts.append((", ", GREY))
        parts.append((seg, team_color(abbr, bg_mid)))
    total = sum(d.textlength(t, font=sf) for t, _ in parts)
    x = (W - total) / 2
    for t, c in parts:
        d.text((x, y + 10), t, font=sf, fill=c)
        x += d.textlength(t, font=sf)
    centered(d, y + 85, card.get("handle", "@FROMWAYDOWNTOWN"), font(BOLD_FONT, 34), GREY)

    img.save(out / f"{card['slug']}.jpg", "JPEG", quality=92, subsampling=0)
    if "caption" not in card:
        return

    text = [
        f"CAPTION:\n{card['caption']}\n",
        "HOOKS (say one in the first 2 seconds):",
        *[f"- {h}" for h in card["hooks"]],
        "\nTALKING POINTS:",
        *[f"- {t}" for t in card["talking_points"]],
        f"\nHASHTAGS:\n{' '.join(card['hashtags'])}",
    ]
    (out / f"{card['slug']}.txt").write_text("\n".join(text))


if __name__ == "__main__":
    cards = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for c in cards:
        render(c, out)
        print("made", c["slug"])
