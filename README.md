# Advantage — East Malvern Green Ball 1

**Advantage** is a phone-first app for the East Malvern **Open Triples Green Ball 1** team
in the Waverley & District Tennis Association, **Sunday AM, Summer 26/27** (section `UA037`).
The name is the tennis call, and it's what every screen is about: points, percentage, position.

It pulls the official ladder, results and fixture from TROLS (the record keeping
system Waverley Tennis uses) and adds the team admin that TROLS doesn't have:
availability and selection for each round.

## What's in it

| Tab | What it shows |
| --- | --- |
| **This week** | Next round, opponent, venue, the three on court, ladder position, and a season strip |
| **Team** | One thing only: the gap to the finals line, with the points for each team that matters |
| **Squad** | Your four — tap a child for every set they have played — plus a ladder of all 31 players in the section |
| **Season** | Ladder / Results / Draw in one tab, switched with a segmented control |
| **Clubs** | Every club in the section with venue, Melway reference and contact |

Every tab has its own link (`#team`, `#squad`, `#season`, …) so you can send the team
straight to the right screen.

## The analysis, and what it is based on

The ladder, results, fixture and club contacts come from TROLS. The squad — team
order and availability — comes from the team roster sheet, and is stored in
`data.json` under `roster` so the daily scrape never overwrites it.

Team tab: a single card showing first, whoever you are level with, you, and fourth, with
points and a dashed line where the finals cut falls, then one sentence of plain English
(how many points clear of the cut, how many rounds left).

Player cards: rounds scheduled, team record in the rounds they were on court,
availability percentage, most frequent partners, and next round's status.

**Every player in the section, not just yours.** The scraper reads all four matches in
every round, so the section ladder covers all 31 players across the eight clubs, and a
parent can see where their child sits in the whole competition. Each player page shows
the round-by-round sets: who they played, with whom, and the score.

**The player ladder is computed, not official.** Waverley publishes the team ladder only;
there is no player ladder on TROLS. These rankings are worked out from the published
rubbers, and the app says so on the card.

The ladder opens in **the website's order**: the eight clubs exactly as they stand on the
official team ladder, with each club's players listed together (within a club, most games
won first). That mirrors how the association lists the section, rather than inventing a
player ranking.

Three further sorts are one tap away — **Games** won, **Win %** (sets won ÷ sets played)
and **Sets** won — for anyone who wants to compare across the whole section. The four
child cards keep their true games-won rank whatever the list is sorted by.

Each row shows games won–lost and how many sets that player has played, so the volume
behind any number is never hidden. **Tapping any player opens a sheet explaining their exact position**, written for that child specifically: their own sets and games, the opponents
they faced, how many others are level with them, a side-by-side of games won for everyone
tied on sets, what it would take to pass the player directly above, and their tightest
set or only loss. The same sheet is one tap away from their own page. The ladder rows
show sets and games inline as well.

**Player points come from the official rubbers.** Each match has a pop-up on TROLS
(`match_popup.php?matchid=…`) listing both sides' players by position and every rubber
score. The scraper reads those, so each player gets real numbers: sets won and lost,
games won and lost, and a singles and doubles record. In triples every player plays one
singles and two doubles each round, so a full round is three rubbers per player.

TROLS spells one name slightly differently from the roster ("Bangalopekar"), so the
scraper matches names back to the roster with a fuzzy match before totalling.

Tapping In / ? / Out on a squad card records a change for the next round. That override
lives in your phone's browser storage only — nothing is uploaded, and it isn't shared
between phones. The roster sheet stays the source of truth in `data.json`.

## It runs as an app, not a browser tab

The site is a PWA. Open it once in the phone's browser, then **Add to Home Screen**
(iPhone: Share → Add to Home Screen). From then on it launches full screen with its own
icon, no address bar, and keeps working offline — the last snapshot is cached.

Files that make that work:

```
manifest.webmanifest   name, icon, standalone display, shortcuts
sw.js                  service worker: offline shell + update checks
icon-192/512.png       app icons
apple-touch-icon.png   iOS home-screen icon
```

## The scores passcode

Games and sets are hidden by default. Settings → **Scores** takes a passcode (the team's
is `1981`); enter it and the scores appear on that phone until you tap "Hide again".

This is a curtain, not a lock. The app is a static site: `data.json` still contains every
score and anyone who reads the file, or views the page source, can see them. The passcode
keeps the figures off the screen when a phone is being passed around — which is the usual
reason to want it on a junior team's app — but it cannot make public data private. If the
scores genuinely must be secret, the data has to stop being public, and that means
hosting it somewhere with a login rather than on GitHub Pages.

## Settings

The gear in the header opens a sheet with the install control, the alerts toggle and the
about block (sources, snapshot time, the "unofficial tool" note) — so none of that takes
up room on a tab. The circular arrow beside it refreshes the data.

## Refresh

The circular arrow in the header pulls the latest `data.json` straight away — useful on
match day, when results land while you have the app open. It reports back in a toast:
"Updated from TROLS", "Already up to date", "Offline — showing saved data", or
"Couldn't reach TROLS". Opening the app already does the same check silently, so the
button is for when you are sitting on the page waiting for a score.

## Alerts

Turning alerts on asks for notification permission. The app then watches for changes
between what you last saw and what TROLS now says:

- a new round of results posted
- the ladder reloading (points or positions moved)
- the fixture or opponent changing

**How it actually fires depends on the phone, and it's worth being precise about it.**
On Android the service worker registers a periodic background check, so alerts can
arrive with the app closed. On iPhone, Safari only allows push notifications from a
server, so there the alert appears the next time you open the app. Nothing is sent to
a third party in either case — the check is the app fetching `data.json`.

If you want alerts to land on the phone even when the app has not been opened for
days, that needs a push service (OneSignal, Firebase, or a tiny server). Say the word
and I'll wire one up; it's a small addition, but it needs an account and a key from you.

## Files

```
index.html                     the whole app (data embedded, so it works offline)
data.json                      the current snapshot — the app loads this if it's newer
manifest.webmanifest           PWA manifest
sw.js                          service worker
icon-192.png, icon-512.png     app icons
apple-touch-icon.png           iOS icon
scrape.py                      refreshes data.json from TROLS (stdlib only)
.github/workflows/update-data.yml   scrapes daily, commits, and deploys Pages
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

### The team code

The fixture page is keyed by an opaque team code (`UA284` for this side) that isn't
published on any page — the site builds its match links in JavaScript. The scraper
handles that in three steps, cheapest first:

1. reuse the code cached in `data.json` → `meta.team_code` (verified every run);
2. probe the codes that appear in the results page markup;
3. scan `SCAN_FROM`–`SCAN_TO` (240–360 by default) as a last resort.

A code is only accepted when every team in its fixture belongs to this section — a
club can field several teams, and East Malvern has another side elsewhere in the
competition whose code would otherwise match by name. Once found, the code is cached,
so the scan runs at most once.

If TROLS ever renumbers teams and the draw goes blank, the fix is one line: set
`SCAN_FROM` / `SCAN_TO` in `scrape.py` to a wider window and run it once. The ladder,
results and club contacts keep working either way.

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

Ladder, results, season draw and club contacts are the official WDTA figures, scraped
from TROLS. The snapshot in the repo is the 29 October 2026 load (after round 3); the
wash-out in round 3 pays each team 4 points, which is why 19 points shows against two
wins. Round 4, on 8 November, is a home match against MCC Glen Iris.

This is an unofficial team tool. TROLS and your club remain the authority on
scores, fixtures and ladders.

- Ladders — https://trols.org.au/wdta/ladders.php
- Results — https://trols.org.au/wdta/results.php
- Fixtures — https://trols.org.au/wdta/fixture.php
- Association — https://www.waverleytennis.asn.au
