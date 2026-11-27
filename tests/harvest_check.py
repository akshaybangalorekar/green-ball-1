"""Regression test for the eligibility rule (v2). Runs the real verify_on_page against known URLs."""
import json, re, sys, urllib.request
from playwright.sync_api import sync_playwright

src = open("events.py").read()
prefix = src[:src.index("raw_utr = utr_events()")]     # everything except the harvest run itself
ns = {}
exec(compile(prefix, "events.py", "exec"), ns)
verify = ns["verify_on_page"]

data = json.loads(urllib.request.urlopen(
    "https://raw.githubusercontent.com/akshaybangalorekar/green-ball-1/main/events.json", timeout=30).read())

def find(frag):
    for e in data["events"]:
        if frag.lower() in e["name"].lower():
            return dict(e)
    return None

CASES = [
    ("Keilor Park",           True,  "junior divisions listed"),
    ("Hume Tennis HEAD Discovery Final", False, "invitational, no junior draw"),
    ("Rosanna Tennis Club",   False, "1 Point Slam, 12+"),
    ("J125",                  True,  "ranked junior event"),
    ("Lauriston",             True,  "junior event"),
]

fails = 0
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page()
    for frag, should_pass, why in CASES:
        e = find(frag)
        if not e:
            print(f"SKIP  {frag} (not in the current list)"); continue
        e, reason = verify(pg, e)
        ok = (reason is None) == should_pass
        print(f"{'PASS' if ok else 'FAIL'}  {frag:34} expected={'eligible' if should_pass else 'dropped'}  got={reason or 'eligible'}   ({why})")
        if not ok: fails += 1
    b.close()
print(f"\n{fails} failure(s) of {len(CASES)} cases")
sys.exit(1 if fails else 0)
