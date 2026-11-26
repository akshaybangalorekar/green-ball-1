"""Harvest junior tournaments near Carnegie 3163 from UTR and Tennis Australia."""
import json, re, math, pathlib, datetime, urllib.request

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
        })
    return out

# ---------- Tennis Australia (needs a browser) ----------
def ta_events():
    from playwright.sync_api import sync_playwright
    WINDOWS = [("2026-11-26", "2027-02-28"), ("2027-03-01", "2027-06-30")]
    MONTHS = dict(jan=1, feb=2, mar=3, apr=4, may=5, jun=6, jul=7, aug=8, sep=9, oct=10, nov=11, dec=12)
    found = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1280, "height": 1600})
        for start, end in WINDOWS:
            url = ("https://tournaments.tennis.com.au/find/tournament"
                   f"?DateFilterType=0&StartDate={start}&EndDate={end}&Distance=25")
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=90000)
                pg.wait_for_timeout(7000)
                cards = pg.eval_on_selector_all("a[href*='tournament?id=']",
                    "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim()}))")
            except Exception as e:
                print("TA list failed:", type(e).__name__)
                continue
            for c in cards:
                gid = re.search(r"id=([0-9A-Fa-f-]{36})", c["href"])
                if not gid or gid.group(1) in found:
                    continue
                found[gid.group(1)] = {"name": (c["text"] or "").split("\n")[0][:110], "url": c["href"]}
        for e in found.values():
            try:
                pg.goto(e["url"], wait_until="domcontentloaded", timeout=60000)
                pg.wait_for_timeout(2500)
                txt = pg.inner_text("body")[:6000]
                html = pg.content()
                title = pg.title()
            except Exception:
                continue
            # name: page title, minus the site suffix
            nm = re.split(r"\s+[–|-]\s+Tennis Australia", title)[0].strip()
            if len(nm) > 5:
                e["name"] = nm[:110]
            # date: structured data first
            for pat in (r'"startDate"\s*:\s*"(\d{4}-\d{2}-\d{2})',
                        r'"start_date"\s*:\s*"(\d{4}-\d{2}-\d{2})',
                        r'"eventStartDate"\s*:\s*"(\d{4}-\d{2}-\d{2})'):
                m = re.search(pat, html)
                if m:
                    e["date"] = m.group(1); break
            if not e.get("date"):
                m = re.search(r"(?:Dates?|When)[^\n]{0,40}?(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})", txt, re.I)
                if m:
                    try:
                        e["date"] = datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1))).isoformat()
                    except ValueError:
                        pass
        b.close()
    out = []
    for e in found.values():
        if not e.get("date"):
            continue
        out.append({"name": e["name"], "date": e["date"], "url": e["url"], "src": "ta",
                    "km": None, "where": "Melbourne"})
    return out

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
