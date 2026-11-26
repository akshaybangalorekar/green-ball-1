"""Harvest junior tournament events near Carnegie 3163 from Tennis Australia and UTR."""
import json, re, urllib.request, pathlib, datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvantageApp/1.0)"}

def get(url, timeout=70):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        return f"ERR {type(e).__name__}"

MON = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}

def parse_date(txt, year_hint=None):
    txt = txt.strip()
    m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s*(\d{4})?", txt)
    if not m:
        return None
    d, mon = int(m.group(1)), MON.get(m.group(2).lower()[:3])
    if not mon:
        return None
    y = int(m.group(3)) if m.group(3) else (year_hint or datetime.date.today().year)
    try:
        return datetime.date(y, mon, d).isoformat()
    except ValueError:
        return None

# ---------- Tennis Australia ----------
TA_WINDOWS = [("2026-11-26", "2027-02-28"), ("2027-03-01", "2027-06-30")]
ta = {}
for start, end in TA_WINDOWS:
    for page in range(1, 5):
        url = ("https://tournaments.tennis.com.au/find/tournament"
               f"?DateFilterType=0&StartDate={start}&EndDate={end}&Distance=25&page={page}")
        txt = get("https://r.jina.ai/" + url)
        if txt.startswith("ERR"):
            break
        rows = re.findall(r"\[([^\]]{8,140})\]\((https://tournaments\.tennis\.com\.au/sport/tournament\?id=[^\)\s]+)\)", txt)
        new = 0
        for label, link in rows:
            if link in ta:
                continue
            dm = re.search(r"(\d{1,2}\s+[A-Za-z]{3}[a-z]*\s*\d{4})", label)
            date = parse_date(dm.group(1)) if dm else None
            name = re.sub(r"^\d{1,2}\s+[A-Za-z]{3}[a-z]*\s*\d{4}\s*[•·-]?\s*", "", label).strip()
            if len(name) < 6:
                continue
            ta[link] = {"name": name[:110], "date": date, "url": link, "src": "ta"}
            new += 1
        if not new:
            break

# ---------- UTR ----------
utr = {}
utr_url = ("https://app.utrsports.net/search?type=events&sportTypes=tennis"
           "&eventState=open_registration&utrMin=1&utrMax=4&utrType=verified"
           "&distance=25mi&latitude=-37.8447&longitude=145.0694")
utxt = get("https://r.jina.ai/" + utr_url)
if not utxt.startswith("ERR"):
    for label, link in re.findall(r"\[([^\]]{10,200})\]\((https://app\.utrsports\.net/events/\d+)\)", utxt):
        if "Australia" not in label:
            continue
        if link in utr:
            continue
        name = label.split("•")[0].strip()[:110]
        utr[link] = {"name": name, "date": None, "url": link, "src": "utr"}

# ---------- filter and sort ----------
today = datetime.date.today().isoformat()
events = [e for e in list(ta.values()) + list(utr.values())
          if not e["date"] or e["date"] >= today]
JUNIOR = re.compile(r"\b(jds|jc|j125|j250|j300|j500|junior|juniors|12u|14u|10u|boys|girls)\b", re.I)
def score(e):
    s = 0
    if JUNIOR.search(e["name"]): s += 3
    if re.search(r"jds|jc\b", e["name"], re.I): s += 2
    if e["src"] == "utr": s += 1
    return s
events.sort(key=lambda e: (e["date"] or "9999", -score(e)))

out = {"generated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
       "count": len(events), "events": events}
pathlib.Path("events.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"{len(events)} events ({len(ta)} TA, {len(utr)} UTR)")
