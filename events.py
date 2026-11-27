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
def find_band(obj):
    """Any numeric utrMin/utrMax anywhere in the event, including inside divisions."""
    lo = hi = None
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            for k, v in o.items():
                kl = k.lower()
                if isinstance(v, (int, float)) and "utr" in kl:
                    if "min" in kl:
                        lo = v if lo is None else min(lo, v)
                    elif "max" in kl:
                        hi = v if hi is None else max(hi, v)
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(o, list):
            stack.extend(o)
    return lo, hi


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
        _b = find_band(src)
        sch = src.get("eventSchedule") or {}
        start = (sch.get("eventStartUtc") or "")[:10] or None
        out.append({
            "name": (src.get("name") or "Event")[:110],
            "date": start,
            "url": f"https://app.utrsports.net/events/{src.get('id')}",
            "src": "utr",
            "km": round(d),
            "where": loc.get("cityName") or loc.get("display") or "",
            "utrMin": _b[0], "utrMax": _b[1],
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
    # one month at a time, so a month's results always fit on the first page
    WINDOWS = []
    cur = datetime.date.today()
    for _ in range(9):
        first = cur.replace(day=1)
        nxt = (first + datetime.timedelta(days=32)).replace(day=1)
        WINDOWS.append((max(first, datetime.date.today()).isoformat(),
                        (nxt - datetime.timedelta(days=1)).isoformat()))
        cur = nxt
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

# --- eligibility: junior, enterable by an 11-year-old ---
BAD = re.compile(r"wheelchair|police|fire games|veteran|senior|invitational|walking tennis|"
                 r"blind|deaf|special olympics|masters|\b1[68]u\b|\bopen age\b", re.I)
GOOD = re.compile(r"\bjds\b|\bjc\b|j\d{3}|junior|juniors|\b1[024]u\b|\b\d{2}u\b|boys|girls|"
                  r"matchplay|match play|green ball|coloured ball|hot shots|development", re.I)
GREEN = re.compile(r"green ball|green-ball|coloured ball|red ball|orange ball|hot shots", re.I)

AGE = 11          # his age now
ADAPTIVE = re.compile(r"wheelchair|walking tennis|blind|deaf|all abilities|para[- ]|"
                      r"special olympics|intellectual|police|fire games|veterans|masters", re.I)
BAD_PAGE = re.compile(r"members only|invitation only|invitational|1 point slam|wheelchair|"
                      r"walking tennis|police|fire games|veterans|masters", re.I)

def verify_on_page(pg, e):
    """Read the event's own block. Include only if a junior division he can enter is listed."""
    try:
        pg.goto(e["url"], wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(2200)
        block = pg.inner_text("body")[:8000]
    except Exception as ex:
        e["unverified"] = True
        return e, None          # a technical failure must not delete an event
    ages = sorted({int(a) for a in re.findall(r"\b(?:U|Under\s?)(\d{2})\b", block)})
    over = re.search(r"(\d{1,2})\s*(?:years?|yrs?)\s*(?:and|&)\s*over", block, re.I)
    min_age = int(over.group(1)) if over else None
    e["ages"] = ages
    e["ball"] = ("green" if re.search(r"green ball", block, re.I)
                 else "yellow" if re.search(r"yellow ball", block, re.I) else "?")
    # invitation language means he cannot enter, whatever divisions exist
    invite = re.search(r"invitation only|invitational|do not sign up until|by invitation", block, re.I)
    if invite:
        return e, "by invitation only — " + invite.group(0).lower()
    # a published junior division wins over members-only wording
    if {12, 14, 16, 18} & set(ages):
        if re.search(r"members only", block, re.I):
            e["note"] = "members only — check before entering"
        return e, None
    bad = BAD_PAGE.search(block)
    if bad:
        return e, "page says: " + bad.group(0)
    if min_age is not None and AGE < min_age:
        return e, f"only {min_age} years and over"
    if not ages and GOOD.search(e["name"]):
        return e, None          # no division published yet, but it is a junior event
    if ages:
        return e, "only a " + "/".join(str(a) for a in ages) + "-and-under draw"
    return e, "no age groups published"


def dedupe_key(e):
    return (re.sub(r"[^a-z0-9]", "", e["name"].lower())[:26], e["date"])


raw_utr = utr_events()
raw_ta = ta_events()
pool = []
for e in raw_utr + raw_ta:
    if not e["date"]:
        print("DROP no date:", e["name"][:50]); continue
    if e["date"] < today:
        print("DROP past:", e["date"], e["name"][:50]); continue
    pool.append(e)
kept = {}
from playwright.sync_api import sync_playwright
with sync_playwright() as _pw:
    _b = _pw.chromium.launch(args=["--no-sandbox"])
    _pg = _b.new_page()
    for e in sorted(pool, key=lambda x: x["src"] != "utr"):
        e, why = verify_on_page(_pg, e)
        if why:
            if ADAPTIVE.search(e["name"]) or ADAPTIVE.search(str(why)):
                print(f"HIDE adaptive: {e['name'][:50]}")
                continue
            e["dropped"] = why
            print(f"TAGGED dropped ({why}):", e["name"][:48])
        kept.setdefault(dedupe_key(e), e)
    _b.close()
events = list(kept.values())
events.sort(key=lambda e: (e["date"], e["src"] != "utr", e["name"]))  # by date, merged
print("after eligibility + dedupe:", len(events), "of", len(pool))

out = {"generated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
       "count": len(events),
       "dropped": sum(1 for e in events if e.get("dropped")),
       "utr": sum(1 for e in events if e["src"] == "utr"),
       "ta": sum(1 for e in events if e["src"] == "ta"),
       "events": events}
pathlib.Path("events.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"{len(events)} events: {out['utr']} UTR, {out['ta']} TA")
for e in events[:5]:
    print("  ", e["date"], e["src"], (e["name"] or "<blank>")[:60])
