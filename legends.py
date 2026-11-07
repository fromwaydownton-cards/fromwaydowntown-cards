"""Guess the Player: Legends library and its shot data.

Shot locations only exist from 1996-97 on (and Basketball-Reference's charts for
the late 90s miss some shots, so cards show a shot PROFILE, never "every shot"), so 80s stars appear through their
late-career seasons. Sources (fetched once, saved to data/legends/<slug>.json):
  - 2003-04 to 2024-25: the public NBA shot dataset github.com/DomSamangy/NBA_Shots_04_25
  - 1996-97 to 2002-03: Basketball-Reference season shot charts (one page per entry,
    fetched slowly: 6 s apart)
An entry whose data can't be found is marked missing and never posted.

python3 legends.py fetch [slug ...]     fetch missing entries (all if no slug)
python3 legends.py list                 show the library and what's fetched

Shot format (same as shots_data.py): x 0-50 ft across (hoop at 25),
y = feet from the hoop toward half court; made, three, date.
Hints never name the player, team or a nickname that gives it away.
"""
import csv
import html
import io
import json
import math
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "legends"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
NBA_ZIP = "https://raw.githubusercontent.com/DomSamangy/NBA_Shots_04_25/main/NBA_{}_Shots.csv.zip"
BBREF = "https://www.basketball-reference.com/players/{}/{}/shooting/{}"


def S(slug, name, season, ppg, hints, bbref=None):
    """A full season. season = '1997-98'. ppg is the official per-game average."""
    return {"slug": slug, "name": name, "mode": "season", "season": season, "ppg": ppg,
            "hints": hints, "bbref": bbref}


def G(slug, name, date, pts, hints, bbref=None):
    """One famous game. date = 'YYYY-MM-DD'. pts is the official total."""
    y, m, _ = (int(x) for x in date.split("-"))
    end = y + 1 if m >= 8 else y
    return {"slug": slug, "name": name, "mode": "game", "season": f"{end - 1}-{str(end)[2:]}",
            "date": date, "pts": pts, "hints": hints, "bbref": bbref}


LIBRARY = [
    # --- 80s stars, late-career seasons (1996-97 on) ---
    S("jordan-1998", "Michael Jordan", "1997-98", 28.7, ["WON MVP AND FINALS MVP THAT SEASON", "ROOKIE YEAR: 1984-85"], "jordami01"),
    S("olajuwon-1997", "Hakeem Olajuwon", "1996-97", 23.2, ["CENTER, TWO-TIME CHAMPION", "NO. 1 PICK IN 1984"], "olajuha01"),
    S("malone-1998", "Karl Malone", "1997-98", 27.0, ["POWER FORWARD, 2X MVP IN HIS CAREER", "ROOKIE YEAR: 1985-86"], "malonka01"),
    S("stockton-1997", "John Stockton", "1996-97", 14.4, ["ALL-TIME LEADER IN ASSISTS AND STEALS", "ROOKIE YEAR: 1984-85"], "stockjo01"),
    S("barkley-1997", "Charles Barkley", "1996-97", 19.2, ["WON MVP IN THE EARLY 90s", "ROOKIE YEAR: 1984-85"], "barklch01"),
    S("ewing-1997", "Patrick Ewing", "1996-97", 22.4, ["CENTER, ROOKIE OF THE YEAR IN 1986", "NO. 1 PICK IN 1985"], "ewingpa01"),
    S("reggie-1998", "Reggie Miller", "1997-98", 19.5, ["SPENT HIS WHOLE CAREER WITH ONE TEAM", "ROOKIE YEAR: 1987-88"], "millere01"),
    S("drexler-1997", "Clyde Drexler", "1996-97", 18.0, ["1992 DREAM TEAM MEMBER", "ROOKIE YEAR: 1983-84"], "drexlcl01"),
    S("pippen-1997", "Scottie Pippen", "1996-97", 20.2, ["6-TIME CHAMPION", "ROOKIE YEAR: 1987-88"], "pippesc01"),
    S("robinson-1998", "David Robinson", "1997-98", 21.6, ["ONCE SCORED 71 IN A GAME", "ROOKIE YEAR: 1989-90"], "robinda01"),
    # --- 90s / 2000s ---
    S("penny-1997", "Penny Hardaway", "1996-97", 20.5, ["HAD A PUPPET ALTER EGO IN SNEAKER ADS", "NO. 3 PICK IN 1993"], "hardaan01"),
    S("shaq-2000", "Shaquille O'Neal", "1999-00", 29.7, ["WON MVP, ONE VOTE SHY OF UNANIMOUS", "CENTER"], "onealsh01"),
    S("payton-2000", "Gary Payton", "1999-00", 24.2, ["1996 DEFENSIVE PLAYER OF THE YEAR", "POINT GUARD"], "paytoga01"),
    S("hill-2000", "Grant Hill", "1999-00", 25.8, ["CO-ROOKIE OF THE YEAR IN 1995", "DUKE GRADUATE"], "hillgr01"),
    S("iverson-2001", "Allen Iverson", "2000-01", 31.1, ["WON MVP THAT SEASON", "LISTED AT 6 FEET TALL"], "iversal01"),
    S("vince-2001", "Vince Carter", "2000-01", 27.6, ["WON THE 2000 DUNK CONTEST", "PLAYED 22 SEASONS"], "cartevi01"),
    S("webber-2001", "Chris Webber", "2000-01", 27.1, ["NO. 1 PICK IN 1993", "POWER FORWARD"], "webbech01"),
    S("duncan-2002", "Tim Duncan", "2001-02", 25.5, ["WON MVP THAT SEASON", "NO. 1 PICK IN 1997"], "duncati01"),
    S("rayallen-2002", "Ray Allen", "2001-02", 21.8, ["STARRED IN A SPIKE LEE MOVIE", "SHOOTING GUARD"], "allenra02"),
    S("pierce-2002", "Paul Pierce", "2001-02", 26.1, ["SHAQ GAVE HIM HIS NICKNAME", "NO. 10 PICK IN 1998"], "piercpa01"),
    S("kidd-2002", "Jason Kidd", "2001-02", 14.7, ["MVP RUNNER-UP THAT SEASON", "POINT GUARD"], "kiddja01"),
    S("tmac-2003", "Tracy McGrady", "2002-03", 32.1, ["WON THE SCORING TITLE", "WENT STRAIGHT FROM HIGH SCHOOL"], "mcgratr01"),
    S("garnett-2004", "Kevin Garnett", "2003-04", 24.2, ["WON MVP THAT SEASON", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    S("benwallace-2004", "Ben Wallace", "2003-04", 9.5, ["4-TIME DEFENSIVE PLAYER OF THE YEAR", "WENT UNDRAFTED"]),
    S("nash-2005", "Steve Nash", "2004-05", 15.5, ["WON MVP THAT SEASON", "POINT GUARD"]),
    S("kobe-2006", "Kobe Bryant", "2005-06", 35.4, ["WON THE SCORING TITLE", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    S("dirk-2007", "Dirk Nowitzki", "2006-07", 24.6, ["WON MVP THAT SEASON", "50-40-90 SHOOTING SEASON"]),
    S("arenas-2007", "Gilbert Arenas", "2006-07", 28.4, ["WORE NUMBER ZERO", "SECOND-ROUND PICK"]),
    S("cp3-2008", "Chris Paul", "2007-08", 21.1, ["MVP RUNNER-UP THAT SEASON", "POINT GUARD"]),
    S("wade-2009", "Dwyane Wade", "2008-09", 30.2, ["WON THE SCORING TITLE", "NO. 5 PICK IN 2003"]),
    S("yao-2009", "Yao Ming", "2008-09", 19.7, ["NO. 1 PICK IN 2002", "CENTER"]),
    # --- 2010s ---
    S("rose-2011", "Derrick Rose", "2010-11", 25.0, ["YOUNGEST MVP EVER", "NO. 1 PICK IN 2008"]),
    S("howard-2011", "Dwight Howard", "2010-11", 22.9, ["3 STRAIGHT DEFENSIVE PLAYER OF THE YEAR AWARDS", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    S("lebron-2013", "LeBron James", "2012-13", 26.8, ["WON MVP AND THE TITLE THAT SEASON", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    S("durant-2014", "Kevin Durant", "2013-14", 32.0, ["WON MVP THAT SEASON", "NO. 2 PICK IN 2007"]),
    S("love-2014", "Kevin Love", "2013-14", 26.1, ["ONCE HAD A 30-POINT, 30-REBOUND GAME", "POWER FORWARD"]),
    S("deandre-2015", "DeAndre Jordan", "2014-15", 11.5, ["LED THE LEAGUE IN FG% THAT SEASON", "SECOND-ROUND PICK"]),
    S("korver-2015", "Kyle Korver", "2014-15", 12.1, ["FIRST ALL-STAR TEAM AT AGE 33", "SECOND-ROUND PICK"]),
    S("curry-2016", "Stephen Curry", "2015-16", 30.1, ["FIRST UNANIMOUS MVP EVER", "NO. 7 PICK IN 2009"]),
    S("westbrook-2017", "Russell Westbrook", "2016-17", 31.6, ["AVERAGED A TRIPLE-DOUBLE AND WON MVP", "POINT GUARD"]),
    S("derozan-2017", "DeMar DeRozan", "2016-17", 27.3, ["ALL-STAR WHO RARELY SHOT THREES", "NO. 9 PICK IN 2009"]),
    S("gobert-2017", "Rudy Gobert", "2016-17", 14.0, ["FUTURE 4-TIME DEFENSIVE PLAYER OF THE YEAR", "BORN IN FRANCE"]),
    S("simmons-2018", "Ben Simmons", "2017-18", 15.8, ["ROOKIE OF THE YEAR", "NO. 1 PICK IN 2016"]),
    S("harden-2019", "James Harden", "2018-19", 36.1, ["SCORED 30+ IN 32 STRAIGHT GAMES", "WON THE SCORING TITLE"]),
    S("kawhi-2019", "Kawhi Leonard", "2018-19", 26.6, ["WON FINALS MVP THAT SEASON", "NO. 15 PICK IN 2011"]),
    S("giannis-2020", "Giannis Antetokounmpo", "2019-20", 29.5, ["WON MVP AND DEFENSIVE PLAYER OF THE YEAR", "NO. 15 PICK IN 2013"]),
    S("dame-2020", "Damian Lillard", "2019-20", 30.0, ["PLAYED COLLEGE BALL AT WEBER STATE", "POINT GUARD"]),
    # --- 2020s ---
    S("jokic-2022", "Nikola Jokic", "2021-22", 27.1, ["DRAFTED 41ST OVERALL", "WON MVP THAT SEASON"]),
    S("embiid-2023", "Joel Embiid", "2022-23", 33.1, ["WON MVP THAT SEASON", "BORN IN CAMEROON"]),
    S("tatum-2023", "Jayson Tatum", "2022-23", 30.1, ["SCORED 51 IN A GAME 7 THAT SPRING", "NO. 3 PICK IN 2017"]),
    S("shai-2024", "Shai Gilgeous-Alexander", "2023-24", 30.1, ["MVP RUNNER-UP THAT SEASON", "BORN IN CANADA"]),
    S("wemby-2025", "Victor Wembanyama", "2024-25", 24.3, ["NO. 1 PICK IN 2023", "BORN IN FRANCE"]),
    # --- famous games ---
    G("tmac-62", "Tracy McGrady", "2004-03-10", 62, ["STILL HIS FRANCHISE'S SINGLE-GAME RECORD", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    G("kobe-81", "Kobe Bryant", "2006-01-22", 81, ["SECOND-MOST POINTS IN A GAME EVER", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    G("arenas-60", "Gilbert Arenas", "2006-12-17", 60, ["SCORED 16 IN OVERTIME", "SECOND-ROUND PICK"]),
    G("kobe-65", "Kobe Bryant", "2007-03-16", 65, ["SCORED 50+ IN 4 STRAIGHT GAMES THAT MONTH", "SHOOTING GUARD"]),
    G("melo-62", "Carmelo Anthony", "2014-01-24", 62, ["SET THE MADISON SQUARE GARDEN RECORD", "NO. 3 PICK IN 2003"]),
    G("lebron-61", "LeBron James", "2014-03-03", 61, ["BROKE HIS TEAM'S SINGLE-GAME RECORD", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    G("kobe-60", "Kobe Bryant", "2016-04-13", 60, ["THE LAST GAME OF HIS CAREER", "WENT STRAIGHT FROM HIGH SCHOOL"]),
    G("curry-13threes", "Stephen Curry", "2016-11-07", 46, ["SET A NEW RECORD FOR THREES IN A GAME", "NO. 7 PICK IN 2009"]),
    G("klay-60", "Klay Thompson", "2016-12-05", 60, ["PLAYED ONLY 29 MINUTES", "NO. 11 PICK IN 2011"]),
    G("booker-70", "Devin Booker", "2017-03-24", 70, ["HE WAS 20 YEARS OLD", "NO. 13 PICK IN 2015"]),
    G("klay-14threes", "Klay Thompson", "2018-10-29", 52, ["BROKE HIS TEAMMATE'S THREES RECORD", "NO. 11 PICK IN 2011"]),
    G("harden-61", "James Harden", "2019-01-23", 61, ["TIED THE MADISON SQUARE GARDEN RECORD", "NO. 3 PICK IN 2009"]),
    G("dame-61", "Damian Lillard", "2020-01-20", 61, ["THE GAME WENT TO OVERTIME", "PLAYED COLLEGE BALL AT WEBER STATE"]),
    G("curry-62", "Stephen Curry", "2021-01-03", 62, ["HIS CAREER HIGH", "NO. 7 PICK IN 2009"]),
    G("kat-60", "Karl-Anthony Towns", "2022-03-14", 60, ["SET HIS FRANCHISE'S SINGLE-GAME RECORD", "NO. 1 PICK IN 2015"]),
    G("kyrie-60", "Kyrie Irving", "2022-03-15", 60, ["SET HIS FRANCHISE'S SINGLE-GAME RECORD", "NO. 1 PICK IN 2011"]),
    G("mitchell-71", "Donovan Mitchell", "2023-01-02", 71, ["THE GAME WENT TO OVERTIME", "NO. 13 PICK IN 2017"]),
    G("embiid-70", "Joel Embiid", "2024-01-22", 70, ["BROKE WILT'S FRANCHISE RECORD", "BORN IN CAMEROON"]),
    G("luka-73", "Luka Doncic", "2024-01-26", 73, ["TIED THE 4TH-MOST POINTS IN A GAME EVER", "NO. 3 PICK IN 2018"]),
]
BY_SLUG = {e["slug"]: e for e in LIBRARY}


def decade(e):
    y = int(e["season"][:4])
    return f"{y // 10 * 10}s"


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


# ---------- NBA dataset (2003-04 on) ----------------------------------------

_SEASONS = {}


def season_rows(end_year):
    if end_year not in _SEASONS:
        zf = zipfile.ZipFile(io.BytesIO(fetch(NBA_ZIP.format(end_year))))
        text = zf.read(zf.namelist()[0]).decode("utf8", "ignore")
        _SEASONS[end_year] = list(csv.DictReader(io.StringIO(text)))
    return _SEASONS[end_year]


def from_dataset(e):
    end = int(e["season"][:4]) + 1
    want = norm(e["name"])
    rows = [r for r in season_rows(end) if norm(r["PLAYER_NAME"]) == want]
    shots = []
    for r in rows:
        dt = datetime.strptime(r["GAME_DATE"], "%m-%d-%Y")
        shots.append({"x": round(float(r["LOC_X"]) + 25, 2), "y": round(float(r["LOC_Y"]) - 5.25, 2),
                      "made": r["SHOT_MADE"].upper() == "TRUE", "three": r["SHOT_TYPE"].startswith("3"),
                      "date": dt.strftime("%Y-%m-%d"), "game": r["GAME_ID"],
                      "team": r["TEAM_NAME"]})
    return shots


# ---------- Basketball-Reference (1996-97 to 2002-03) -----------------------

# Last day of each regular season: Basketball-Reference's season chart also
# includes the playoffs, and the legends cards show regular seasons only.
REG_END = {1997: "1997-04-20", 1998: "1998-04-19", 1999: "1999-05-05", 2000: "2000-04-19",
           2001: "2001-04-18", 2002: "2002-04-17", 2003: "2003-04-16"}
TIP = re.compile(r'<div style="top:(-?\d+)px;left:(-?\d+)px;" tip="([^"]+)" class="tooltip (make|miss)"')


def from_bbref(e):
    pid = e["bbref"]
    end = int(e["season"][:4]) + 1
    page = fetch(BBREF.format(pid[0], pid, end)).decode("utf8", "ignore")
    raw = []
    for top, left, tip, res in TIP.findall(page):
        tip = html.unescape(tip)
        m = re.search(r"from (\d+) ft", tip)
        dm = re.match(r"([A-Z][a-z]{2} \d+, \d{4})", tip)
        if not dm:
            continue
        raw.append({"top": int(top), "left": int(left), "made": res == "make",
                    "three": "3-pointer" in tip, "ft": int(m.group(1)) if m else None,
                    "date": datetime.strptime(dm.group(1), "%b %d, %Y").strftime("%Y-%m-%d")})
    # Calibrate the hoop position on bbref's 500 px court (10 px per foot) from the
    # shot distances in the tooltips, so markers land exactly where the shots were.
    cal = [s for s in raw if s["ft"] is not None][:1500]
    best = None
    for cx in range(235, 266):
        for hy in range(20, 81):
            err = sorted(abs(math.hypot((s["left"] - cx) / 10, (s["top"] - hy) / 10) - s["ft"] - 0.5)
                         for s in cal)
            med = err[len(err) // 2] if err else 99
            if best is None or med < best[0]:
                best = (med, cx, hy)
    _, cx, hy = best
    print(f"  bbref calibration: hoop at left={cx}px top={hy}px, median error {best[0]:.2f} ft")
    keep = [s for s in raw if e["mode"] == "game" or s["date"] <= REG_END[end]]
    return [{"x": round((s["left"] - cx) / 10 + 25, 2), "y": round((s["top"] - hy) / 10, 2),
             "made": s["made"], "three": s["three"], "date": s["date"],
             "px": [s["left"], s["top"]], "ft": s["ft"]} for s in keep]


# ---------- fetch + checks --------------------------------------------------

def pick_game(shots, date):
    """Shots from the game on `date` (±1 day for time zones): the game with the
    most field-goal points among those dates."""
    d = datetime.strptime(date, "%Y-%m-%d")
    near = {(d + timedelta(days=k)).strftime("%Y-%m-%d") for k in (-1, 0, 1)}
    by = {}
    for s in shots:
        if s["date"] in near:
            by.setdefault(s["date"], []).append(s)
    if not by:
        return []
    return max(by.values(), key=lambda g: sum((3 if s["three"] else 2) for s in g if s["made"]))


def summarize(e, shots):
    made = sum(s["made"] for s in shots)
    tpa = sum(s["three"] for s in shots)
    tpm = sum(s["made"] and s["three"] for s in shots)
    out = {"fga": len(shots), "fgm": made, "tpa": tpa, "tpm": tpm,
           "games": len({s["date"] for s in shots})}
    if e["mode"] == "game":
        fg_pts = 2 * made + tpm
        out["ftm"] = e["pts"] - fg_pts
    return out


def fetch_entry(e):
    shots = from_bbref(e) if e.get("bbref") and int(e["season"][:4]) < 2003 else from_dataset(e)
    if e["mode"] == "game":
        shots = pick_game(shots, e["date"])
    st = summarize(e, shots) if shots else {}
    ok = bool(shots) and (e["mode"] == "season" and st["fga"] >= 250
                          or e["mode"] == "game" and 0 <= st.get("ftm", -1) <= 30)
    rec = {"entry": e, "ok": ok, "stats": st, "shots": shots,
           "fetched": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"{e['slug']}.json").write_text(json.dumps(rec, separators=(",", ":")))
    return rec


def load(slug):
    f = DATA / f"{slug}.json"
    return json.loads(f.read_text()) if f.exists() else None


def ready():
    """Slugs with good data, in library order."""
    return [e["slug"] for e in LIBRARY if (r := load(e["slug"])) and r["ok"]]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for e in LIBRARY:
            r = load(e["slug"])
            state = "missing" if not r else ("OK" if r["ok"] else "BAD")
            print(f"{e['slug']:<18} {e['mode']:<6} {e['season']}  {state}  {r['stats'] if r else ''}")
        return
    slugs = sys.argv[2:] or [e["slug"] for e in LIBRARY if not load(e["slug"])]
    bad = []
    for slug in slugs:
        e = BY_SLUG[slug]
        try:
            r = fetch_entry(e)
            print(f"{'OK ' if r['ok'] else 'BAD'} {slug}: {r['stats']}")
            if not r["ok"]:
                bad.append(slug)
        except Exception as ex:
            print(f"FAIL {slug}: {type(ex).__name__} {str(ex)[:150]}")
            bad.append(slug)
        if e.get("bbref") and int(e["season"][:4]) < 2003:
            time.sleep(6)            # stay well under Basketball-Reference's rate limit
    print(f"done: {len(slugs) - len(bad)} ok, {len(bad)} not usable: {' '.join(bad)}")


if __name__ == "__main__":
    main()
