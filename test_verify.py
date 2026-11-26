import json, re, urllib.request
from playwright.sync_api import sync_playwright

data = json.loads(urllib.request.urlopen(
    "https://raw.githubusercontent.com/akshaybangalorekar/green-ball-1/main/events.json",
    timeout=30).read())
evs = data["events"]
print("checking", len(evs), "events")
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page()
    for e in evs:
        try:
            pg.goto(e["url"], wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(2500)
            txt = pg.inner_text("body")
        except Exception as ex:
            print("ERR", e["name"][:40], type(ex).__name__); continue
        ages = sorted(set(re.findall(r"\b(?:U|Under\s?)(\d{2})\b", txt)))
        ball = "green" if re.search(r"green ball", txt, re.I) else (
               "yellow" if re.search(r"yellow ball", txt, re.I) else "?")
        wc = bool(re.search(r"wheelchair|walking|police|fire games", txt, re.I))
        print(f"{e['src']:3} {e['date']} ages={','.join(ages) or '-':9} ball={ball:6} "
              f"excl={wc} {e['name'][:42]}")
    b.close()
