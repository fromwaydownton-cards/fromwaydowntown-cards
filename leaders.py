"""Pick the five players for the nightly graphic.

pts: most points            (tiebreak: fewer FGA)
reb: most rebounds          (tiebreak: more points)
ast: most assists           (tiebreak: fewer turnovers)
three: best 3PT% with at least MIN_3PA attempts (tiebreak: more makes)
worst_pm: lowest plus/minus (tiebreak: more minutes doesn't exist here, so fewer points)
A player can only appear once; if a later category's leader is already shown,
the next player in that category is used.
"""
MIN_3PA = 5


def pick(players):
    used, out = set(), {}

    def take(key, rank, pool=players):
        for p in sorted(pool, key=rank):
            if p["id"] not in used:
                used.add(p["id"])
                out[key] = p
                return

    take("pts", lambda p: (-p["pts"], p["fga"]))
    take("reb", lambda p: (-p["reb"], -p["pts"]))
    take("ast", lambda p: (-p["ast"], p["tov"]))
    shooters = [p for p in players if p["tpa"] >= MIN_3PA] or [p for p in players if p["tpa"] > 0]
    take("three", lambda p: (-(p["tpm"] / p["tpa"]), -p["tpm"]), shooters)
    take("worst_pm", lambda p: (p["pm"], p["pts"]))
    return out
