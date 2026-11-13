"""The Today and Trends pages compute their numbers in the browser with assets/calc.js. This test
runs that same file under Node on a multi-day history built by the real pipeline, and checks every
number against an independent Python implementation of the definitions."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import fixture_bytes, make_fetcher, report_with_open_lifts
from telltracker import pipeline, sources
from telltracker.history import read_history
from telltracker.moves import compare


def find_node():
    exe = shutil.which("node")
    if exe:
        return [exe]
    try:
        import nodejs_wheel.executable as nw
        d = Path(nw.__file__).parent
        return [str(d / ("node.exe" if (d / "node.exe").exists() else "node"))]
    except Exception:
        return None


NODE = find_node()
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")
ROOT = Path(__file__).resolve().parent.parent

SCRIPT = r"""
const C = require(process.argv[2]);
const rows = C.parseHistory(require('fs').readFileSync(process.argv[3], 'utf8'));
const days = C.daysOf(rows);
const compared = days.map(function (d) { const c = C.compare(rows, d); return { day: d, previous: c.previous,
  moves: c.moves.map(function (m) { return [m.item_id, m.field, m.old, m.new, m.delta, m.score]; }),
  appeared: c.appeared.map(function (r) { return r.item_id; }), gone: c.gone.map(function (r) { return r.item_id; }) }; });
const dt = C.depthTrend(rows);
console.log(JSON.stringify({
  numeric: C.NUMERIC, days: days, calendar: C.calendar(rows), compared: compared,
  latest: C.latestRows(rows).map(function (r) { return [r.item_id, r.date]; }),
  depth: { first: dt.mountainFirst, last: dt.mountainLast, deepest: dt.deepest, ids: dt.ids, mountain: dt.series['mountain:telluride'] },
  terrain: C.terrainOpen(rows), activity: C.activity(rows), spread: C.stationSpread(rows).perDay,
  since: C.sinceFirstRun(rows), lifts: C.liftDays(rows),
  series: C.valueSeries(rows, ['station:713', 'lift:chondola'], 'snow_depth_in', C.calendar(rows))
}));
"""


def at(day):
    y, m, d = map(int, day.split("-"))
    return datetime(y, m, d, 14, 30, tzinfo=timezone.utc)


def snotel(changes):
    data = json.loads(fixture_bytes("snotel.json"))
    for station in data:
        station_id = station["stationTriplet"].split(":")[0]
        for series in station["data"]:
            if series["stationElement"]["elementCode"] == "SNWD" and station_id in changes:
                series["values"][-1]["value"] = changes[station_id]
    return json.dumps(data).encode()


def without_first_lift(page):
    page = page.decode("utf-8")
    start = page.index("<tr>", page.index("tsr-report-app-lift-table") + 200)
    return (page[:start] + page[page.index("</tr>", start) + 5:]).encode("utf-8")


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("data")
    base = {"telluride": fixture_bytes("snow_report.html"), "snotel": fixture_bytes("snotel.json"), "nws": fixture_bytes("nws_grid.json")}
    plan = [  # day, telluride page, snotel changes, failing sources
        ("2026-11-13", base["telluride"], {}, ()),
        ("2026-11-14", report_with_open_lifts(2), {"713": 30, "1344": 15}, ()),
        ("2026-11-15", report_with_open_lifts(5), {"713": 30, "1344": 15}, ("nws",)),
        ("2026-11-17", report_with_open_lifts(4), {"713": 33, "538": 9}, ("snotel",)),
        ("2026-11-18", without_first_lift(report_with_open_lifts(6)), {"713": 36, "538": 9, "1344": 20}, ()),
    ]
    for day, page, changes, failing in plan:
        responses = dict(base, telluride=page, snotel=snotel(changes))
        pipeline.run(sources.SOURCES, make_fetcher(responses, failing), tmp, now=at(day))
    return tmp / "history.csv"


@pytest.fixture(scope="module")
def js(history, tmp_path_factory):
    script = tmp_path_factory.mktemp("js") / "run.js"
    script.write_text(SCRIPT)
    out = subprocess.run(NODE + [str(script), str(ROOT / "assets" / "calc.js"), str(history)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def rows(history):
    out = read_history(history)
    for r in out:
        for c in sources.NUMERIC:
            r[c] = float(r[c]) if r[c] != "" else None
    return out


def num_days(rows):
    return sorted({r["date"] for r in rows})


def calendar(rows):
    from datetime import date, timedelta
    d = num_days(rows)
    a, b = date.fromisoformat(d[0]), date.fromisoformat(d[-1])
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def test_the_history_has_the_shape_the_checks_need(rows):
    assert num_days(rows) == ["2026-11-13", "2026-11-14", "2026-11-15", "2026-11-17", "2026-11-18"]
    assert {r["source"] for r in rows} == {"telluride", "snotel", "nws"}


def test_the_numeric_columns_match_the_python_side(js):
    assert js["numeric"] == sources.NUMERIC


def test_days_and_calendar(js, rows):
    assert js["days"] == num_days(rows) and js["calendar"] == calendar(rows)


def test_latest_row_of_every_item(js, rows):
    last = {}
    for r in rows:
        if r["item_id"] not in last or r["date"] > last[r["item_id"]]:
            last[r["item_id"]] = r["date"]
    assert js["latest"] == [[i, last[i]] for i in sorted(last)]


def test_the_move_rule_gives_the_same_answer_in_js_and_python(js, rows):
    for entry in js["compared"]:
        want = compare(rows, entry["day"])
        assert entry["previous"] == want["previous"], entry["day"]
        assert entry["appeared"] == [r["item_id"] for r in want["appeared"]], entry["day"]
        assert entry["gone"] == [r["item_id"] for r in want["gone"]], entry["day"]
        assert [(m[0], m[1], m[2], m[3], m[4]) for m in entry["moves"]] == \
               [(m["item_id"], m["field"], m["old"], m["new"], m["delta"]) for m in want["moves"]], entry["day"]
        assert [m[5] for m in entry["moves"]] == pytest.approx([m["score"] for m in want["moves"]]), entry["day"]


def test_the_scenario_really_exercises_moves_appearances_and_failures(js):
    by_day = {e["day"]: e for e in js["compared"]}
    assert len(by_day["2026-11-14"]["moves"]) >= 5           # 2 lifts opened, 2 stations changed, the forecast moved
    assert by_day["2026-11-18"]["gone"] == ["lift:free-gondola-town-to-mv"]
    assert "nws" not in by_day["2026-11-15"]["previous"]        # nws failed that day
    assert by_day["2026-11-17"]["previous"].get("telluride") == "2026-11-15"
    assert "snotel" not in by_day["2026-11-17"]["previous"]


def test_depth_trend(js, rows):
    mountain = {r["date"]: r["snow_depth_in"] for r in rows if r["item_id"] == "mountain:telluride"}
    assert js["depth"]["first"] == mountain["2026-11-13"] and js["depth"]["last"] == mountain["2026-11-18"]
    assert js["depth"]["mountain"] == [mountain.get(d) for d in calendar(rows)]
    latest = {}
    for r in sorted((r for r in rows if r["category"] == "station" and r["snow_depth_in"] is not None), key=lambda r: r["date"]):
        latest[r["item_id"]] = (r["snow_depth_in"], r["item"])
    best = max(latest.items(), key=lambda kv: (kv[1][0], [-ord(c) for c in kv[0]]))
    assert js["depth"]["deepest"]["value"] == best[1][0]
    assert js["depth"]["deepest"]["id"] == best[0]


def test_terrain_open_counts(js, rows):
    cal = calendar(rows)
    for kind, open_key, total_key in (("lift", "liftsOpen", "liftsTotal"), ("trail", "trailsOpen", "trailsTotal")):
        want_open, want_total = [], []
        for d in cal:
            day = [r for r in rows if r["date"] == d and r["category"] == kind]
            want_open.append(sum(r["is_open"] or 0 for r in day) if day else None)
            want_total.append(len(day) if day else None)
        assert js["terrain"][open_key] == want_open and js["terrain"][total_key] == want_total
    assert js["terrain"]["firstDay"] == "2026-11-13" and js["terrain"]["lastDay"] == "2026-11-18"


def test_activity_and_the_biggest_day(js, rows):
    per = {e["day"]: e for e in js["activity"]["perDay"]}
    for d in num_days(rows):
        want = compare(rows, d)
        assert (per[d]["moved"], per[d]["appeared"], per[d]["gone"]) == (len(want["moves"]), len(want["appeared"]), len(want["gone"]))
        assert per[d]["score"] == pytest.approx(sum(m["score"] for m in want["moves"]))
    compared = [(d, len(compare(rows, d)["moves"])) for d in num_days(rows) if compare(rows, d)["previous"]]
    best = max(compared, key=lambda x: (x[1], [-ord(c) for c in x[0]]))
    assert js["activity"]["best"]["day"] == best[0] and js["activity"]["best"]["moved"] == best[1]


def test_station_spread(js, rows):
    for entry, d in zip(js["spread"], calendar(rows)):
        stations = [r for r in rows if r["date"] == d and r["category"] == "station" and r["snow_depth_in"] is not None]
        if len(stations) < 2:
            assert entry["spread"] is None
            continue
        lo = min(r["snow_depth_in"] for r in stations)
        hi = max(r["snow_depth_in"] for r in stations)
        assert (entry["min"], entry["max"], entry["spread"]) == (lo, hi, hi - lo)


def test_change_since_the_first_run(js, rows):
    want = {}
    for r in sorted((r for r in rows if r["category"] == "station" and r["snow_depth_in"] is not None), key=lambda r: r["date"]):
        want.setdefault(r["item_id"], {"first": r["snow_depth_in"], "firstDay": r["date"]})
        want[r["item_id"]].update(last=r["snow_depth_in"], lastDay=r["date"])
    got = {s["item_id"]: s for s in js["since"]}
    assert set(got) == set(want)
    for i, w in want.items():
        assert (got[i]["first"], got[i]["last"], got[i]["change"], got[i]["firstDay"]) == (w["first"], w["last"], w["last"] - w["first"], w["firstDay"])
    changes = [s["change"] for s in js["since"]]
    assert changes == sorted(changes, reverse=True) and changes[0] > 0


def test_days_each_lift_was_open(js, rows):
    want = {}
    for r in rows:
        if r["category"] == "lift":
            w = want.setdefault(r["item_id"], [0, 0])
            w[0] += 1
            w[1] += int(r["is_open"] or 0)
    got = {l["item_id"]: (l["listed"], l["open"]) for l in js["lifts"]}
    assert got == {i: tuple(v) for i, v in want.items()}
    opens = [l["open"] for l in js["lifts"]]
    assert opens == sorted(opens, reverse=True)


def test_value_series_has_a_gap_for_days_with_no_row(js, rows):
    cal = calendar(rows)
    depth = {r["date"]: r["snow_depth_in"] for r in rows if r["item_id"] == "station:713"}
    assert js["series"]["station:713"] == [depth.get(d) for d in cal]
    assert js["series"]["lift:chondola"] == [None] * len(cal)  # not a real lift id: no rows, all gaps


def test_csv_parser_handles_quotes_commas_and_blank_fields(tmp_path):
    script = tmp_path / "csv.js"
    script.write_text("const C=require(process.argv[2]);"
                      "console.log(JSON.stringify(C.parseCSV('a,b,c\\r\\n\"x, \"\"y\"\"\",,z\\n')));")
    out = subprocess.run(NODE + [str(script), str(ROOT / "assets" / "calc.js")], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [["a", "b", "c"], ['x, "y"', "", "z"]]
