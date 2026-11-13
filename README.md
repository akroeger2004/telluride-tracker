# Telluride Tracker

[![tests](https://github.com/akroeger2004/telluride-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/akroeger2004/telluride-tracker/actions/workflows/tests.yml)
[![daily](https://github.com/akroeger2004/telluride-tracker/actions/workflows/daily.yml/badge.svg)](https://github.com/akroeger2004/telluride-tracker/actions/workflows/daily.yml)

A tool that tracks **snowfall, lifts and runs at Telluride and Mountain Village, Colorado**. Every
day, on its own, it downloads the latest values, adds them to a history with one row per item per
day, reports what moved, and publishes the result to a website.

Live site: <https://akroeger2004.github.io/telluride-tracker/>

Financial Data Analytics course project. Built with Claude Code.

## What is tracked

About 189 items a day, from three sources that need no login and no API key:

| Category | Items | Count |
|---|---|---|
| `mountain` | Telluride Ski Resort (snow depth, new snow, season total, lifts and trails open, weather) | 1 |
| `lift` | Every lift, including the free Town to Mountain Village gondola and the Mountain Village lifts | 17 |
| `terrain` | The hike-to terrain areas (Bald Mountain, Black Iron Bowl, Gold Hill Ridge, Palmyra Peak) | 4 |
| `trail` | Every trail (run) on the snow report, with its difficulty and whether it is groomed | 157 |
| `station` | NRCS SNOTEL snow stations around Telluride | 9 |
| `forecast` | National Weather Service forecast for the Mountain Village grid point | 1 |

The lifts and trails are closed until the ski season opens, so for the first weeks the values that
change are the snow numbers, the stations and the forecast. When the lifts start opening, the
moves, the Trends page and the daily issue start to show it.

## Sources

| Source | What it is | Format | Kept |
|---|---|---|---|
| `telluride` | The Telluride Ski & Golf snow report, <https://tellurideskiresort.com/snow-report/> | web page (`.html.gz`) | Only the report part of the page (snow totals, lifts, terrain, trails, weather); the site navigation and footer are dropped before saving |
| `snotel` | NRCS SNOTEL daily data from the AWDB web service, <https://wcc.sc.egov.usda.gov/awdbRestApi> | JSON (`.json.gz`) | Only the 9 stations within about 20 miles of Telluride, 6 elements (snow depth, snow water equivalent, precipitation, average, maximum and minimum temperature) and the last 7 days |
| `nws` | National Weather Service gridpoint forecast for Mountain Village (`GJT/115,49`), <https://api.weather.gov> | JSON (`.json.gz`) | Only the 7 properties used: update time, elevation, temperature, max and min temperature, snowfall amount, probability of precipitation |

SNOTEL stations tracked: Alta Lakes, Red Mountain Pass, Idarado, Mineral Creek, Lizard Head Pass,
Molas Lake, El Diente Peak, Spud Mountain and Cascade #2. No API key is used, so there are no
secrets in the repository.

Item keys (`item_id`) are built from the source's own names, so the same item lines up every day:
`mountain:telluride`, `lift:<slug of the lift name>`, `terrain:<slug>`, `trail:<slug of the trail name>`,
`station:<SNOTEL station number>` and `forecast:mountain-village`. A trail listed under two lifts is one item.

## How it works

1. A GitHub Actions workflow (`daily.yml`) runs once a day at 14:30 UTC (7:30 a.m. in Telluride).
2. `telltracker/pipeline.py` calls every source and saves what it returned, compressed and in the
   format it came in, to `data/raw/<date>/<source>.<format>.gz`. A source that fails writes no file
   that day (this includes an answer the converter cannot read, such as a blocked page); its failure
   is recorded in `data/status.json` and the run carries on.
3. `telltracker/history.py` builds `data/history.csv` from the raw files.
4. The pipeline writes `data/status.json` and opens a GitHub Issue titled with the date that lists the
   items that moved the most, with old and new values, and any item that appeared or disappeared,
   then closes the previous day's issue. The issue is opened every day, even on a day with no changes.
5. The workflow commits the raw files, the history and the status. GitHub Pages serves the site from
   the repository root.

A successful run is one that finishes and commits, even when some sources failed. A second run on the
same day replaces that day's raw files, builds the history again and updates that day's issue, so
each day counts once. If a source fails on the second run, its file from the first run is kept.

## Build the history from the raw files

```
python -m telltracker.history
```

This reads only `data/raw/` and rewrites `data/history.csv`. Running it again gives the same file,
and a change to a rule applies to every day of the history. A day with no raw file for a source has
no rows from that source. Rows are sorted by `date`, then `item_id`.

## The history file: `data/history.csv`

One row per item per day. Dates are UTC dates (`YYYY-MM-DD`); every run takes the UTC date of the
moment it runs. A value a source does not report for an item is left empty.

| Column | Meaning | Unit |
|---|---|---|
| `date` | The run date (UTC) | date |
| `item_id` | Stable key for the item (see above) | text |
| `item` | The item's name | text |
| `source` | Which source reported the row: `telluride`, `snotel` or `nws` | text |
| `category` | `mountain`, `lift`, `terrain`, `trail`, `station` or `forecast` | text |
| `area` | Lifts: the area of the mountain. Trails: the lift they are listed under. Terrain: "Hike-to terrain". Stations: "San Juan Mountains". | text |
| `level` | Trails only: difficulty (`novice`, `intermediate`, `advanced_novice`, `advanced_intermediate`, `expert`, `extreme`) | text |
| `status` | Lifts, trails and terrain: `open`, `hold` (on hold) or `closed` (terrain can also be `hike`). Mountain: the snow condition reported (for example `variable`). | text |
| `obs_date` | The date the value refers to, for the mountain, stations and forecast (SNOTEL reports the previous day) | date |
| `is_open` | 1 if the lift, trail or terrain area is open (or open to hike), 0 if closed or on hold | 0/1 |
| `on_hold` | 1 if a lift, trail or hike-to terrain area is on hold | 0/1 |
| `is_groomed` | 1 if a trail is groomed | 0/1 |
| `hours_open` | Operating hours listed for a lift today; 0 when closed | hours |
| `snow_depth_in` | Snow depth on the ground (mountain and stations) | inches |
| `snow_overnight_in` | Snow that fell overnight (mountain) | inches |
| `snow_24h_in` | Snow in the last 24 hours (mountain) | inches |
| `snow_48h_in` | Snow in the last 48 hours (mountain) | inches |
| `snow_7d_in` | Snow in the last 7 days (mountain) | inches |
| `season_total_in` | Snow this season (mountain) | inches |
| `lifts_open` | Number of lifts open, counted from the lift rows (mountain) | count |
| `lifts_total` | Number of lifts on the snow report (mountain) | count |
| `trails_open` | Number of trails open, counted from the trail list (mountain) | count |
| `trails_total` | Number of trails on the snow report (mountain) | count |
| `swe_in` | Snow water equivalent: the water in the snowpack (stations) | inches |
| `precip_in` | Precipitation accumulated since October 1 (stations) | inches |
| `elevation_ft` | Station elevation | feet |
| `temp_f` | Mountain: current temperature. Stations: average air temperature for the day. | °F |
| `temp_high_f` | Mountain: today's forecast high. Stations: the day's maximum. Forecast: the next 24 hours' maximum. | °F |
| `temp_low_f` | Mountain: today's forecast low. Stations: the day's minimum. Forecast: the next 24 hours' minimum. | °F |
| `forecast_snow_24h_in` | Forecast snowfall for the 24 hours starting 12:00 UTC (6 a.m. in Telluride) on the run date | inches |
| `forecast_snow_72h_in` | Forecast snowfall for the 72 hours from the same start | inches |
| `forecast_precip_chance` | Highest forecast probability of precipitation in those first 24 hours | percent |

The `item_id`, `date`, `item` and `source` columns come first, in that order.

## The move rule

Every item has one **primary value**, chosen by its category:

| Category | Primary value |
|---|---|
| `lift`, `trail`, `terrain` | `is_open` (1 open, 0 closed or on hold) |
| `mountain`, `station` | `snow_depth_in` (inches) |
| `forecast` | `forecast_snow_72h_in` (inches) |

An item's **move** is the change in its primary value since the previous run of its source: new
minus old. To rank moves in different units, each gets a **score** = |move| ÷ scale, where the scale
is 1 for `is_open` and 6 inches for snow depth and for the snow forecast. So a lift opening or
closing (score 1.0) ranks the same as six inches of snow depth change. Moves are ranked by score,
highest first, ties broken by `item_id`.

The **previous run of a source** is the latest earlier day that has a raw file for that source, so a
source that failed on some day does not make its items look as if they disappeared. An item has
**appeared** if it is in the latest run but not in the previous run of its source, and has **gone** if
it was in the previous run but not in the latest. The first run of a source has nothing to compare
with, so nothing appears, disappears or moves in it.

The daily issue lists up to **20** of the biggest moves with their old and new values, every item
that appeared or went (up to 30 of each), and says when nothing changed. The same rule is used
by the Today and Trends pages (in `assets/calc.js`), and a test checks that both agree.

## Status file: `data/status.json`

`run_time` (UTC), `first_run_date` (the date of the earliest raw file), `days_with_success` (the
number of different dates with a raw file), `items` (items in the latest run), `new_today` (items
that appeared), `gone_today` (items that went) and `sources`, a list with one entry per source holding
`name`, `ok` (true or false) and `count` (items the source gave; 0 if it failed).

## The site

All three pages load `data/history.csv` and `data/status.json` in the browser and do the calculations
there.

- **Today** (`index.html`): time of the last run, status of every source, the counts from the status
  file, the biggest moves, what appeared and went, and the latest value of every item with its
  change since the previous run.
- **Browse** (`browse.html`): the latest value of every item with filters on category, area, status
  and level, a search box on item names, sorting up and down on every numeric column, and a star on
  every item that saves it to a shortlist kept in the browser (it is still there after a reload).
- **Trends** (`trends.html`): six findings, each with a heading that states the finding, a
  paragraph with the numbers and how they are computed, and a chart (snow depth over the days; lifts
  and trails open; the day with the most moves; how far apart the stations are; each station's change
  since the first run; days each lift has been open), plus an explorer with a chart of every
  numeric value and a control that picks which items are shown.

The site has a web app manifest and a service worker, so it installs from the browser as an app. Online,
the pages load the data files from the network; offline, the site still opens and shows the last
data it loaded.

## Files

| File | What it does |
|---|---|
| `telltracker/__init__.py` | Marks `telltracker` as a Python package |
| `telltracker/sources.py` | The three sources: how to fetch each one, and how to convert what it returned into item rows |
| `telltracker/rawio.py` | Writes and reads the compressed raw files |
| `telltracker/history.py` | Builds `data/history.csv` from the raw files (`python -m telltracker.history`) |
| `telltracker/moves.py` | The move rule |
| `telltracker/status.py` | Builds `data/status.json` |
| `telltracker/issue.py` | Writes and publishes the daily GitHub Issue |
| `telltracker/pipeline.py` | The daily run (`python -m telltracker.pipeline --issue`) |
| `tests/conftest.py` | Shared test helpers and fixtures |
| `tests/test_sources.py` | Tests of the conversion of each source to the common columns |
| `tests/test_history.py` | Tests of the history build, including a second run on the same day |
| `tests/test_moves.py` | Tests of the move rule |
| `tests/test_pipeline.py` | Tests of the daily run: failed sources, status, same-day re-runs, the issue |
| `tests/test_issue.py` | Tests of the issue text and of creating, updating and closing issues |
| `tests/test_site_calc.py` | Runs `assets/calc.js` under Node and checks every number against Python |
| `tests/fixtures/snow_report.html` | A saved copy of the report part of the snow report page |
| `tests/fixtures/snotel.json`, `tests/fixtures/nws_grid.json` | Saved SNOTEL and NWS answers |
| `.github/workflows/daily.yml` | Runs the pipeline every day and commits the data |
| `.github/workflows/tests.yml` | Runs the tests on every push |
| `data/raw/<date>/<source>.<format>.gz` | What each source returned that day |
| `data/history.csv` | One row per item per day |
| `data/status.json` | Describes the latest run |
| `index.html` | Today page |
| `browse.html` | Browse page |
| `trends.html` | Trends page |
| `assets/calc.js` | The calculations: the history parser, the move rule and the Trends numbers (pure functions, also run under Node by the tests) |
| `assets/common.js` | Shared navigation bar, data loading and helpers |
| `assets/charts.js` | The chart components (lines, columns, bars) |
| `assets/style.css` | Shared fonts and colors |
| `assets/today.js`, `assets/browse.js`, `assets/trends.js` | The page scripts |
| `sw.js` | Service worker: network first, last copy when offline |
| `manifest.webmanifest` | Web app manifest |
| `icons/icon-192.png`, `icons/icon-512.png`, `icons/icon-maskable-512.png` | App icons |
| `tools/make_icons.py` | Draws the app icons |
| `pyproject.toml` | Project metadata and pytest settings |
| `.gitignore`, `.gitattributes` | Ignore rules and line-ending rules (raw `.gz` files are binary) |
| `README.md` | This file |

## Run it yourself

```
python -m pip install pytest
python -m pytest -q                   # tests (the site checks need Node.js)
python -m telltracker.pipeline        # fetch everything and rebuild
python -m telltracker.history         # rebuild the history from data/raw only
python -m http.server 8000            # then open http://localhost:8000
```

Python 3.11 or later; the pipeline uses only the standard library.
