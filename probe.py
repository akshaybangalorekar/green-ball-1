"""One-off probe: work out how tournaments.tennis.com.au exposes a filtered list."""
import json, urllib.request, urllib.parse, datetime, re, sys

BASE = "https://tournaments.tennis.com.au"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)"}

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), f"ERR {type(e).__name__}: {e}"

today = datetime.date.today()
start = today.isoformat()
end = (today + datetime.timedelta(days=120)).isoformat()

def q(**kw):
    p = {"DateFilterType": "0", "StartDate": start, "EndDate": end, "Distance": "20", "page": "1"}
    p.update(kw)
    return BASE + "/find/tournament?" + urllib.parse.urlencode(p)

out = {"start": start, "end": end, "tests": []}

# 1. does the page render server-side, and which postcode param does it accept?
variants = {
    "no_postcode": q(),
    "Postcode": q(Postcode="3163"),
    "ZipCode": q(ZipCode="3163"),
    "PostCode": q(PostCode="3163"),
    "Location": q(Location="3163"),
}
for name, url in variants.items():
    status, body = get(url)
    ids = len(re.findall(r"sport/tournament\?id=", body))
    vics = len(re.findall(r"\b(Toorak|Malvern|Glen Iris|Caulfield|Glen Huntly|Oakleigh|Mentone|Dingley|Bentleigh|Carnegie)\b", body))
    out["tests"].append({
        "name": name, "url": url, "status": status, "bytes": len(body),
        "tournament_links": ids, "vic_suburb_hits": vics,
        "head": body[:300].replace("\n", " "),
    })

# 2. any obvious JSON api behind the list?
for path in ["/api/tournament/find", "/api/find/tournament", "/api/tournaments"]:
    url = BASE + path + "?" + urllib.parse.urlencode({"postcode": "3163", "distance": "20"})
    status, body = get(url)
    out["tests"].append({"name": "api " + path, "url": url, "status": status,
                         "bytes": len(body), "head": body[:200].replace("\n", " ")})

open("probe.json", "w").write(json.dumps(out, indent=1))
print("wrote probe.json")
for t in out["tests"]:
    print(t.get("name"), t.get("status"), t.get("bytes"), "links=" + str(t.get("tournament_links")), "vic=" + str(t.get("vic_suburb_hits")))
