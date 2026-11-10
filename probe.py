"""Probe 5: can a renderer return the site's own postcode-filtered list?"""
import json, urllib.request, urllib.parse, re

UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)",
      "Accept": "text/plain"}

def get(url, timeout=60):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), f"ERR {type(e).__name__}: {e}"

BASE = "https://tournaments.tennis.com.au/find/tournament"
def target(**kw):
    p = {"DateFilterType": "0", "StartDate": "2026-11-10", "EndDate": "2027-03-01", "Distance": "20", "page": "1"}
    p.update(kw)
    return BASE + "?" + urllib.parse.urlencode(p)

variants = {
    "plain": target(),
    "Postcode": target(Postcode="3163"),
    "Location": target(Location="3163"),
    "StateVIC": target(State="VIC"),
}

def summarise(text):
    names = re.findall(r"#### \[([^\]]+)\]", text)
    places = re.findall(r"\n([A-Z][^|\n]{2,40}) \| ([A-Za-z \-']{3,30}) \d{1,2}/\d{1,2}/\d{4}", text)
    return names[:6], places[:6]

out = {"tests": []}
for name, url in variants.items():
    st, body = get("https://r.jina.ai/" + url)
    names, places = summarise(body) if st == 200 else ([], [])
    out["tests"].append({"name": name, "status": st, "bytes": len(body),
                         "names": names, "places": places, "head": body[:200].replace("\n", " ")})

open("probe.json", "w").write(json.dumps(out, indent=1))
for t in out["tests"]:
    print(t["name"], t["status"], t["bytes"], "|", "; ".join(p[1] for p in t["places"]))
