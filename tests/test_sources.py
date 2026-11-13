import json
from collections import Counter
from datetime import date

import pytest

from conftest import fixture_bytes, report_with_open_lifts, snotel_with_depth
from telltracker import sources
from telltracker.sources import (NUMERIC, TEXT, SourceError, convert_nws, convert_report, convert_snotel,
                                 extract_report_region, slug)

RUN = date(2026, 11, 13)
KNOWN = set(NUMERIC) | set(TEXT) | {"item_id", "item"}


# ------------------------------------------------------------- snow report page


def test_report_converts_to_mountain_lifts_terrain_and_trails():
    rows = convert_report(fixture_bytes("snow_report.html"), RUN)
    assert Counter(r["category"] for r in rows) == {"mountain": 1, "lift": 17, "terrain": 4, "trail": 157}


def test_report_mountain_row_has_the_snow_numbers():
    m = {r["item_id"]: r for r in convert_report(fixture_bytes("snow_report.html"), RUN)}["mountain:telluride"]
    assert (m["snow_depth_in"], m["season_total_in"], m["snow_overnight_in"]) == (12.0, 12.0, 6.0)
    assert (m["snow_24h_in"], m["snow_48h_in"], m["snow_7d_in"]) == (0.0, 0.0, 0.0)
    assert m["status"] == "variable"
    assert (m["lifts_open"], m["lifts_total"], m["trails_open"], m["trails_total"]) == (0, 17, 0, 157)
    assert (m["temp_f"], m["temp_high_f"], m["temp_low_f"]) == (39.0, 48.0, 27.0)


def test_report_lift_row():
    lifts = {r["item_id"]: r for r in convert_report(fixture_bytes("snow_report.html"), RUN) if r["category"] == "lift"}
    gondola = lifts["lift:free-gondola-town-to-mv"]
    assert gondola["item"] == "Free Gondola – Town to MV"      # the HTML entity is decoded
    assert (gondola["area"], gondola["status"], gondola["is_open"], gondola["on_hold"]) == ("Village", "closed", 0, 0)
    assert gondola["hours_open"] == 0.0


def test_report_trail_row_keeps_level_area_and_flags():
    trails = {r["item_id"]: r for r in convert_report(fixture_bytes("snow_report.html"), RUN) if r["category"] == "trail"}
    t = trails["trail:meadows-south"]
    assert (t["item"], t["area"], t["level"]) == ("Meadows – South", "Chondola", "novice")
    assert (t["status"], t["is_open"], t["on_hold"], t["is_groomed"]) == ("closed", 0, 0, 0)


def test_report_notices_lifts_that_open():
    rows = convert_report(report_with_open_lifts(3), RUN)
    by = {r["item_id"]: r for r in rows}
    assert by["mountain:telluride"]["lifts_open"] == 3
    assert [r["is_open"] for r in rows if r["category"] == "lift"].count(1) == 3
    assert next(r for r in rows if r["category"] == "lift")["status"] == "open"


def test_every_item_in_every_category_has_at_least_two_numeric_values():
    """The assignment needs two numeric values per item; check each category of each source."""
    from conftest import fixture_bytes as fb
    rows = (convert_report(fb("snow_report.html"), RUN) + convert_snotel(fb("snotel.json"), RUN)
            + convert_nws(fb("nws_grid.json"), RUN))
    for r in rows:
        numeric = [c for c in NUMERIC if r.get(c) is not None]
        assert len(numeric) >= 2, (r["item_id"], numeric)


def test_terrain_areas_report_open_and_hold():
    terrain = [r for r in convert_report(fixture_bytes("snow_report.html"), RUN) if r["category"] == "terrain"]
    assert len(terrain) == 4 and all(r["is_open"] == 0 and r["on_hold"] == 0 for r in terrain)


def test_report_rows_use_known_columns_and_unique_item_ids():
    rows = convert_report(fixture_bytes("snow_report.html"), RUN)
    assert all(set(r) <= KNOWN for r in rows)
    ids = [r["item_id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_a_trail_listed_under_two_lifts_is_one_item():
    page = fixture_bytes("snow_report.html").decode("utf-8")
    rows = convert_report((page + page[page.index("tsr-report-app-trail-list-lift"):]).encode("utf-8"), RUN)
    assert len([r for r in rows if r["category"] == "trail"]) == 157


def test_report_with_the_wrong_page_is_an_error():
    with pytest.raises(SourceError):
        convert_report(b"<html><body>Just a moment...</body></html>", RUN)


def test_extract_report_region_drops_the_site_navigation():
    page = "<html><nav>menu</nav>" + fixture_bytes("snow_report.html").decode("utf-8") + "<footer>f</footer></html>"
    region = extract_report_region(page)
    assert "menu" not in region and "<footer>" not in region and "tsr-report-app-lift-table" in region
    assert len(convert_report(region.encode("utf-8"), RUN)) == 179


def test_extract_report_region_rejects_a_page_without_the_report():
    with pytest.raises(SourceError):
        extract_report_region("<html>Access denied</html>")


@pytest.mark.parametrize("text,hours", [("CLOSED", 0.0), ("9:00AM - 4:00PM", 7.0), ("8:30 AM - 4:00 PM", 7.5),
                                        ("", 0.0), ("see map", None)])
def test_hours_open(text, hours):
    assert sources._hours_open(text) == hours


def test_slug():
    assert slug("Free Gondola &#8211; Town to MV") == "free-gondola-town-to-mv"
    assert slug("Children&#8217;s Magic Carpet") == "children-s-magic-carpet"


# -------------------------------------------------------------------- SNOTEL


def test_snotel_converts_every_station():
    rows = convert_snotel(fixture_bytes("snotel.json"), RUN)
    assert len(rows) == 9 and all(r["category"] == "station" and r["item_id"].startswith("station:") for r in rows)
    alta = next(r for r in rows if r["item_id"] == "station:1344")
    assert alta["item"] == "Alta Lakes (SNOTEL)" and alta["elevation_ft"] == 11290
    assert (alta["snow_depth_in"], alta["swe_in"]) == (18, 4.8)
    assert alta["obs_date"] == "2026-11-12"  # the newest day the station reported


def test_snotel_reports_the_newest_value_on_or_before_the_run_date():
    rows = convert_snotel(fixture_bytes("snotel.json"), date(2026, 11, 10))
    assert {r["obs_date"] for r in rows} == {"2026-11-10"}


def test_snotel_picks_up_a_changed_depth():
    rows = convert_snotel(snotel_with_depth("713:CO:SNTL", 41), RUN)
    assert next(r for r in rows if r["item_id"] == "station:713")["snow_depth_in"] == 41


def test_snotel_skips_a_station_with_no_snow_depth_and_rejects_an_empty_answer():
    data = json.loads(fixture_bytes("snotel.json"))
    for series in data[0]["data"]:
        if series["stationElement"]["elementCode"] == "SNWD":
            series["values"] = []
    assert len(convert_snotel(json.dumps(data).encode(), RUN)) == 8
    with pytest.raises(SourceError):
        convert_snotel(b"[]", RUN)


# ----------------------------------------------------------------------- NWS


def nws(snow, **extra):
    return json.dumps({"properties": {"snowfallAmount": {"values": snow}, **extra}}).encode()


def test_nws_converts_the_real_forecast():
    row = convert_nws(fixture_bytes("nws_grid.json"), RUN)[0]
    assert row["item_id"] == "forecast:mountain-village" and row["category"] == "forecast"
    assert row["forecast_snow_72h_in"] >= row["forecast_snow_24h_in"] >= 0
    assert row["temp_high_f"] > row["temp_low_f"]


def test_nws_sums_snowfall_and_converts_millimetres_to_inches():
    snow = [{"validTime": "2026-11-13T12:00:00+00:00/PT6H", "value": 25.4},
            {"validTime": "2026-11-14T18:00:00+00:00/PT6H", "value": 50.8},
            {"validTime": "2026-11-15T12:00:00+00:00/PT6H", "value": 25.4}]
    row = convert_nws(nws(snow), RUN)[0]
    assert row["forecast_snow_24h_in"] == 1.0    # only the first interval ends before 12:00 UTC on the 14th
    assert row["forecast_snow_72h_in"] == 4.0    # all three intervals are inside the 72 hours


def test_nws_prorates_an_interval_that_straddles_the_window_edge():
    # 12:00 UTC on the 13th starts the window; this interval runs 09:00 to 15:00, so half is inside
    snow = [{"validTime": "2026-11-13T09:00:00+00:00/PT6H", "value": 25.4 * 2}]
    assert convert_nws(nws(snow), RUN)[0]["forecast_snow_24h_in"] == 1.0


def test_nws_understands_day_durations_and_temperatures():
    snow = [{"validTime": "2026-11-13T12:00:00+00:00/P1D", "value": 0}]
    extra = {"maxTemperature": {"values": [{"validTime": "2026-11-13T12:00:00+00:00/PT12H", "value": 10}]},
             "minTemperature": {"values": [{"validTime": "2026-11-13T18:00:00+00:00/PT12H", "value": -5}]},
             "probabilityOfPrecipitation": {"values": [{"validTime": "2026-11-13T12:00:00+00:00/PT6H", "value": 40},
                                                       {"validTime": "2026-11-13T18:00:00+00:00/PT6H", "value": 70}]}}
    row = convert_nws(nws(snow, **extra), RUN)[0]
    assert (row["temp_high_f"], row["temp_low_f"], row["forecast_precip_chance"]) == (50.0, 23.0, 70)


def test_nws_without_snowfall_is_an_error():
    with pytest.raises(SourceError):
        convert_nws(b'{"properties": {}}', RUN)


def test_the_source_list():
    assert [s["name"] for s in sources.SOURCES] == ["telluride", "snotel", "nws"]
    assert {s["format"] for s in sources.SOURCES} == {"html", "json"}
    assert len(sources.STATIONS) == 9
