import re, json
from playwright.sync_api import sync_playwright

calls = []
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"])
    ctx = b.new_context(geolocation={"latitude": -37.8447, "longitude": 145.0694},
                        permissions=["geolocation"], viewport={"width": 1280, "height": 1500})
    pg = ctx.new_page()
    pg.on("request", lambda r: calls.append(r.url) if "/v2/search/events" in r.url else None)
    pg.goto("https://app.utrsports.net/search?type=events&sportTypes=tennis", wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(8000)
    # set the location through the UI
    for sel in ["input[placeholder*='ocation']", "input[type='search']", "input[placeholder*='earch']"]:
        el = pg.query_selector(sel)
        if el:
            el.click()
            el.type("Carnegie", delay=80)
            pg.wait_for_timeout(3000)
            try:
                pg.keyboard.press("ArrowDown"); pg.keyboard.press("Enter")
            except Exception:
                pass
            pg.wait_for_timeout(9000)
            break
    html = pg.content()
    print("event links rendered:", len(set(re.findall(r"events/(\d+)", html))))
    b.close()

print("event-search calls:", len(calls))
for u in list(dict.fromkeys(calls))[:4]:
    print("URL:", u[:400])
