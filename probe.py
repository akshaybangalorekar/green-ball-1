"""Find the real tournament URLs for the events in the plan. v2"""
import json, re, urllib.request, urllib.parse, pathlib

UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)"}

def get(url, timeout=60):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"

WINDOWS = [("2026-11-25", "2027-01-05"), ("2027-01-01", "2027-02-15"), ("2027-02-01", "2027-04-15")]
found = {}
seen_pages = 0
for start, end in WINDOWS:
    for page in range(1, 7):
        target = ("https://tournaments.tennis.com.au/find/tournament"
                  f"?DateFilterType=0&StartDate={start}&EndDate={end}&Distance=15&page={page}")
        st, txt = get("https://r.jina.ai/" + target)
        seen_pages += 1
        if st != 200:
            break
        hits = re.findall(r"\[([^\]]{6,120})\]\((https://tournaments\.tennis\.com\.au/sport/tournament\?id=[^\)\s]+)", txt)
        new = 0
        for name, url in hits:
            key = name.strip()
            if key not in found:
                found[key] = url
                new += 1
        if not new:
            break

out = {"pages": seen_pages, "count": len(found), "events": found}
pathlib.Path("events_map.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"{len(found)} tournament links across {seen_pages} pages")
