import re
from playwright.sync_api import sync_playwright

seen = []
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"])
    ctx = b.new_context(geolocation={"latitude": -37.8447, "longitude": 145.0694},
                        permissions=["geolocation"],
                        viewport={"width": 1280, "height": 1400})
    pg = ctx.new_page()
    pg.on("request", lambda r: seen.append(r.url) if re.search(r"/api/|graphql|search|events", r.url) else None)
    pg.goto("https://app.utrsports.net/events", wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(9000)
    # try to set a location the way a person would
    try:
        box = pg.query_selector("input[placeholder*='ocation'], input[placeholder*='earch'], input[type='search']")
        if box:
            box.click(); box.type("Carnegie, Victoria, Australia", delay=60)
            pg.wait_for_timeout(2500)
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(7000)
    except Exception as e:
        print("ui:", type(e).__name__)
    txt = pg.inner_text("body")
    print("page mentions Australia:", txt.count("Australia"))
    print("event links on page:", len(set(re.findall(r"events/(\d+)", pg.content()))))
    b.close()

api = [u for u in dict.fromkeys(seen) if "utrsports.net" in u]
print("API calls seen:", len(api))
for u in api[:25]:
    print("  ", u[:190])
