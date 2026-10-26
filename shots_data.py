"""Pull every shot (location, made/missed, value) for the night's top scorers
from ESPN play-by-play.

Usage: python3 shots_data.py YYYYMMDD [N]   (needs data/nights/YYYYMMDD.json)
Writes data/shots/YYYYMMDD.json: {player_id: {"player": {...}, "shots": [...]}}
"""
import json
import sys
from pathlib import Path

from night_data import ROOT, SUMMARY, fetch


def top_scorers(night, n):
    return sorted(night["players"], key=lambda p: (-p["pts"], p["fga"]))[:n]


def shots_for(players):
    by_game = {}
    for p in players:
        by_game.setdefault(p["game"], []).append(p)
    out, sample = {}, None
    for gid, ps in by_game.items():
        summ = fetch(SUMMARY.format(gid))
        plays = summ.get("plays", [])
        ids = {p["id"]: p for p in ps}
        for p in ps:
            out[p["id"]] = {"player": p, "shots": [], "ft_made": 0, "ft_att": 0}
        for pl in plays:
            if not pl.get("shootingPlay"):
                continue
            parts = pl.get("participants") or []
            if not parts:
                continue
            pid = parts[0].get("athlete", {}).get("id")
            if pid not in ids:
                continue
            text = pl.get("text", "")
            typ = (pl.get("type") or {}).get("text", "")
            if "Free Throw" in typ or "free throw" in text.lower():
                out[pid]["ft_att"] += 1
                out[pid]["ft_made"] += 1 if pl.get("scoringPlay") else 0
                continue
            c = pl.get("coordinate") or {}
            sample = sample or pl
            out[pid]["shots"].append({
                "x": c.get("x"), "y": c.get("y"), "made": bool(pl.get("scoringPlay")),
                "value": pl.get("scoreValue"), "type": typ, "text": text,
                "period": (pl.get("period") or {}).get("number"),
                "clock": (pl.get("clock") or {}).get("displayValue"),
            })
    return out, sample


if __name__ == "__main__":
    date = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    night = json.loads((ROOT / "data" / "nights" / f"{date}.json").read_text())
    out, sample = shots_for(top_scorers(night, n))
    d = ROOT / "data" / "shots"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{date}.json").write_text(json.dumps(out, indent=1))
    for pid, v in out.items():
        s = v["shots"]
        made = sum(x["made"] for x in s)
        threes = [x for x in s if x["value"] == 3 or "three" in x["text"].lower()]
        print(f"{v['player']['name']}: box {v['player']['fgm']}-{v['player']['fga']} FG | "
              f"pbp {made}-{len(s)} FG, {sum(x['made'] for x in threes)}-{len(threes)} 3PT, "
              f"FT {v['ft_made']}-{v['ft_att']}")
    print("SAMPLE", json.dumps(sample)[:600])
