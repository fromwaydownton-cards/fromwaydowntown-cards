"""Pick the night's best "Guess the player" candidate: an outlier game.

Outlier = points far above what the player normally scores. Normal is his
last full season's PPG (ESPN); for rookies, his average in our saved games
before this night. Stars (normal >= STAR_PPG) are skipped, since the goal is
a surprise, not another star highlight.
"""
import json

from night_data import ROOT

MIN_PTS, STAR_PPG, MIN_RATIO = 20, 22.0, 1.6


def season_avg(pid, before):
    pts = []
    for f in sorted((ROOT / "data" / "nights").glob("*.json")):
        if f.stem >= before:
            continue
        for p in json.loads(f.read_text())["players"]:
            if p["id"] == pid:
                pts.append(p["pts"])
    return sum(pts) / len(pts) if pts else None


def pick_outlier(night, prior_ppg):
    best = None
    for p in night["players"]:
        if p["pts"] < MIN_PTS:
            continue
        normal = prior_ppg(p["id"])
        src = "last season"
        if normal is None:
            normal, src = season_avg(p["id"], night["date"]), "this season"
        if normal is None:
            normal, src = 8.0, "rookie"
        if normal >= STAR_PPG:
            continue
        jump, ratio = p["pts"] - normal, p["pts"] / max(normal, 4.0)
        if ratio < MIN_RATIO:
            continue
        if not best or jump > best[1]:
            best = (p, jump, normal, src)
    if not best:
        return None
    p, jump, normal, src = best
    return dict(p, normal=round(normal, 1), normal_src=src, jump=round(jump, 1))
