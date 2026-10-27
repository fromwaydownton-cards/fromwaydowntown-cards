"""Collect a range of nights and the headshots a weekly graphic needs.

Usage: python3 week_data.py START END [--shots DATE]
  START/END: YYYYMMDD (inclusive). Re-collects each night (full box scores),
  saves headshots for the week's top 10 by average Game Score.
  --shots DATE: also pull shot data for that night's top scorer.
"""
import sys
from datetime import datetime, timedelta

from night_data import collect, save_headshots
from mvp import ladder

start, end = sys.argv[1], sys.argv[2]
d = datetime.strptime(start, "%Y%m%d")
nights = []
while d <= datetime.strptime(end, "%Y%m%d"):
    n = collect(d.strftime("%Y%m%d"))
    print(n["date"], len(n["games"]), "games", len(n["players"]), "lines")
    nights.append(n)
    d += timedelta(days=1)
rows = ladder(nights, 10)
save_headshots([(r["id"], r["headshot"]) for r in rows])
for i, r in enumerate(rows, 1):
    print(f"{i}. {r['name']} ({r['team']}) GP {r['gp']} GmSc {r['gmsc']:.1f} | "
          f"{r['ppg']:.1f}/{r['rpg']:.1f}/{r['apg']:.1f} | team {r['w']}-{r['l']}")
if "--shots" in sys.argv:
    import json
    from night_data import ROOT
    from shots_data import build_shots
    date = sys.argv[sys.argv.index("--shots") + 1]
    night = json.loads((ROOT / "data" / "nights" / f"{date}.json").read_text())
    out = build_shots(night, 1)
    for v in out.values():
        print("shots:", v["player"]["name"], len(v["shots"]))
