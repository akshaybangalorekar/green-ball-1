"""Harvest junior tournaments near Carnegie 3163 from UTR and Tennis Australia."""
import json, re, math, pathlib, datetime, urllib.request, urllib.parse, time

HOME = (-37.8447, 145.0694)   # Carnegie 3163
MY_UTR = float(__import__("os").environ.get("MY_UTR", "1.6"))
UTR_MIN = max(0.0, round(MY_UTR - 1.0, 1))
UTR_MAX = round(MY_UTR + 2.0, 1)
RADIUS_KM = 60
UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)", "Accept": "application/json"}

def km(a, b):
    R = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

def jget(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("GET failed:", type(e).__name__, str(e)[:80])
        return None

# ---------- UTR (public JSON API) ----------
def utr_events():
    out = []
    base = ("https://api.utrsports.net/v2/search/events?top=100&searchOrigin=searchPage"
            "&showTennisContent=true&showPickleballContent=false&eventState=open_registration"
            f"&utrMin={UTR_MIN}&utrMax={UTR_MAX}&utrType=verified&utrTeamType=singles"
            f"&latitude={HOME[0]}&longitude={HOME[1]}&distance=50")
    data = jget(base)
    if not data:
        return out
    for h in data.get("hits", []):
        src = h.get("source") or {}
        loc = (src.get("eventLocations") or [{}])[0]
        lat, lng = loc.get("lat"), loc.get("lng")
        if lat is None or lng is None:
            continue
        d = km(HOME, (lat, lng))
        if d > RADIUS_KM:
            continue
        sch = src.get("eventSchedule") or {}
        start = (sch.get("eventStartUtc") or "")[:10] or None
        out.append({
            "name": (src.get("name") or "Event")[:110],
            "date": start,
            "url": f"https://app.utrsports.net/events/{src.get('id')}",
            "src": "utr",
            "km": round(d),
            "where": loc.get("cityName") or loc.get("display") or "",
            "utrMin": src.get("utrMin"), "utrMax": src.get("utrMax"),
            "regEnd": (sch.get("registrationEndUtc") or "")[:10] or None,
        })
    return out

# ---------- Tennis Australia (needs a browser) ----------
_GEO = {}

def geocode(place):
    """Suburb -> lat/lng via OpenStreetMap, cached for the run."""
    if not place or place in _GEO:
        return _GEO.get(place)
    q = urllib.parse.urlencode({"q": f"{place}, Australia", "format": "json", "limit": 1,
                                "addressdetails": 1})
    try:
        req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}",
                                     headers={"User-Agent": "AdvantageApp/1.0 (tennis team app)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            hits = json.loads(r.read().decode())
        if hits and "Victoria" in (hits[0].get("display_name") or ""):
            _GEO[place] = (float(hits[0]["lat"]), float(hits[0]["lon"]))
        else:
            _GEO[place] = None
    except Exception:
        _GEO[place] = None
    return _GEO[place]


def ta_events():
    """Read the tournament cards: name, venue and DD/MM/YYYY dates are all in the card text."""
    from playwright.sync_api import sync_playwright
    WINDOWS = [("2026-11-26", "2027-02-28"), ("2027-03-01", "2027-06-30")]
    found = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1280, "height": 1600})
        for start_d, end_d in WINDOWS:
            url = ("https://tournaments.tennis.com.au/find/tournament"
                   f"?DateFilterType=0&StartDate={start_d}&EndDate={end_d}&Distance=25")
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=90000)
                pg.wait_for_timeout(7000)
                cards = pg.eval_on_selector_all("a[href*='tournament?id=']", """els => els.map(e => ({
                    href: e.href,
                    card: (e.closest('li,div,article')?.innerText || '').trim()
                }))""")
            except Exception as e:
                print("TA list failed:", type(e).__name__)
                continue
            for c in cards:
                gid = re.search(r"id=([0-9A-Fa-f-]{36})", c["href"])
                if not gid or gid.group(1) in found:
                    continue
                lines = [l.strip() for l in c["card"].split("\n") if l.strip()]
                if not lines:
                    continue
                name = lines[0][:110]
                venue = ""
                for l in lines[1:3]:
                    if "|" in l:
                        venue = l.split("|")[-1].strip()
                        break
                dm = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", c["card"])
                date = None
                if dm:
                    try:
                        date = datetime.date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1))).isoformat()
                    except ValueError:
                        date = None
                if not date:
                    continue
                found[gid.group(1)] = {"name": name, "date": date, "url": c["href"],
                                       "src": "ta", "km": None, "where": venue or "Melbourne"}
        b.close()
    kept = []
    for e in found.values():
        time.sleep(1.1)
        pt = geocode(e["where"])
        if not pt:
            continue
        d = km(HOME, pt)
        if d > RADIUS_KM:
            continue
        e["km"] = round(d)
        kept.append(e)
    print("TA within radius:", len(kept), "of", len(found))
    return kept

today = datetime.date.today().isoformat()
events = [e for e in (utr_events() + ta_events()) if e["date"] and e["date"] >= today]
events.sort(key=lambda e: (e["date"], e["src"] != "utr", e["name"]))

out = {"generated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
       "count": len(events),
       "utr": sum(1 for e in events if e["src"] == "utr"),
       "ta": sum(1 for e in events if e["src"] == "ta"),
       "events": events}
pathlib.Path("events.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"{len(events)} events: {out['utr']} UTR, {out['ta']} TA")
for e in events[:5]:
    print("  ", e["date"], e["src"], (e["name"] or "<blank>")[:60])
