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
                self._cell = {"text": "", "href": None, "onclick": None, "tag": tag}
        elif tag == "a" and self._cell is not None:
            self._href = a.get("href") or ""
            if a.get("onclick"):
                self._cell["onclick"] = a["onclick"]
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

            def ctext(x):
                return (x["text"] if isinstance(x, dict) else x).strip()
            home, away = ctext(raw[0]), ctext(raw[-1])
            if not home or not away:
                continue
            middle = [ctext(x) for x in raw[1:-1] if ctext(x)]
            if not middle:
                continue
            if any("wash" in x.lower() for x in middle):
                current["matches"].append({"home": home, "away": away, "washout": True})
                current["washout"] = True
                continue
            if len(middle) < 6:
                continue
            onclick = r[0].get("onclick") if (r and isinstance(r[0], dict)) else None
            mid = None
            if onclick:
                found = re.search(r"open_match\([^)]*?'([A-Z]{2}\d{6})'", onclick)
                mid = found.group(1) if found else None
            current["matches"].append({
                "matchid": mid,
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



# ---- individual rubbers --------------------------------------------------
def parse_match_popup(html):
    """The popup lists both sides' players by position and every rubber score.

    Layout (left = home):
        title "Open Triples Green Ball 1 Rd.2 on 18th Oct 26"
        home team, away team
        1. Player, 2. Player, 3. Player      (home)
        2+3 | 5-6 | 2+3                       (six rubbers)
        1   | 18-32 | 5                       (sets, games, sets)
        1. Player, 2. Player, 3. Player      (away)
    """
    import html as htmllib
    flat = htmllib.unescape(re.sub(r"<[^>]+>", "|", html))
    toks = [t.strip() for t in flat.split("|") if t.strip() and t.strip() != "&nbsp;"]

    players = []
    for t in toks:
        m = re.match(r"^(\d)\.\s*(.+)$", t)
        if m and 1 <= int(m.group(1)) <= 3 and len(m.group(2)) > 1:
            players.append(m.group(2).strip())
    if len(players) < 4:
        return None

    scores = [i for i, t in enumerate(toks) if re.fullmatch(r"\d+-\d+", t)]
    if len(scores) < 7:
        return None

    rubbers = []
    for i in scores[:6]:
        left_label = toks[i - 1] if i else ""
        right_label = toks[i + 1] if i + 1 < len(toks) else ""
        a, b = toks[i].split("-")
        rubbers.append({"home_label": left_label, "away_label": right_label,
                        "home_games": int(a), "away_games": int(b)})

    totals = toks[scores[6]].split("-")
    return {
        "home_players": players[:3],
        "away_players": players[3:6],
        "rubbers": rubbers,
        "home_sets": sum(1 for r in rubbers if r["home_games"] > r["away_games"]),
        "away_sets": sum(1 for r in rubbers if r["away_games"] > r["home_games"]),
        "home_games_total": int(totals[0]),
        "away_games_total": int(totals[1]),
    }


def fetch_match_detail(matchid):
    try:
        html = fetch(f"{BASE}/match_popup.php?matchid={matchid}&seasonid=")
    except Exception:  # noqa: BLE001
        return None
    return parse_match_popup(html)


def positions(label):
    return [int(x) for x in re.split(r"\+", label or "") if x.isdigit()]


def build_section(results):
    """Every player in the section, from every match, plus round-by-round detail."""
    matches, failures = [], 0
    for r in results:
        for m in r["matches"]:
            if m.get("washout") or not m.get("matchid"):
                continue
            d = fetch_match_detail(m["matchid"])
            if not d:
                failures += 1
                continue
            d.update({"round": r["round"], "date": r["date"], "home": m["home"], "away": m["away"]})
            matches.append(d)
    matches.sort(key=lambda x: x["round"])

    players = {}

    def slot(name, team):
        return players.setdefault(name, {
            "name": name, "team": team, "rubbers": 0,
            "sets_won": 0, "sets_lost": 0, "games_won": 0, "games_lost": 0,
            "singles_won": 0, "singles_played": 0, "doubles_won": 0, "doubles_played": 0,
            "detail": [],
        })

    for d in matches:
        for side in ("home", "away"):
            other = "away" if side == "home" else "home"
            team = d[side]
            squad = d[f"{side}_players"]
            opp_squad = d[f"{other}_players"]
            for pos, raw_name in enumerate(squad, start=1):
                if raw_name.lower().startswith("no player"):
                    continue  # placeholder for a team that fielded fewer players
                st = slot(raw_name, team)
                entry = {"round": d["round"], "date": d["date"],
                         "opponent_team": d[other], "rubbers": []}
                for r in d["rubbers"]:
                    mine = positions(r[f"{side}_label"])
                    if pos not in mine:
                        continue
                    theirs = positions(r[f"{other}_label"])
                    ours_g = r[f"{side}_games"]
                    their_g = r[f"{other}_games"]
                    won = ours_g > their_g
                    st["rubbers"] += 1
                    st["sets_won" if won else "sets_lost"] += 1
                    st["games_won"] += ours_g
                    st["games_lost"] += their_g
                    single = len(mine) == 1
                    key = "singles" if single else "doubles"
                    st[f"{key}_played"] += 1
                    if won:
                        st[f"{key}_won"] += 1
                    entry["rubbers"].append({
                        "type": "singles" if single else "doubles",
                        "ours": ours_g, "theirs": their_g, "won": won,
                        "partner": next((squad[p - 1] for p in mine if p != pos), None),
                        "opponents": [opp_squad[p - 1] for p in theirs if p <= len(opp_squad)],
                    })
                if entry["rubbers"]:
                    st["detail"].append(entry)

    for st in players.values():
        total = st["sets_won"] + st["sets_lost"]
        st["set_pct"] = round(100 * st["sets_won"] / total, 1) if total else None
        total_g = st["games_won"] + st["games_lost"]
        st["game_pct"] = round(100 * st["games_won"] / total_g, 1) if total_g else None

    if failures:
        print(f"  ! {failures} match pop-ups could not be read")
    return matches, players


def tidy_names(players, roster_names):
    """TROLS spells a name slightly differently to the roster — align them."""
    import difflib

    fixed = {}
    for name, st in players.items():
        match = difflib.get_close_matches(name, roster_names, n=1, cutoff=0.7)
        clean = match[0] if match else name
        st["name"] = clean
        fixed[clean] = st
    return fixed



# ---- section rating -------------------------------------------------------
def compute_ratings(matches):
    """Elo-style rating from every rubber in the section.

    Each rubber is a contest between one or two players a side. The rating is
    fitted so that the share of games a side actually won matches the share
    the ratings predicted — so beating someone well moves you further than
    scraping past them, and a player's number does not depend on how many
    matches they have played.
    """
    players, contests = {}, []

    for m in matches:
        for r in m["rubbers"]:
            a = [p for p in positions(r["home_label"]) if p <= len(m["home_players"])]
            b = [p for p in positions(r["away_label"]) if p <= len(m["away_players"])]
            side_a = [m["home_players"][i - 1] for i in a]
            side_b = [m["away_players"][i - 1] for i in b]
            side_a = [n for n in side_a if not n.lower().startswith("no player")]
            side_b = [n for n in side_b if not n.lower().startswith("no player")]
            if not side_a or not side_b:
                continue
            if r["home_games"] + r["away_games"] == 0:
                continue
            contests.append((side_a, side_b, r["home_games"], r["away_games"]))
            for n in side_a + side_b:
                players.setdefault(n, 5.0)

    if not players:
        return {}

    K, SCALE = 0.30, 2.0
    for _ in range(600):
        for side_a, side_b, ga, gb in contests:
            ra = sum(players[n] for n in side_a) / len(side_a)
            rb = sum(players[n] for n in side_b) / len(side_b)
            expect = 1 / (1 + 10 ** ((rb - ra) / SCALE))
            actual = ga / (ga + gb)
            delta = K * (actual - expect)
            for n in side_a:
                players[n] += delta / len(side_a)
            for n in side_b:
                players[n] -= delta / len(side_b)
        mean = sum(players.values()) / len(players)
        for n in players:
            players[n] += (5.0 - mean) * 0.5

    return {n: round(min(10.0, max(1.0, v)), 2) for n, v in players.items()}


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

    # every match in the section, for per-player rubbers and the section ladder
    roster_names = [p["name"] for p in old.get("roster", {}).get("players", [])]
    section_matches, section_players = build_section(results)
    section_players = tidy_names(section_players, roster_names)
    ours = {n: section_players[n] for n in roster_names if n in section_players}
    # full scorecards for our own matches, so the app can draw the scoresheet
    our_matches = [m for m in section_matches if CLUB in (m["home"], m["away"])]
    print(f"  · rubbers: {len(section_matches)} matches, {len(section_players)} players in section")
    ratings = compute_ratings(section_matches)
    if ratings:
        top = sorted(ratings.items(), key=lambda kv: -kv[1])[:3]
        print("  · ratings: " + ", ".join(f"{n} {v}" for n, v in top))

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
        "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
        # The roster is maintained by the team, not by TROLS — always carry it over.
        "roster": old.get("roster", {}),
        "section_players": section_players or old.get("section_players", {}),
        "our_players": ours or old.get("our_players", {}),
        "match_count": len(section_matches) or old.get("match_count", 0),
        "match_details": our_matches or old.get("match_details", []),
        "ratings": ratings or old.get("ratings", {}),
    }

    DATA_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {DATA_FILE} — {len(ladder)} teams, {len(results)} rounds, {len(out['draw'])} draw rows")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
