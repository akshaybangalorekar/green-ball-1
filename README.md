# East Malvern — Green Ball 1

A phone-first web app for the East Malvern **Open Triples Green Ball 1** team in the
Waverley & District Tennis Association, **Sunday AM, Summer 26/27** (section `UA037`).

It pulls the official ladder, results and fixture from TROLS (the record keeping
system Waverley Tennis uses) and adds the team admin that TROLS doesn't have:
availability and selection for each round.

## What's in it

| Tab | What it shows |
| --- | --- |
| **This week** | Next round, opponent, venue, ladder position, recent form |
| **Ladder** | All eight teams — points, percentage, sets, gap to the top |
| **Results** | Every round, match by match, East Malvern highlighted |
| **Draw** | The full season calendar through to the grand final |
| **Team** | Roster, availability (in / maybe / out), the three picked, copy-to-clipboard for the group chat |
| **Clubs** | Every club in the section with venue, Melway reference and contact |

The roster and availability live in your phone's browser storage. Nothing is uploaded,
and nothing is shared between phones — it's a selection aid, not a live shared sheet.

## Files

```
index.html                     the whole app (data embedded, so it works offline)
data.json                      the current snapshot — the app loads this if it's newer
scrape.py                      refreshes data.json from TROLS (stdlib only)
.github/workflows/update-data.yml   runs the scraper daily and commits the result
```

## Publish it on GitHub Pages

1. Push this folder to a repository (public is simplest).
2. **Settings → Pages → Source: Deploy from a branch → `main` / root → Save.**
3. The app is live at `https://<user>.github.io/<repo>/` in about a minute.
4. Open that URL on your phone → Share → **Add to Home Screen**.

Because the scraper commits `data.json` into the repo, Pages serves the fresh copy and
the app picks it up on load. No server, no database, no build step.

## The daily refresh

`.github/workflows/update-data.yml` runs at 08:00 Melbourne time (and on every push).
It runs `scrape.py`, and commits `data.json` only when something actually changed.

`scrape.py` does this:

1. Finds the competition code for `Sunday AM` and the section code for
   `Open Triples Green Ball 1` — from the dropdowns if they're in the markup,
   otherwise by scanning section codes until the ladder title matches.
2. Reads the ladder (`ladders.php`) and every round of results (`results.php`).
3. Works out played / won / sets / games per team from the results.
4. Finds East Malvern's team code from the results page links, then reads the
   fixture (`fixture.php`) for the season draw and the section's club contacts.
5. Writes `data.json`. **If anything fails it exits non-zero and leaves the old
   file untouched**, so a bad scrape never wipes good data.

To run it yourself:

```bash
python scrape.py
```

### If the fixture stays "to be confirmed"

The fixture page is keyed by an internal team code that only appears inside the
JavaScript on the results page. If TROLS changes that markup, `scrape.py` won't find
the code and the draw keeps its previous values while the ladder and results carry on
updating. Fix is usually one line: set `DAYTIME_FALLBACK` / `SECTION_FALLBACK` at the
top of `scrape.py`, or print `team_codes(results_html)` and pin the code.

## Changing season or section

Everything is driven by three constants at the top of `scrape.py`:

```python
CLUB = "East Malvern"
COMPETITION_LABEL = "Sunday AM"
SECTION_LABEL = "Open Triples Green Ball 1"
```

Change them for a different team or season and re-run. `index.html` re-renders from
whatever `data.json` contains, so it follows automatically.

## Data provenance

Ladder and results are the official WDTA figures, loaded from TROLS on
29 October 2026 (after round 3). The wash-out in round 3 pays each team 4 points,
which is why 19 points shows against two wins.

This is an unofficial team tool. TROLS and your club remain the authority on
scores, fixtures and ladders.

- Ladders — https://trols.org.au/wdta/ladders.php
- Results — https://trols.org.au/wdta/results.php
- Fixtures — https://trols.org.au/wdta/fixture.php
- Association — https://www.waverleytennis.asn.au
