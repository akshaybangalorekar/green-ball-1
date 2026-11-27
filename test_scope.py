import json, re, urllib.request
from playwright.sync_api import sync_playwright
d = json.loads(urllib.request.urlopen("https://raw.githubusercontent.com/akshaybangalorekar/green-ball-1/main/events.json", timeout=30).read())
def find(f):
    for e in d["events"]:
        if f.lower() in e["name"].lower(): return e
KEILOR, HUME = find("Keilor"), find("Hume Tennis HEAD Discovery Final")
SELS = ["main", "[class*='event']", "[class*='detail']", "[class*='tab']", "[class*='content']", "section"]
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page()
    for label, e in (("KEILOR", KEILOR), ("HUME", HUME)):
        if not e: continue
        pg.goto(e["url"], wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3500)
        print("==", label)
        for sel in SELS:
            try:
                r = pg.evaluate("""(sel) => {
                  const els = [...document.querySelectorAll(sel)];
                  const best = els.map(e => e.innerText || "").sort((a,b)=>b.length-a.length)[0] || "";
                  return {len: best.length, ages: /\b(?:U|Under\s?)(1[02468])\b/.test(best),
                          invite: /do not sign up until|by invitation only/i.test(best),
                          word: /invitational/i.test(best)};
                }""", sel)
                print(f"   {sel:24} len={r['len']:6} ages={r['ages']} explicitInvite={r['invite']} word={r['word']}")
            except Exception as ex:
                print(f"   {sel:24} ERR {type(ex).__name__}")
    b.close()
