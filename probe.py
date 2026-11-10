"""Probe 4: is the result list in the HTML, and which location params work?"""
import json, urllib.request, urllib.parse, re

BASE = "https://tournaments.tennis.com.au"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)"}

def get(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), f"ERR {type(e).__name__}: {e}"

def names(html):
    found = re.findall(r'href="([^"]*tournament[^"]*)"', html, re.I)
    return found

def q(**kw):
    p = {"DateFilterType": "0", "StartDate": "2026-11-10", "EndDate": "2027-03-01", "Distance": "20", "page": "1"}
    p.update(kw)
    return BASE + "/find/tournament?" + urllib.parse.urlencode(p)

out = {"tests": []}
for name, url in {
    "plain": q(),
    "Postcode": q(Postcode="3163"),
    "State": q(State="VIC"),
    "PostcodeState": q(Postcode="3163", State="VIC"),
}.items():
    st, body = get(url)
    links = names(body)
    # any embedded json blob?
    blobs = re.findall(r'<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.{0,200})', body, re.S)
    out["tests"].append({
        "name": name, "status": st, "bytes": len(body),
        "tournament_hrefs": len(links),
        "sample": links[:4],
        "json_blobs": len(blobs),
        "postcode_field": len(re.findall(r'(?i)name="[^"]*postcode[^"]*"', body)),
        "has_results_word": "Results" in body,
    })

open("probe.json", "w").write(json.dumps(out, indent=1))
for t in out["tests"]:
    print(t["name"], "| status", t["status"], "| hrefs", t["tournament_hrefs"], "| json", t["json_blobs"], "| pcfield", t["postcode_field"])
    for s in t["sample"]:
        print("    ", s[:90])
