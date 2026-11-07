"""Probe which historical shot-chart sources the Actions runner can reach."""
import json
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
NBA_H = {"User-Agent": UA, "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com",
         "Accept": "application/json, text/plain, */*", "x-nba-stats-origin": "stats", "x-nba-stats-token": "true",
         "Accept-Language": "en-US,en;q=0.9"}


def get(name, url, headers=None, raw=False):
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            b = r.read()
        print(f"OK {name} {len(b)}B")
        return b if raw else json.loads(b)
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__} {str(e)[:120]}")


d = get("nba-shots-jordan98", "https://stats.nba.com/stats/shotchartdetail?PlayerID=893&Season=1997-98"
        "&SeasonType=Regular%20Season&ContextMeasure=FGA&TeamID=0&GameID=&LeagueID=00&Month=0&OpponentTeamID=0"
        "&Period=0&LastNGames=0&DateFrom=&DateTo=&GameSegment=&Location=&Outcome=&PlayerPosition=&RookieYear="
        "&SeasonSegment=&VsConference=&VsDivision=&PlayerID=893&ContextFilter=&AheadBehind=&ClutchTime=&EndPeriod="
        "&EndRange=&GameEventID=&PointDiff=&RangeType=&StartPeriod=&StartRange=", NBA_H)
if d:
    rs = d["resultSets"][0]
    print(" headers", rs["headers"][:24], "rows", len(rs["rowSet"]), rs["rowSet"][:1])
get("nba-career-jordan", "https://stats.nba.com/stats/playercareerstats?PlayerID=893&PerMode=PerGame", NBA_H)
r = get("gh-domsamangy", "https://api.github.com/repos/DomSamangy/NBA_Shots_04_25/contents")
if r:
    print(" files", [(f["name"], f.get("size")) for f in r][:30])
get("espn-kobe81", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=260122013")
s = get("espn-2009", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=290204018")
if s:
    pl = [p for p in s.get("plays", []) if p.get("shootingPlay")]
    print(" 2009 shooting plays", len(pl), pl[:1] and pl[0].get("coordinate"))
get("bbref", "https://www.basketball-reference.com/players/j/jordami01/shooting/1998", raw=True)
