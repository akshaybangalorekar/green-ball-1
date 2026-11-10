"""Probe 2: find the JSON endpoint the tournament search uses."""
import json, urllib.request, urllib.parse, re

BASE = "https://tournaments.tennis.com.au"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)"}

def get(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), f"ERR {type(e).__name__}: {e}"

out = {"scripts": [], "api_hits": [], "tests": []}

status, html = get(BASE + "/find/tournament?Distance=20&page=1")
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
out["scripts"] = scripts[:20]

needles = ["/api/", "apiUrl", "baseUrl", "tournament/find", "Postcode", "postcode", "Distance"]
seen = set()
for src in scripts:
    url = src if src.startswith("http") else BASE + ("" if src.startswith("/") else "/") + src
    st, body = get(url)
    if st != 200 or len(body) < 100:
        continue
    for n in needles:
        for m in re.finditer(re.escape(n), body):
            s = max(0, m.start() - 90)
            snip = body[s:m.start() + 110].replace("\n", " ")
            key = snip[:60]
            if key in seen:
                continue
            seen.add(key)
            out["api_hits"].append({"needle": n, "script": url.split("/")[-1][:60], "snippet": snip})
            if len(out["api_hits"]) > 60:
                break

open("probe.json", "w").write(json.dumps(out, indent=1))
print("scripts:", len(scripts), "hits:", len(out["api_hits"]))
for h in out["api_hits"][:25]:
    print("-", h["needle"], "|", h["snippet"][:120])
