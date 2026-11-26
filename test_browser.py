import re, sys
from playwright.sync_api import sync_playwright

def probe(page, url, pattern, wait_ms=6000):
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(wait_ms)
    html = page.content()
    hits = re.findall(pattern, html)
    return len(set(hits)), html

with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1280, "height": 1600})

    ta_url = ("https://tournaments.tennis.com.au/find/tournament"
              "?DateFilterType=0&StartDate=2026-11-26&EndDate=2027-02-28&Distance=25")
    n_ta, html = probe(pg, ta_url, r"tournament\?id=([0-9A-Fa-f-]{36})")
    print("TA links:", n_ta)
    if n_ta:
        names = re.findall(r'"tournamentName"\s*:\s*"([^"]{5,90})"', html)[:5]
        print("TA sample:", names)

    utr_url = ("https://app.utrsports.net/search?type=events&sportTypes=tennis"
               "&eventState=open_registration&utrMin=1&utrMax=4&utrType=verified&distance=25mi")
    n_utr, uhtml = probe(pg, utr_url, r"events/(\d+)", 8000)
    print("UTR links:", n_utr)
    aus = len(re.findall(r"Australia", uhtml))
    print("UTR mentions of Australia:", aus)
    b.close()
