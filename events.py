"""Harvest junior tournaments near Carnegie 3163 with a real browser."""
import json, re, pathlib, datetime
from playwright.sync_api import sync_playwright

WINDOWS = [("2026-11-26", "2027-02-28"), ("2027-03-01", "2027-06-30")]
JUNIOR = re.compile(r"\b(jds|jc|j125|j250|j300|j500|junior|juniors|12u|14u|10u|boys|girls)\b", re.I)

def scrape_ta(page):
    out = {}
    for start, end in WINDOWS:
        url = ("https://tournaments.tennis.com.au/find/tournament"
               f"?DateFilterType=0&StartDate={start}&EndDate={end}&Distance=25")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(7000)
            cards = page.eval_on_selector_all("a[href*='tournament?id=']", """els => els.map(e => ({
                href: e.href,
                text: (e.innerText || '').trim(),
                near: (e.closest('div,li,article') ? e.closest('div,li,article').innerText : '').slice(0, 300)
            }))""")
        except Exception as e:
            print("TA error:", type(e).__name__)
            continue
        for c in cards:
            gid = re.search(r"id=([0-9A-Fa-f-]{36})", c["href"])
            if not gid:
                continue
            key = gid.group(1)
            if key in out:
                continue
            blob = (c["text"] + " " + c["near"]).replace("\n", " ")
            dm = re.search(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(\d{4})?", blob, re.I)
            date = None
            if dm:
                months = dict(jan=1, feb=2, mar=3, apr=4, may=5, jun=6, jul=7, aug=8, sep=9, oct=10, nov=11, dec=12)
                y = int(dm.group(3)) if dm.group(3) else int(start[:4])
                try:
                    date = datetime.date(y, months[dm.group(2).lower()[:3]], int(dm.group(1))).isoformat()
                except ValueError:
                    date = None
            name = (c["text"] or "").strip().split("\n")[0][:110]
            if len(name) < 6:
                continue
            out[key] = {"name": name, "date": date, "url": c["href"], "src": "ta", "near": blob[:160]}
    return list(out.values())

with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1280, "height": 1600})
    ta = scrape_ta(pg)
    b.close()

today = datetime.date.today().isoformat()
events = [e for e in ta if not e["date"] or e["date"] >= today]
events.sort(key=lambda e: (e["date"] or "9999", 0 if JUNIOR.search(e["name"]) else 1))

out = {"generated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
       "count": len(events), "events": events}
pathlib.Path("events.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"{len(events)} events harvested from Tennis Australia")
