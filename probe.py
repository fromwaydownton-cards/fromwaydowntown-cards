"""One-off: show the shape of ESPN standings and athlete stats responses."""
import json
from night_data import fetch

def show(url, depth=3):
    try:
        d = fetch(url)
    except Exception as e:
        print("FAIL", url, e); return None
    def walk(o, path="", lvl=0):
        if lvl > depth: return
        if isinstance(o, dict):
            for k, v in list(o.items())[:12]:
                t = type(v).__name__
                print("  " * lvl + f"{k}: {t}" + (f" = {str(v)[:70]}" if not isinstance(v, (dict, list)) else f" [{len(v)}]"))
                walk(v, path + "." + k, lvl + 1)
        elif isinstance(o, list) and o:
            walk(o[0], path + "[0]", lvl)
    print("OK", url); walk(d); return d

st = show("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings", 5)
# Ty Jerome (4065733), a role player, for prior-season averages
a = show("https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/4065733/stats", 4)
if a:
    for cat in a.get("categories", [])[:1]:
        print("labels", cat.get("labels") or cat.get("names"))
        for s in (cat.get("statistics") or [])[-3:]:
            print("season", (s.get("season") or {}).get("year"), s.get("stats"))
