"""Probe 3: enumerate every /api/ endpoint in the site's bundles."""
import json, urllib.request, re

BASE = "https://tournaments.tennis.com.au"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)"}

def get(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), f"ERR {type(e).__name__}: {e}"

status, html = get(BASE + "/find/tournament?Distance=20&page=1")
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)

paths, search_ctx = set(), []
for src in scripts:
    url = src if src.startswith("http") else BASE + ("" if src.startswith("/") else "/") + src
    if "googletagmanager" in url:
        continue
    st, body = get(url)
    if st != 200:
        continue
    for m in re.finditer(r'/api/[A-Za-z0-9_\-/]{2,60}', body):
        paths.add(m.group(0))
    for m in re.finditer(r'(?i)(search[a-z]*tournament|tournament[a-z]*search|findTournament|TournamentList)', body):
        s = max(0, m.start() - 120)
        search_ctx.append(body[s:m.start() + 160].replace("\n", " "))

out = {"scripts": scripts, "api_paths": sorted(paths)[:120], "search_ctx": search_ctx[:15]}
open("probe.json", "w").write(json.dumps(out, indent=1))
print("api paths:", len(paths))
for p in sorted(paths):
    if any(k in p.lower() for k in ("tour", "search", "find", "event", "comp")):
        print("  *", p)
