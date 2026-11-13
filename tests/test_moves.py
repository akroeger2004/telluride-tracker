"""The move rule (see telltracker/moves.py)."""
import pytest

from telltracker.moves import PRIMARY, SCALE, compare


def row(day, item_id, category="lift", source="telluride", **values):
    r = {"date": day, "item_id": item_id, "item": item_id.split(":")[1].title(), "source": source,
         "category": category, "status": "", "is_open": "", "snow_depth_in": "", "forecast_snow_72h_in": ""}
    r.update({k: str(v) for k, v in values.items()})
    return r


def test_a_lift_that_opens_is_a_move_of_score_one():
    rows = [row("2026-11-01", "lift:a", is_open=0, status="closed"), row("2026-11-02", "lift:a", is_open=1, status="open")]
    m = compare(rows, "2026-11-02")["moves"]
    assert len(m) == 1
    assert (m[0]["field"], m[0]["old"], m[0]["new"], m[0]["delta"], m[0]["score"]) == ("is_open", 0, 1, 1, 1.0)
    assert (m[0]["old_status"], m[0]["new_status"]) == ("closed", "open")


def test_six_inches_of_snow_depth_scores_the_same_as_a_lift_opening():
    rows = [row("2026-11-01", "station:1", "station", snow_depth_in=10), row("2026-11-02", "station:1", "station", snow_depth_in=16)]
    assert compare(rows, "2026-11-02")["moves"][0]["score"] == 1.0


def test_a_fall_in_depth_counts_as_much_as_a_rise():
    rows = [row("2026-11-01", "station:1", "station", snow_depth_in=30), row("2026-11-02", "station:1", "station", snow_depth_in=24)]
    m = compare(rows, "2026-11-02")["moves"][0]
    assert m["delta"] == -6 and m["score"] == 1.0


def test_each_category_uses_its_own_primary_value():
    assert PRIMARY == {"lift": "is_open", "trail": "is_open", "terrain": "is_open", "mountain": "snow_depth_in",
                       "station": "snow_depth_in", "forecast": "forecast_snow_72h_in"}
    assert SCALE == {"is_open": 1.0, "snow_depth_in": 6.0, "forecast_snow_72h_in": 6.0}


def test_forecast_snow_is_the_forecast_items_primary_value():
    rows = [row("2026-11-01", "forecast:mv", "forecast", forecast_snow_72h_in=0.5),
            row("2026-11-02", "forecast:mv", "forecast", forecast_snow_72h_in=3.5)]
    m = compare(rows, "2026-11-02")["moves"][0]
    assert (m["field"], m["delta"], m["score"]) == ("forecast_snow_72h_in", 3.0, 0.5)


def test_unchanged_items_are_not_moves():
    rows = [row("2026-11-01", "lift:a", is_open=0), row("2026-11-02", "lift:a", is_open=0)]
    assert compare(rows, "2026-11-02")["moves"] == []


def test_moves_are_ranked_by_score_then_item_id():
    rows = [row("2026-11-01", "lift:b", is_open=0), row("2026-11-01", "lift:a", is_open=0),
            row("2026-11-01", "station:1", "station", snow_depth_in=0),
            row("2026-11-02", "lift:b", is_open=1), row("2026-11-02", "lift:a", is_open=1),
            row("2026-11-02", "station:1", "station", snow_depth_in=12)]
    ids = [m["item_id"] for m in compare(rows, "2026-11-02")["moves"]]
    assert ids == ["station:1", "lift:a", "lift:b"]  # 12 in scores 2.0, the lifts 1.0 each


def test_items_that_appeared_or_disappeared():
    rows = [row("2026-11-01", "trail:old"), row("2026-11-01", "trail:stays"),
            row("2026-11-02", "trail:stays"), row("2026-11-02", "trail:new")]
    ch = compare(rows, "2026-11-02")
    assert [r["item_id"] for r in ch["appeared"]] == ["trail:new"]
    assert [r["item_id"] for r in ch["gone"]] == ["trail:old"]


def test_the_first_run_has_nothing_to_compare_with():
    ch = compare([row("2026-11-01", "lift:a", is_open=1)], "2026-11-01")
    assert ch["moves"] == [] and ch["appeared"] == [] and ch["gone"] == [] and ch["previous"] == {}


def test_previous_run_is_the_latest_earlier_day_of_that_source():
    rows = [row("2026-11-01", "lift:a", is_open=0), row("2026-11-05", "lift:a", is_open=1)]
    ch = compare(rows, "2026-11-05")
    assert ch["previous"] == {"telluride": "2026-11-01"} and len(ch["moves"]) == 1


def test_a_source_that_did_not_run_today_makes_nothing_look_gone():
    rows = [row("2026-11-01", "lift:a", source="telluride"), row("2026-11-01", "station:1", "station", source="snotel"),
            row("2026-11-02", "lift:a", source="telluride")]  # snotel has no file on the 2nd
    ch = compare(rows, "2026-11-02")
    assert ch["gone"] == [] and list(ch["previous"]) == ["telluride"]


def test_a_new_source_does_not_make_its_items_appear():
    rows = [row("2026-11-01", "lift:a", source="telluride"),
            row("2026-11-02", "lift:a", source="telluride"), row("2026-11-02", "station:1", "station", source="snotel")]
    assert compare(rows, "2026-11-02")["appeared"] == []


def test_a_missing_value_is_not_a_move():
    rows = [row("2026-11-01", "station:1", "station", snow_depth_in=""), row("2026-11-02", "station:1", "station", snow_depth_in=5)]
    assert compare(rows, "2026-11-02")["moves"] == []


@pytest.mark.parametrize("old,new", [(0, 1), (1, 0)])
def test_opening_and_closing_have_the_same_score(old, new):
    rows = [row("2026-11-01", "lift:a", is_open=old), row("2026-11-02", "lift:a", is_open=new)]
    assert compare(rows, "2026-11-02")["moves"][0]["score"] == 1.0
