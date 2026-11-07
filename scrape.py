#!/usr/bin/env python3
"""
Refresh data.json for the East Malvern Green Ball 1 team app.

Scrapes the Waverley Tennis (WDTA) competition site on TROLS, which is the
official record for ladders, results and fixtures:

    https://trols.org.au/wdta/ladders.php
    https://trols.org.au/wdta/results.php
    https://trols.org.au/wdta/fixture.php

Run manually:   python scrape.py
In CI:          .github/workflows/update-data.yml (daily)

Only the standard library is used, so there is nothing to install.

If anything goes wrong the script exits non-zero WITHOUT touching data.json,
so a bad scrape never replaces good data.
"""

import json
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://trols.org.au/wdta"
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data.json"

# ---- what to follow -------------------------------------------------------
CLUB = "East Malvern"
COMPETITION_LABEL = "Sunday AM"          # as shown in the TROLS competition dropdown
SECTION_LABEL = "Open Triples Green Ball 1"

# Fallbacks if the dropdowns cannot be parsed (they are built by JavaScript
# on the live site, so this is the normal path for WDTA).
DAYTIME_FALLBACK = "UA"
SECTION_FALLBACK = "UA037"
SECTION_SCAN_LIMIT = 90
SCAN_FROM = 240
SCAN_TO = 360                  # how many section codes to try before giving up

UA = "Mozilla/5.0 (compatible; em-tennis-ladder/1.0)"


def fetch(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


# ---- tiny HTML table reader ----------------------------------------------
class TableReader(HTMLParser):
    """Collects every <table> as rows of cells.

    TROLS is old PHP-generated HTML and frequently omits closing </td> and
    </tr> tags, so cells and rows are also closed implicitly when the next
    one starts, and again at </table>.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._t = None
        self._row = None
        self._cell = None
        self._href = None

    def _close_cell(self):
        if self._cell is not None and self._row is not None:
            self._cell["text"] = re.sub(r"\s+", " ", self._cell["text"]).strip()
            self._row.append(self._cell)
        self._cell = None
        self._href = None

    def _close_row(self):
        self._close_cell()
        if self._row is not None and self._t is not None and self._row:
            self._t.append(self._row)
        self._row = None

    def _close_table(self):
        self._close_row()
        if self._t:
            self.tables.append(self._t)
        self._t = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._close_table()
            self._t = []
        elif tag == "tr":
            self._close_row()
            if self._t is not None:
                self._row = []
        elif tag in ("td", "th"):
            self._close_cell()
            if self._row is not None:
                self._cell = {"text": "", "href": None, "tag": tag}
        elif tag == "a" and self._cell is not None:
            self._href = a.get("href") or ""
        elif tag == "br" and self._cell is not None:
            self._cell["text"] += " "

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._close_cell()
        elif tag == "tr":
            self._close_row()
        elif tag == "table":
            self._close_table()
        elif tag == "a":
            self._href = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data
            if self._href is not None and self._cell["href"] is None:
                self._cell["href"] = self._href

    def close(self):
        super().close()
        self._close_table()


def tables(html):
    p = TableReader()
    p.feed(html)
    return p.tables


def cells(row):
    return [c["text"] for c in row]


def num(s, default=None):
    m = re.search(r"-?\d+(?:[.,]\d+)?", s or "")
    if not m:
        return default
    return float(m.group(0).replace(",", ""))


def iso_date(s):
    """'11 Oct 26' or '8 Nov 26' -> '2026-10-11'."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\w*\s+(\d{2,4})", s or "")
    if not m:
        return None
    day, mon, yr = m.group(1), m.group(2).title(), m.group(3)
    months = {m: i + 1 for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
    if mon not in months:
        return None
    year = int(yr)
    if year < 100:
        year += 2000
    return f"{year:04d}-{months[mon]:02d}-{int(day):02d}"


# ---- discover the competition + section codes ----------------------------
def find_option_code(html, label_contains):
    """Read <option value="XX">Label</option> pairs, even if the site builds
    them in JavaScript (we try the raw markup first, then inline JS arrays)."""
    for value, label in re.findall(
            r'<option[^>]*value="([^"]+)"[^>]*>([^<]+)</option>', html, re.I):
        if label_contains.lower() in label.lower():
            return value.strip()
    # inline JS: ["AA","Saturday AM - Summer 26/27"] or 'AA': 'Saturday AM'
    for value, label in re.findall(
            r'["\']([A-Z]{2}\d{0,3})["\']\s*[,:]\s*["\']([^"\']{4,60})["\']', html):
        if label_contains.lower() in label.lower():
            return value
    return None


def resolve_codes():
    daytime = None
    try:
        daytime = find_option_code(fetch(f"{BASE}/ladders.php"), COMPETITION_LABEL)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! competition lookup failed ({exc})")
    if not daytime:
        daytime = DAYTIME_FALLBACK
        print(f"  · using fallback competition code {daytime}")

    section = None
    try:
        page = fetch(f"{BASE}/ladders.php?daytime={daytime}&style=")
        section = find_option_code(page, SECTION_LABEL)
    except Exception:  # noqa: BLE001
        pass

    if not section:
        # Scan section codes until the ladder title matches.
        for i in range(1, SECTION_SCAN_LIMIT + 1):
            code = f"{daytime}{i:03d}"
            try:
                page = fetch(f"{BASE}/ladders.php?daytime={daytime}&section={code}&style=")
            except Exception:  # noqa: BLE001
                continue
            if SECTION_LABEL.lower() in page.lower():
                section = code
                print(f"  · found section {code} by scan")
                break

    if not section:
        section = SECTION_FALLBACK
        print(f"  · using fallback section code {section}")
    return daytime, section


# ---- parsers --------------------------------------------------------------
def parse_ladder(html):
    rows = []
    for t in tables(html):
        head = " ".join(cells(t[0])).lower() if t else ""
        if "pts" not in head or "%" not in head:
            continue
        for r in t[1:]:
            c = [x for x in cells(r) if x.strip()]
            if len(c) < 3:
                continue
            pts, p = num(c[-2]), num(c[-1])
            if pts is None or p is None:
                continue
            rows.append({"team": c[0], "pts": pts, "pct": p})
        if rows:
            break
    return rows


def parse_results(html):
    """Returns [{round, date, washout, matches:[...]}] newest first.

    A match row looks like:
        Home | Pts | S | G | (empty) | Pts | S | G | Away
    """
    rounds, current = [], None
    for t in tables(html):
        flat = " ".join(" ".join(cells(r)) for r in t).lower()
        if "home team" not in flat:
            continue
        for r in t:
            raw = cells(r)
            joined = " ".join(raw).strip()
            if not joined:
                continue
            m = re.search(r"Rd\.?\s*(\d+)", joined, re.I)
            if m:
                current = {"round": int(m.group(1)), "date": iso_date(joined),
                           "washout": False, "matches": []}
                rounds.append(current)
                continue
            if current is None:
                continue
            if "home team" in joined.lower():
                continue

            home, away = raw[0].strip(), raw[-1].strip()
            if not home or not away:
                continue
            middle = [x for x in raw[1:-1] if x.strip()]
            if not middle:
                continue
            if any("wash" in x.lower() for x in middle):
                current["matches"].append({"home": home, "away": away, "washout": True})
                current["washout"] = True
                continue
            if len(middle) < 6:
                continue
            current["matches"].append({
                "home": home,
                "homePts": num(middle[0], 0.0), "homeSets": int(num(middle[1], 0) or 0),
                "homeGames": int(num(middle[2], 0) or 0),
                "away": away,
                "awayPts": num(middle[3], 0.0), "awaySets": int(num(middle[4], 0) or 0),
                "awayGames": int(num(middle[5], 0) or 0),
            })
    rounds = [r for r in rounds if r["matches"]]
    rounds.sort(key=lambda r: r["round"], reverse=True)
    return rounds


def team_codes(html, daytime, limit=150):
    """Team codes appear as XX123. Prefer ones that sit near the club name."""
    found = []
    for m in re.finditer(r"\b([A-Z]{2}\d{3})\b", html):
        code = m.group(1)
        if not code.startswith(daytime):
            continue
        near_club = CLUB.lower() in html[max(0, m.start() - 400):m.end() + 400].lower()
        found.append((0 if near_club else 1, code))
    seen, out = set(), []
    for _, code in sorted(found):
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out[:limit]


def parse_fixture(html):
    """Returns (fixture rows, section club rows) or (None, None)."""
    fixture, clubs = None, None
    for t in tables(html):
        head = " ".join(cells(t[0])).lower() if t else ""
        if "section information" in head:
            clubs = []
            for r in t[1:]:
                c = cells(r)
                if len(c) >= 3 and c[0].isdigit():
                    melway = re.sub(r"^Melway\s*", "", c[2]).strip()
                    clubs.append({"name": c[1], "melway": melway, "venue": None,
                                  "contact": None, "phone": None})
                elif clubs and len(c) >= 1:
                    blob = " ".join(c)
                    phone = re.search(r"(?:Mob|Ph)\s*:?\s*([\d\s]{8,14})", blob)
                    name = re.search(
                        r"Club Contact\s*:?\s*([A-Za-z' .-]+?)(?=\s*(?:Mob|Ph|$))", blob)
                    if clubs[-1]["venue"] is None and len(blob) > 12:
                        clubs[-1]["venue"] = re.sub(r"Club Contact.*$", "", blob).strip(" |")
                    if name:
                        clubs[-1]["contact"] = name.group(1).strip()
                    if phone:
                        clubs[-1]["phone"] = re.sub(r"\s+", " ", phone.group(1)).strip()
        if "fixture for" in head:
            fixture = []
            for r in t[1:]:
                c = cells(r)
                if len(c) >= 4 and re.fullmatch(r"\d+", c[0].strip()):
                    fixture.append({"round": int(c[0]), "date": iso_date(c[1]),
                                    "home": c[2], "away": c[3]})
    return fixture, clubs


def check_code(code, daytime, section, valid_teams):
    """Return the fixture page for this team code if it really is our team."""
    try:
        page = fetch(f"{BASE}/fixture.php?daytime={daytime}&section={section}"
                     f"&style=&team={code}&which=2")
    except Exception:  # noqa: BLE001
        return None, None
    if f"fixture for {CLUB}".lower() not in page.lower():
        return None, None
    fixture, _ = parse_fixture(page)
    if not fixture:
        return None, None
    names = {f["home"] for f in fixture} | {f["away"] for f in fixture}
    if valid_teams and not names.issubset(valid_teams | {"Bye", "No Play"}):
        return None, None
    return fixture, page


def find_our_team_code(results_html, daytime, section, valid_teams, cached=None):
    """TROLS fixture pages are keyed by a team code that only appears in the
    page's markup, so probe candidate codes.

    A club can field several teams across the competition, so a code is only
    accepted when every name in its fixture belongs to this section.
    """
    if cached:
        fixture, page = check_code(cached, daytime, section, valid_teams)
        if page:
            print(f"  · {CLUB} team code {cached} (cached)")
            return cached, page
        print(f"  · cached code {cached} no longer valid — searching again")

    candidates = team_codes(results_html, daytime)
    print(f"  · probing {len(candidates)} team codes for {CLUB}")
    for code in candidates:
        fixture, page = check_code(code, daytime, section, valid_teams)
        if page:
            print(f"  · {CLUB} team code {code}")
            return code, page
    # Team codes are opaque and not published on any page we can read, so fall
    # back to a bounded scan. Only runs once: the hit is cached in data.json.
    print(f"  · scanning team codes {SCAN_FROM}-{SCAN_TO} for {CLUB}")
    for n in range(SCAN_FROM, SCAN_TO + 1):
        code = f"{daytime}{n:03d}"
        fixture, page = check_code(code, daytime, section, valid_teams)
        if page:
            print(f"  · {CLUB} team code {code} (found by scan)")
            return code, page
    print(f"  ! no team code matched this section")
    return None, None


def enrich(ladder, results):
    """Add played / won / lost / sets / games to ladder rows from results."""
    stats = {}
    for r in results:
        for m in r["matches"]:
            if m.get("washout"):
                continue
            for side, other in (("home", "away"), ("away", "home")):
                name = m[side]
                s = stats.setdefault(name, {"played": 0, "won": 0, "lost": 0,
                                            "sets_for": 0, "sets_against": 0,
                                            "games_for": 0, "games_against": 0})
                s["played"] += 1
                mine, theirs = m[f"{side}Pts"], m[f"{other}Pts"]
                s["won" if mine > theirs else "lost"] += 1
                s["sets_for"] += m[f"{side}Sets"]
                s["sets_against"] += m[f"{other}Sets"]
                s["games_for"] += m[f"{side}Games"]
                s["games_against"] += m[f"{other}Games"]
    for i, row in enumerate(ladder, start=1):
        row["pos"] = i
        st = stats.get(row["team"], {})
        for k in ("played", "won", "lost", "sets_for", "sets_against", "games_for", "games_against"):
            row[k] = st.get(k, 0)
        row["drawn"] = 0
        if row["team"] == CLUB:
            row["isUs"] = True
    return ladder


def build_draw(fixture):
    draw = []
    for f in fixture or []:
        ours = CLUB in (f["home"], f["away"])
        draw.append({
            "round": f["round"],
            "date": f["date"],
            "opponent": (f["away"] if f["home"] == CLUB else f["home"]) if ours else None,
            "homeAway": ("H" if f["home"] == CLUB else "A") if ours else None,
            "result": None,
        })
    return draw


# ---- main -----------------------------------------------------------------
def debug_pages(daytime, section):
    """Print what the runner actually receives, so a markup change is obvious."""
    for name, url in (
        ("ladders", f"{BASE}/ladders.php?daytime={daytime}&section={section}&style="),
        ("results", f"{BASE}/results.php?daytime={daytime}&section={section}&style="),
    ):
        try:
            html = fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[debug] {name}: FETCH FAILED {exc}")
            continue
        print(f"[debug] {name}: {len(html)} bytes, {html.count('<table')} tables, "
              f"{html.count('<tr')} rows, {html.count('</td>')} closed cells")
        print(f"[debug] {name} head: {html[:300]!r}")
        for i, t in enumerate(tables(html)):
            first = " | ".join(cells(t[0]))[:150] if t else ""
            second = " | ".join(cells(t[1]))[:150] if len(t) > 1 else ""
            print(f"[debug] {name} table{i}: {len(t)} rows :: r0={first!r} :: r1={second!r}")
        if name == "ladders":
            for sel in re.findall(r"<select[^>]*name=\"([^\"]+)\"[^>]*>(.*?)</select>", html, re.S | re.I):
                opts = re.findall(r'<option[^>]*value="([^"]*)"', sel[1])
                print(f"[debug] select name={sel[0]!r} options={len(opts)} sample={opts[:6]}")
            print(f"[debug] codes on ladder page: {sorted(set(re.findall(r'\\b([A-Z]{2}\\d{3})\\b', html)))[:12]}")
            club_url = f"{BASE}/ladders.php?daytime={daytime}&club={CLUB.replace(' ', '+')}&style="
            try:
                ch = fetch(club_url)
                print(f"[debug] club page {len(ch)} bytes, codes="
                      f"{sorted(set(re.findall(r'\\b([A-Z]{2}\\d{3})\\b', ch)))[:12]}")
                print(f"[debug] club page tables: {[(' | '.join(cells(t[0]))[:90]) for t in tables(ch)][:8]}")
            except Exception as exc:  # noqa: BLE001
                print(f"[debug] club page FAILED {exc}")
            pass


def main():
    print(f"Scraping {CLUB} — {COMPETITION_LABEL} / {SECTION_LABEL}")
    daytime, section = resolve_codes()
    print(f"  · competition {daytime}, section {section}")

    if "--debug" in sys.argv:
        debug_pages(daytime, section)

    ladder_html = fetch(f"{BASE}/ladders.php?daytime={daytime}&section={section}&style=")
    results_html = fetch(f"{BASE}/results.php?daytime={daytime}&section={section}&style=")

    ladder = parse_ladder(ladder_html)
    if not ladder:
        raise RuntimeError("no ladder rows parsed")
    results = parse_results(results_html)
    if not results:
        print("  ! no results parsed — keeping ladder only")

    ladder = enrich(ladder, results)

    old = {}
    if DATA_FILE.exists():
        try:
            old = json.loads(DATA_FILE.read_text())
        except Exception:  # noqa: BLE001
            old = {}

    valid_teams = {row["team"] for row in ladder}
    our_code, fixture_html = find_our_team_code(
        results_html, daytime, section, valid_teams, cached=old.get("meta", {}).get("team_code"))
    fixture, clubs = (None, None)
    if fixture_html:
        fixture, clubs = parse_fixture(fixture_html)
        if fixture:
            print(f"  · fixture: {len(fixture)} rounds")
        if clubs:
            print(f"  · section: {len(clubs)} clubs")

    loaded = re.search(r"Loaded:?\s*([0-9]{1,2}\w{2}\s+\w+\s+\d{2,4}[^<]*)", ladder_html)
    loaded_txt = loaded.group(1).strip() if loaded else None

    meta = old.get("meta", {})
    meta.update({
        "club": CLUB,
        "competition": COMPETITION_LABEL,
        "season": meta.get("season", "Summer 26/27"),
        "section": SECTION_LABEL,
        "daytime_code": daytime,
        "section_code": section,
        "ladder_loaded": loaded_txt or meta.get("ladder_loaded"),
        "results_loaded": loaded_txt or meta.get("results_loaded"),
        "synced": time.strftime("%Y-%m-%d"),
        "source_ladder": f"{BASE}/ladders.php?daytime={daytime}&section={section}&style=",
        "source_results": f"{BASE}/results.php?daytime={daytime}&section={section}&style=",
        "source_fixture": f"{BASE}/fixture.php?daytime={daytime}&section={section}&style=",
    })

    draw = build_draw(fixture)
    if not draw:
        # No fixture this run: keep the dates, but never keep opponents that
        # aren't in this section.
        draw = [
            {**row, "opponent": row.get("opponent") if row.get("opponent") in valid_teams else None,
             "homeAway": row.get("homeAway") if row.get("opponent") in valid_teams else None}
            for row in old.get("draw", [])
        ]
        if draw:
            print("  ! fixture unavailable — keeping dates only")

    meta["team_code"] = our_code or meta.get("team_code")

    out = {
        "meta": meta,
        "ladder": ladder,
        "results": results,
        "draw": draw,
        "finals": old.get("finals", []),
        "clubs": clubs or old.get("clubs", []),
    }

    DATA_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {DATA_FILE} — {len(ladder)} teams, {len(results)} rounds, {len(out['draw'])} draw rows")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
