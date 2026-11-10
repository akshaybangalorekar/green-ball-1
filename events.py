"""Daily pull of junior tournaments within ~20 km of postcode 3163.

The Tennis Australia calendar filters in the browser, so the URL cannot be
pre-filtered. We render the page through r.jina.ai, parse the list, then keep
only the suburbs that sit inside the radius and the events that suit a junior
moving from green to yellow ball.

Writes events.json. If anything fails, the previous file is left untouched.
"""
import json, re, sys, urllib.request, datetime, pathlib

HOME_SUBURBS = {
    # within roughly 20 km of Glen Huntly (3163)
    "glen huntly", "caulfield", "caulfield south", "caulfield north", "caulfield east",
    "carnegie", "murrumbeena", "bentleigh", "bentleigh east", "mckinnon", "ormond",
    "elwood", "st kilda", "st kilda east", "balaclava", "ripponlea", "windsor",
    "prahan", "prahran", "south yarra", "toorak", "armadale", "malvern", "malvern east",
    "glen iris", "ashburton", "ashwood", "burwood", "chadstone", "hughesdale",
    "oakleigh", "oakleigh east", "huntingdale", "clayton", "notting hill",
    "mount waverley", "wheelers hill", "mulgrave", "glen waverley", "springvale",
    "noble park", "keysborough", "dingley", "dingley village", "mentone", "parkdale",
    "mordialloc", "moorabbin", "highett", "cheltenham", "brighton", "brighton east",
    "hampton", "black rock", "sandringham", "beaumaris", "elsternwick", "elwood",
    "glenhuntly", "caulfield junction", "glen huntly", "south yarra", "hawthorn",
    "hawthorn east", "kew", "hawthorn", "balwyn", "canterbury", "surrey hills",
    "deepdene", "blackburn", "box hill", "mont albert", "forest hill", "nunawading",
}

WANT = re.compile(r"(?i)\b(junior|coloured ball|cbc|green|orange|red ball|jds|de minaur|u/?1[024]|10u|12u|14u)\b")
DROP = re.compile(r"(?i)\b(invite only|invitation only|cancelled|closed)\b")

FEED = "https://tournaments.tennis.com.au/find/tournament"


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)",
        "Accept": "text/plain",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse(text):
    """Pull (name, url, club, suburb, start, end, surface) out of the rendered page."""
    rows = []
    # #### [Name](url "...")  then  Club | Suburb 10/11/2026 to 12/11/2026 Hardcourt
    for m in re.finditer(r"####\s*\[([^\]]+)\]\(([^)\s]+)[^)]*\)\s*\n+\s*([^\n|]+?)\s*\|\s*([A-Za-z '\-\.]+?)\s+"
                         r"(\d{1,2}/\d{1,2}/\d{4})(?:\s+to\s+(\d{1,2}/\d{1,2}/\d{4}))?", text):
        name, url, club, suburb, start, end = m.groups()
        tail = text[m.end():m.end() + 200]
        surface = ""
        for s in ("Hardcourt", "Clay", "Syn Grass", "Grass", "Various"):
            if s.lower() in tail[:120].lower():
                surface = s
                break
        rows.append({
            "name": name.strip(), "url": url.strip(),
            "club": club.strip(), "suburb": suburb.strip(),
            "start": start, "end": end or start, "surface": surface,
            "tags": " ".join(re.findall(r"[A-Za-z0-9/+ ]+", tail[:200]))[:160].strip(),
        })
    return rows


def keep(ev):
    sub = ev["suburb"].lower().strip()
    if sub not in HOME_SUBURBS:
        return False
    blob = f"{ev['name']} {ev['tags']}"
    if DROP.search(blob):
        return False
    return bool(WANT.search(blob))


def iso(d):
    day, month, year = d.split("/")
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def main():
    today = datetime.date.today()
    start, end = today.isoformat(), (today + datetime.timedelta(days=120)).isoformat()
    seen, events = set(), []
    for page in (1, 2, 3):
        url = (f"{FEED}?DateFilterType=0&StartDate={start}&EndDate={end}"
               f"&Distance=20&page={page}")
        try:
            text = fetch("https://r.jina.ai/" + url)
        except Exception as e:
            print(f"  page {page}: {type(e).__name__} {e}")
            break
        rows = parse(text)
        print(f"  page {page}: {len(rows)} listings")
        if not rows:
            break
        for ev in rows:
            if ev["name"] in seen or not keep(ev):
                continue
            seen.add(ev["name"])
            ev["start"] = iso(ev["start"])
            ev["end"] = iso(ev["end"])
            events.append(ev)

    events.sort(key=lambda e: (e["start"], e["name"]))
    pathlib.Path("events.json").write_text(json.dumps({
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "postcode": "3163",
        "radius_km": 20,
        "events": events,
    }, indent=1, ensure_ascii=False))
    print(f"kept {len(events)} events near 3163")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        rows = parse(pathlib.Path(sys.argv[1]).read_text())
        print(f"parsed {len(rows)}; kept {sum(1 for r in rows if keep(r))}")
        for r in rows:
            if keep(r):
                print(" -", r["name"][:60], "|", r["suburb"], r["start"])
    else:
        main()
