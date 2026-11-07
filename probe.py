"""Probe which historical shot-chart sources the Actions runner can reach (round 2)."""
import io
import json
import re
import urllib.request
import zipfile

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"


def get(name, url, raw=False):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            b = r.read()
        print(f"OK {name} {len(b)}B")
        return b if raw else json.loads(b)
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__} {str(e)[:120]}")


b = get("bbref-jordan98", "https://www.basketball-reference.com/players/j/jordami01/shooting/1998", raw=True)
if b:
    t = b.decode("utf8", "ignore")
    tips = re.findall(r'<div style="([^"]+)" tip="([^"]+)" class="tooltip (make|miss)"', t)
    print(" bbref tooltips", len(tips), tips[:2], "| 'tooltip' count", t.count("tooltip"))
    i = t.find("shot-area")
    print(" snippet", t[i:i + 500].replace("\n", " ") if i >= 0 else "no shot-area")
for eid, label in (("170201004", "1997"), ("200206017", "2000"), ("220115013", "2002"), ("240203013", "2004")):
    s = get(f"espn-{label}", f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={eid}")
    if s:
        pl = [p for p in s.get("plays", []) if p.get("shootingPlay")]
        hdr = s.get("header", {}).get("competitions", [{}])[0].get("date")
        print(f" {label} date={hdr} shooting={len(pl)} coord={pl[0].get('coordinate') if pl else None}")
z = get("domsamangy-2016", "https://raw.githubusercontent.com/DomSamangy/NBA_Shots_04_25/main/NBA_2016_Shots.csv.zip", raw=True)
if z:
    zf = zipfile.ZipFile(io.BytesIO(z))
    name = zf.namelist()[0]
    lines = zf.read(name).decode().splitlines()
    print(" ", name, len(lines), "rows")
    print(" ", lines[0])
    print(" ", lines[1])
r = get("gh-domsamangy-data", "https://api.github.com/repos/DomSamangy/NBA_Shots_04_25/contents/Data")
if r:
    print(" Data/", [(f["name"], f.get("size")) for f in r][:10] if isinstance(r, list) else r)
