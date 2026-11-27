import json, re, urllib.request
from playwright.sync_api import sync_playwright
d = json.loads(urllib.request.urlopen("https://raw.githubusercontent.com/akshaybangalorekar/green-ball-1/main/events.json", timeout=30).read())
inv = [e for e in d["events"] if e.get("dropped") and "invitation" in e["dropped"].lower()][:2]
print("checking", len(inv), "invitational-dropped events")
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page()
    for e in inv:
        pg.goto(e["url"], wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)
        txt = pg.inner_text("body")
        ages = sorted({int(a) for a in re.findall(r"\b(?:U|Under\s?)(\d{2})\b", txt)})
        print("==", e["name"][:50], "| ages:", ages)
        for m in re.finditer(r"invitation", txt, re.I):
            s = max(0, m.start()-70)
            print("   ...", txt[s:m.end()+70].replace("\n", " ")[:150])
    b.close()
