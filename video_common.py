"""Shared pieces for the vertical videos: easing, text, rings, the 2X SPEED
badge, game-result lines, and the ffmpeg encoder with the original beat."""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from audio_bed import write_beat
from night_card import BAR, BG, HIGHLIGHT, INK, MUTED, NUM, BOLD, F, text_color

W, H, FPS = 1080, 1920, 30
WIN = (34, 166, 82)
LOSS = (214, 48, 49)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def back(t):
    t = max(0.0, min(1.0, t))
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def ctext(d, cx, y, s, font, fill):
    d.text((cx - d.textlength(s, font=font) / 2, y), s, font=font, fill=fill)


def alpha_text(img, cx, y, s, font, fill, a):
    if a <= 0:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((cx - ld.textlength(s, font=font) / 2, y), s, font=font, fill=fill + (int(255 * min(1, a)),))
    img.alpha_composite(layer)


def ring_img(r, color, width=12):
    s = 2 * r + 2 * width
    big = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((width, width, s * 2 - width, s * 2 - width),
                                outline=color + (255,), width=width * 2)
    return big.resize((s, s), Image.LANCZOS)


def scaled(im, s):
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def speed_badge(img, t):
    """'2X SPEED' pill, top right under the app's search icon; pulses at the start."""
    pulse = 1 + 0.12 * abs(math.sin(math.pi * t / 0.6)) if t < 2.4 else 1.0
    f = F(NUM, int(34 * pulse))
    d = ImageDraw.Draw(img)
    label = "2X SPEED"
    tw = d.textlength(label, font=f)
    icon = int(26 * pulse)
    pad, gap = 22, 12
    w = pad * 2 + icon + gap + tw
    h = int(60 * pulse)
    x1, y0 = W - 40, 178
    x0 = x1 - w
    d.rounded_rectangle((x0, y0, x1, y0 + h), radius=h // 2, fill=BAR, outline=HIGHLIGHT, width=3)
    ix, iy = x0 + pad, y0 + (h - icon) / 2
    for k in (0, icon * 0.55):
        d.polygon([(ix + k, iy), (ix + k + icon * 0.6, iy + icon / 2), (ix + k, iy + icon)], fill=HIGHLIGHT)
    d.text((ix + icon + gap, y0 + (h - f.size) / 2 - f.size * 0.12), label, font=f, fill=(255, 255, 255))


def game_result(night, p):
    """(opponent, 'vs' or '@', won, team score, opponent score) for a player's game."""
    g = next((g for g in night["games"] if g["id"] == p.get("game")), None)
    if not g:
        return None
    home = g["home"] == p["team"]
    mine, theirs = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
    return (g["away"] if home else g["home"]), ("vs" if home else "@"), mine > theirs, mine, theirs


def draw_result(img, cx, y, res, a=1.0, size=40):
    """'vs CLE · L 125-127' with the opponent in its team color and W/L in green/red."""
    if not res or a <= 0:
        return
    opp, where, won, mine, theirs = res
    f = F(NUM, size)
    parts = [(f"{where.upper()} ", MUTED), (opp, text_color(opp)), ("  ·  ", MUTED),
             ("W " if won else "L ", WIN if won else LOSS), (f"{mine}-{theirs}", INK)]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    total = sum(ld.textlength(s, font=f) for s, _ in parts)
    x = cx - total / 2
    for s, c in parts:
        ld.text((x, y), s, font=f, fill=c + (int(255 * min(1, a)),))
        x += ld.textlength(s, font=f)
    img.alpha_composite(layer)


def encode(out, total, draw_frame, seed=7):
    """Render frames with draw_frame(img, t) (badge added here) and mux the beat."""
    out = Path(out)
    wav = out.with_suffix(".wav")
    write_beat(wav, total, seed=seed)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    blank = Image.new("RGBA", (W, H), BG + (255,))
    for fi in range(int(total * FPS)):
        t = fi / FPS
        img = blank.copy()
        draw_frame(img, t)
        speed_badge(img, t)
        proc.stdin.write(img.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink(missing_ok=True)
    return total
