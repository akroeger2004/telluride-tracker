"""Building the history from raw files (see telltracker/history.py)."""
import filecmp
import json

from conftest import fixture_bytes
from telltracker.history import COLUMNS, build_history, fmt, read_history, write_history
from telltracker.rawio import list_raw, raw_path, write_raw


def put(tmp_path, day, items, source="fake"):
    write_raw(tmp_path, day, source, "json", json.dumps(items).encode())


def test_the_first_four_columns_are_fixed():
    assert COLUMNS[:4] == ["date", "item_id", "item", "source"]


def test_one_row_per_item_per_day_sorted_by_date_then_item_id(tmp_path, fake_source):
    put(tmp_path, "2026-11-02", [["b", "open", 1], ["a", "closed", 0]])
    put(tmp_path, "2026-11-01", [["c", "open", 1], ["a", "closed", 0]])
    rows = build_history(tmp_path)
    assert [(r["date"], r["item_id"]) for r in rows] == [
        ("2026-11-01", "a"), ("2026-11-01", "c"), ("2026-11-02", "a"), ("2026-11-02", "b")]
    assert all(set(r) == set(COLUMNS) for r in rows)


def test_a_day_with_no_raw_file_for_a_source_has_no_rows_from_it(tmp_path, fake_source):
    put(tmp_path, "2026-11-01", [["a", "open", 1]])
    put(tmp_path, "2026-11-03", [["a", "open", 1]])
    assert sorted({r["date"] for r in build_history(tmp_path)}) == ["2026-11-01", "2026-11-03"]


def test_a_source_that_fails_does_not_remove_the_other_sources_rows(tmp_path, fake_source):
    write_raw(tmp_path, "2026-11-01", "nws", "json", fixture_bytes("nws_grid.json"))
    put(tmp_path, "2026-11-01", [["a", "open", 1]])
    put(tmp_path, "2026-11-02", [["a", "open", 1]])  # nws has no file on the 2nd
    rows = build_history(tmp_path)
    assert {(r["date"], r["source"]) for r in rows} == {("2026-11-01", "nws"), ("2026-11-01", "fake"), ("2026-11-02", "fake")}


def test_a_value_the_source_does_not_report_is_left_empty(tmp_path, fake_source):
    put(tmp_path, "2026-11-01", [["a", "open", 1]])
    row = build_history(tmp_path)[0]
    assert row["is_open"] == "1" and row["snow_depth_in"] == "" and row["level"] == ""


def test_rebuilding_gives_the_same_file(tmp_path, tmp_path_factory, fake_source):
    put(tmp_path, "2026-11-01", [["a", "open", 1], ["b", "closed", 0]])
    put(tmp_path, "2026-11-02", [["a", "closed", 0]])
    out = tmp_path_factory.mktemp("out")
    write_history(build_history(tmp_path), out / "one.csv")
    write_history(build_history(tmp_path), out / "two.csv")
    assert filecmp.cmp(out / "one.csv", out / "two.csv", shallow=False)


def test_a_second_run_on_the_same_day_replaces_the_days_file(tmp_path, fake_source):
    put(tmp_path, "2026-11-01", [["a", "closed", 0]])
    put(tmp_path, "2026-11-01", [["a", "open", 1], ["b", "open", 1]])  # the second run of the day
    rows = build_history(tmp_path)
    assert [(r["item_id"], r["status"]) for r in rows] == [("a", "open"), ("b", "open")]
    assert len(list_raw(tmp_path)["2026-11-01"]) == 1  # one file, so the day counts once


def test_a_rule_change_applies_to_every_day(tmp_path, fake_source, monkeypatch):
    put(tmp_path, "2026-11-01", [["a", "open", 1]])
    put(tmp_path, "2026-11-02", [["a", "open", 1]])
    monkeypatch.setitem(fake_source, "convert", lambda content, day: [
        {"item_id": "a", "item": "A", "category": "lift", "status": "changed", "is_open": 9}])
    assert {r["status"] for r in build_history(tmp_path)} == {"changed"}


def test_duplicate_item_ids_in_one_file_count_once(tmp_path, fake_source):
    put(tmp_path, "2026-11-01", [["a", "open", 1], ["a", "closed", 0]])
    assert [r["status"] for r in build_history(tmp_path)] == ["open"]


def test_a_raw_file_for_an_unknown_source_is_ignored(tmp_path, fake_source):
    write_raw(tmp_path, "2026-11-01", "retired", "json", b"[]")
    assert build_history(tmp_path) == []


def test_real_sources_build_into_one_history(tmp_path, responses):
    for name, fmt_ in (("telluride", "html"), ("snotel", "json"), ("nws", "json")):
        write_raw(tmp_path, "2026-11-13", name, fmt_, responses[name])
    rows = build_history(tmp_path)
    assert len(rows) == 189 and {r["source"] for r in rows} == {"telluride", "snotel", "nws"}
    assert len({r["item_id"] for r in rows}) == 189 and all(r["date"] == "2026-11-13" for r in rows)


def test_numbers_are_written_without_trailing_zeros():
    assert [fmt(x) for x in (12.0, 0.5, 3.1, 2.345678, 0, None, "")] == ["12", "0.5", "3.1", "2.346", "0", "", ""]


def test_csv_round_trip(tmp_path, fake_source):
    put(tmp_path / "raw", "2026-11-01", [['say "hi", ok', "open", 1]])
    rows = build_history(tmp_path / "raw")
    write_history(rows, tmp_path / "h.csv")
    assert read_history(tmp_path / "h.csv")[0]["item_id"] == 'say "hi", ok'


def test_raw_files_are_named_source_format_gz(tmp_path):
    p = write_raw(tmp_path, "2026-11-01", "telluride", "html", b"<p>x</p>")
    assert p == raw_path(tmp_path, "2026-11-01", "telluride", "html")
    assert p.relative_to(tmp_path).as_posix() == "2026-11-01/telluride.html.gz"
    assert list_raw(tmp_path) == {"2026-11-01": {"telluride": p}}
