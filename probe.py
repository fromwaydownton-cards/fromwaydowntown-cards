import json
from espn_extra import standings, prior_ppg
from guess import pick_outlier
from night_data import ROOT, collect
from datetime import datetime, timedelta
st = standings()
d = datetime(2026, 10, 20)
nights = []
while d <= datetime(2026, 10, 26):
    nights.append(collect(d.strftime("%Y%m%d"))); d += timedelta(days=1)
for n in nights:
    c = pick_outlier(n, prior_ppg)
    print(n["date"], "GUESS:", (f"{c['name']} ({c['team']}) {c['pts']} pts vs normal {c['normal']} ({c['normal_src']})" if c else "none"))
from mvp import ladder
from night_data import save_headshots
rows = ladder(nights, 10, st)
save_headshots([(r["id"], r["headshot"]) for r in rows])
for i, r in enumerate(rows, 1):
    print(f"{i}. {r['name']} ({r['team']}) score {r['score']:.1f} | GmSc {r['gmsc']:.1f} on/off {r['onoff']:+.1f} | team {r['team_w']}-{r['team_l']} #{r['seed']} {r['conf']} | {r['mins']} min")
