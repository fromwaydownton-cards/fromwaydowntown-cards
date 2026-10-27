"""ESPN standings and players' prior-season scoring averages."""
import json

from night_data import ESPN_ABBR, ROOT, fetch

STANDINGS = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
ATHLETE_STATS = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{}/stats"


def standings():
    """{abbr: {"w", "l", "pct", "seed", "conf"}} for the current season."""
    d = fetch(STANDINGS)
    out = {}
    for conf in d.get("children", []):
        cname = conf.get("abbreviation", "")
        for e in conf["standings"]["entries"]:
            abbr = ESPN_ABBR.get(e["team"]["abbreviation"], e["team"]["abbreviation"])
            st = {s["name"]: s.get("value") for s in e["stats"]}
            out[abbr] = {"w": int(st.get("wins") or 0), "l": int(st.get("losses") or 0),
                         "pct": float(st.get("winPercent") or 0), "seed": int(st.get("playoffSeed") or 0),
                         "conf": cname}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "standings.json").write_text(json.dumps(out, indent=1))
    return out


def prior_ppg(athlete_id, current_year=2027, min_gp=10):
    """Points per game in the player's most recent completed season (None for rookies)."""
    cache_f = ROOT / "data" / "prior_ppg.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    if str(athlete_id) in cache:
        return cache[str(athlete_id)]
    d = fetch(ATHLETE_STATS.format(athlete_id))
    val = None
    for cat in d.get("categories", []):
        if cat.get("name") not in ("averages", None) and "aver" not in str(cat.get("displayName", "")).lower():
            continue
        names = cat.get("names") or cat.get("labels") or []
        labels = [str(x).lower() for x in names]
        pi = next((i for i, x in enumerate(labels) if x in ("pts", "avgpoints", "points")), None)
        gi = next((i for i, x in enumerate(labels) if x in ("gp", "gamesplayed")), None)
        if pi is None:
            continue
        seasons = []
        for s in cat.get("statistics", []):
            yr = (s.get("season") or {}).get("year")
            st = s.get("stats") or []
            try:
                gp = float(st[gi]) if gi is not None else 99
                seasons.append((yr, gp, float(st[pi])))
            except (ValueError, IndexError, TypeError):
                pass
        done = [x for x in seasons if x[0] and x[0] < current_year and x[1] >= min_gp]
        if done:
            val = max(done)[2]
        break
    cache[str(athlete_id)] = val
    cache_f.write_text(json.dumps(cache, indent=1))
    return val
