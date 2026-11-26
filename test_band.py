import re, json, urllib.request
from playwright.sync_api import sync_playwright

ev = json.loads(urllib.request.urlopen(
    "https://raw.githubusercontent.com/akshaybangalorekar/green-ball-1/main/events.json", timeout=30).read())["events"]
utr = [e for e in ev if e["src"] == "utr"][:1]
ta  = [e for e in ev if e["src"] == "ta"][:1]

calls = []
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page()
    pg.on("request", lambda r: calls.append(r.url) if re.search(r"/api/|division|event", r.url) else None)

    for e in utr:
        print("== UTR:", e["name"][:50])
        pg.goto(e["url"], wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(9000)
        txt = pg.inner_text("body")
        hits = [m.group(0) for m in re.finditer(r"UTR[^\n]{0,40}", txt)][:6]
        print("  page UTR mentions:", hits)
        for u in list(dict.fromkeys([c for c in calls if "utrsports" in c]))[:8]:
            print("  XHR:", u[:150])

    for e in ta:
        print("== TA:", e["name"][:50])
        pg.goto(e["url"], wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
        txt = pg.inner_text("body")
        print("  UTR on TA page:", [m.group(0) for m in re.finditer(r"UTR[^\n]{0,40}", txt)][:5])
        print("  divisions:", [m.group(0) for m in re.finditer(r"(U1[02468]|12U|14U)[^\n]{0,30}", txt)][:5])
    b.close()
