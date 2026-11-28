import json, re, urllib.request
from playwright.sync_api import sync_playwright
d = json.loads(urllib.request.urlopen("https://raw.githubusercontent.com/akshaybangalorekar/green-ball-1/main/events.json", timeout=30).read())
ta = [e for e in d["events"] if e["src"] == "ta" and not e.get("dropped")][:2]
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page()
    for e in ta:
        print("==", e["name"][:50])
        pg.goto(e["url"], wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)
        try:
            pg.click("text=Events", timeout=5000); pg.wait_for_timeout(2500)
        except Exception as ex:
            print("  click failed:", type(ex).__name__)
        txt = pg.inner_text("body")
        i = txt.lower().find("event")
        print("  --- snippet ---")
        print("  " + txt[max(0,i-200):i+900].replace("\n", " | ")[:1000])
    b.close()
