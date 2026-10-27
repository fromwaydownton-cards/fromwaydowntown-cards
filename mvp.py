"""Weekly MVP ladder.

MVP score = average Game Score
          + 0.15 x on/off net rating (team point margin per 48 min with him on
            the floor minus with him on the bench, over the week)
          + 8 x (team win% - .500)  (season standings)
Minimum 2 games and 50 minutes in the week.

On/off is exact from box scores: the team's margin while he played is his
plus/minus; the margin while he sat is the final margin minus that, over the
game's remaining minutes.
"""
MIN_GP, MIN_MIN = 2, 50
W_ONOFF, W_TEAM = 0.15, 8.0


def game_score(p):
    return (p["pts"] + 0.4 * p["fgm"] - 0.7 * p["fga"] - 0.4 * (p.get("fta", 0) - p.get("ftm", 0))
            + 0.7 * p.get("oreb", 0) + 0.3 * p.get("dreb", p["reb"]) + p["stl"] + 0.7 * p["ast"]
            + 0.7 * p["blk"] - 0.4 * p.get("pf", 0) - p["tov"])


def game_minutes(team_minutes):
    """Regulation 48, plus 5 per overtime, from the team's summed player minutes."""
    raw = team_minutes / 5
    return 48 + 5 * max(0, round((raw - 48) / 5))


def ladder(nights, n=5, standings=None):
    standings = standings or {}
    games, team_min = {}, {}
    for night in nights:
        for g in night["games"]:
            if g["final"]:
                games[g["id"]] = g
        for p in night["players"]:
            k = (p["game"], p["team"])
            team_min[k] = team_min.get(k, 0) + p.get("min", 0)
    agg = {}
    for night in nights:
        for p in night["players"]:
            if p["game"] not in games:
                continue
            a = agg.setdefault(p["id"], {"id": p["id"], "name": p["name"], "team": p["team"],
                                         "headshot": p["headshot"], "lines": []})
            a["team"] = p["team"]
            a["lines"].append(p)
    rows = []
    for a in agg.values():
        L = a["lines"]
        mins = sum(p.get("min", 0) for p in L)
        if len(L) < MIN_GP or mins < MIN_MIN:
            continue
        on_pts = off_pts = off_min = 0
        w = l = 0
        for p in L:
            g = games[p["game"]]
            home = g["home"] == p["team"]
            margin = (g["home_score"] - g["away_score"]) * (1 if home else -1)
            w += margin > 0
            l += margin < 0
            gm = game_minutes(team_min.get((p["game"], p["team"]), 240))
            on_pts += p["pm"]
            off_pts += margin - p["pm"]
            off_min += max(0, gm - p.get("min", 0))
        on48 = on_pts / mins * 48 if mins else 0
        off48 = off_pts / off_min * 48 if off_min else 0
        st = standings.get(a["team"], {})
        pct = st.get("pct", 0.5)
        gp = len(L)
        gmsc = sum(game_score(p) for p in L) / gp
        onoff = on48 - off48
        rows.append(dict(a, gp=gp, w=w, l=l, mins=mins, gmsc=gmsc, onoff=onoff, on48=on48, off48=off48,
                         team_w=st.get("w"), team_l=st.get("l"), seed=st.get("seed"), conf=st.get("conf"),
                         score=gmsc + W_ONOFF * onoff + W_TEAM * (pct - 0.5),
                         ppg=sum(p["pts"] for p in L) / gp, rpg=sum(p["reb"] for p in L) / gp,
                         apg=sum(p["ast"] for p in L) / gp,
                         fg=(sum(p["fgm"] for p in L), sum(p["fga"] for p in L)),
                         best=max(p["pts"] for p in L)))
    rows.sort(key=lambda r: (-r["score"], -r["gmsc"]))
    return rows[:n]
