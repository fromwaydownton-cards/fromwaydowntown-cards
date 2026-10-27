from espn_extra import standings, prior_ppg
st = standings()
for t in ("LAL", "MEM", "DAL", "HOU", "MIN", "SAC"):
    print(t, st.get(t))
for name, pid in (("Ty Jerome", 4065733), ("Anthony Edwards", 4594268), ("Domantas Sabonis", 3155942),
                  ("Marcus Sasser", 4432107), ("Caleb Wilson (rookie)", 5095151)):
    print(name, "prior PPG:", prior_ppg(pid))
