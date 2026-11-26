import re
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page()
    pg.goto("https://tournaments.tennis.com.au/find/tournament?DateFilterType=0&StartDate=2026-11-26&EndDate=2027-02-28&Distance=25",
            wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(7000)
    cards = pg.eval_on_selector_all("a[href*='tournament?id=']",
        "els => els.slice(0,3).map(e => ({href:e.href, text:(e.innerText||'').trim(), card:(e.closest('li,div,article')?.innerText||'').slice(0,200)}))")
    print("cards:", len(cards))
    for c in cards:
        print("TEXT:", repr(c["text"])[:120])
        print("CARD:", repr(c["card"])[:200])
    if cards:
        pg.goto(cards[0]["href"], wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(3000)
        print("TITLE:", pg.title()[:120])
        html = pg.content()
        for pat in [r'"(startDate|start_date|eventStartDate|tournamentStartDate|dateFrom)"\s*:\s*"?([0-9T:\-]{8,25})',
                    r'(20\d\d-[01]\d-[0-3]\d)']:
            print("PAT", pat[:28], "->", re.findall(pat, html)[:4])
        txt = pg.inner_text("body")
        print("BODYTXT:", repr(txt[:400]))
    b.close()
