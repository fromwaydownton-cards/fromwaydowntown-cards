import json
from espn_extra import prior_ppg, standings
from guess import pick_outlier
from night_data import ROOT, save_headshots
from shots_data import shots_for
standings()
n = json.loads((ROOT / "data" / "nights" / "20261026.json").read_text())
c = pick_outlier(n, prior_ppg)
out, _ = shots_for([c])
(ROOT / "data" / "guess").mkdir(parents=True, exist_ok=True)
(ROOT / "data" / "guess" / "20261026.json").write_text(json.dumps({"pick": c, "shots": out[c["id"]]}, indent=1))
save_headshots([(c["id"], c["headshot"])])
print("guess", c["name"], c["pts"], "normal", c["normal"], len(out[c["id"]]["shots"]), "shots")
