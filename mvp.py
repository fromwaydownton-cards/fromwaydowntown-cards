"""Weekly MVP ladder: rank players by average Game Score over the week.

Minimum 2 games. Ties broken by points per game. Also tracks each player's
team record that week, since winning matters in MVP talk.
"""
MIN_GP = 2


def game_score(p):
    return (p["pts"] + 0.4 * p["fgm"] - 0.7 * p["fga"] - 0.4 * (p.get("fta", 0) - p.get("ftm", 0))
            + 0.7 * p.get("oreb", 0) + 0.3 * p.get("dreb", p["reb"]) + p["stl"] + 0.7 * p["ast"]
            + 0.7 * p["blk"] - 0.4 * p.get("pf", 0) - p["tov"])


def ladder(nights, n=5):
    team_wl, games = {}, {}
    for night in nights:
        for g in night["games"]:
            if not g["final"]:
                continue
            games[g["id"]] = g
            hw = g["home_score"] > g["away_score"]
            for t, won in ((g["home"], hw), (g["away"], not hw)):
                w, l = team_wl.get(t, (0, 0))
                team_wl[t] = (w + won, l + (not won))
    agg = {}
    for night in nights:
        for p in night["players"]:
            a = agg.setdefault(p["id"], {"id": p["id"], "name": p["name"], "team": p["team"],
                                         "headshot": p["headshot"], "lines": []})
            a["team"] = p["team"]
            a["lines"].append(p)
    rows = []
    for a in agg.values():
        L = a["lines"]
        if len(L) < MIN_GP:
            continue
        gp = len(L)
        # player's team record in the games he played
        w = l = 0
        for p in L:
            g = games.get(p.get("game"))
            if not g:
                continue
            home = g["home"] == p["team"]
            won = (g["home_score"] > g["away_score"]) == home
            w += won
            l += not won
        rows.append(dict(a, gp=gp, w=w, l=l,
                         gmsc=sum(game_score(p) for p in L) / gp,
                         ppg=sum(p["pts"] for p in L) / gp, rpg=sum(p["reb"] for p in L) / gp,
                         apg=sum(p["ast"] for p in L) / gp,
                         fg=(sum(p["fgm"] for p in L), sum(p["fga"] for p in L)),
                         best=max(p["pts"] for p in L)))
    rows.sort(key=lambda r: (-r["gmsc"], -r["ppg"]))
    return rows[:n]
