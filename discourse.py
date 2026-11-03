"""Open captions with a take tied to what NBA fans are arguing about right now.

Talking points live in data/discourse.json (refresh every 1-2 weeks). A take is
used only if one of tonight's featured players (or a worst +/- player's team)
has an entry that hasn't expired. Otherwise callers fall back to their usual
questions, so a stale or missing file never breaks a caption.
"""
import json
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILE = ROOT / "data" / "discourse.json"
SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in s.replace(".", "").split() if w not in {"jr", "sr", "ii", "iii", "iv"})


def last(name):
    parts = name.split()
    while len(parts) > 1 and parts[-1].lower() in SUFFIXES:
        parts.pop()
    return parts[-1]


def load(date):
    try:
        d = json.loads(FILE.read_text())
    except Exception:
        return {"players": [], "teams": []}
    live = lambda e: e.get("until", "9999-12-31").replace("-", "") >= date
    return {"players": [e for e in d.get("players", []) if live(e)],
            "teams": [e for e in d.get("teams", []) if live(e)]}


def line(p):
    """'42 pts, 7 reb, 13 ast' with the zero-ish stats dropped."""
    parts = [f"{p['pts']} pts"]
    if p.get("reb", 0) >= 8:
        parts.append(f"{p['reb']} reb")
    if p.get("ast", 0) >= 7:
        parts.append(f"{p['ast']} ast")
    if len(parts) == 1:
        parts.append(f"{p['fgm']}-{p['fga']} FG")
    return ", ".join(parts)


def form(p, date):
    """', his 3rd straight 40-point game' from earlier nights on disk, else ''."""
    pts = []
    for f in sorted((ROOT / "data" / "nights").glob("*.json"), reverse=True):
        if f.stem >= date:
            continue
        night = json.loads(f.read_text())
        me = next((q for q in night.get("players", []) if q["id"] == p["id"]), None)
        if me is None:
            continue           # off night for his team; keep looking back
        pts.append(me["pts"])
        if len(pts) >= 6:
            break
    for bar in (40, 35, 30):
        if p["pts"] < bar:
            continue
        n = 1
        for x in pts:
            if x < bar:
                break
            n += 1
        if n >= 2:
            nth = {2: "2nd", 3: "3rd"}.get(n, f"{n}th")
            return f", his {nth} straight {bar}-point game"
    return ""


def fill(tpl, p, date):
    v = dict(name=p["name"], last=last(p["name"]), team=p["team"], pts=p["pts"], reb=p["reb"],
             ast=p["ast"], fgm=p["fgm"], fga=p["fga"], tpm=p["tpm"], tpa=p["tpa"],
             pm=f"{p['pm']:+d}", line=line(p), form=form(p, date) if "{form}" in tpl else "")
    return tpl.format(**v)


def take(players, date, worst=None, offset=0):
    """First matching take for players (in priority order), rotating by date.
    worst: the worst +/- player, checked against team takes.
    offset: shifts the rotation so the next-morning post doesn't repeat the night's take.
    Returns str or None."""
    d = load(date)
    for p in players:
        if not p:
            continue
        for e in d["players"]:
            if norm(p["name"]) in {norm(m) for m in e["match"]}:
                takes = e["takes"]
                if offset and len(takes) == 1:
                    break      # only one take: leave it to the night post
                return fill(takes[(int(date) + offset) % len(takes)], p, date)
    if worst:
        for e in d["teams"]:
            if worst["team"] in e["match"] and e.get("worst_pm"):
                return fill(e["worst_pm"], worst, date)
    return None
