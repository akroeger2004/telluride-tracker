"""The daily run (see telltracker/pipeline.py), with the three real sources answering from fixtures."""
import json
from datetime import datetime, timezone

from conftest import make_fetcher, report_with_open_lifts, snotel_with_depth
from telltracker import pipeline
from telltracker.history import read_history
from telltracker.rawio import list_raw, read_raw
from telltracker.sources import SOURCES


def at(day, hour=14):
    y, m, d = map(int, day.split("-"))
    return datetime(y, m, d, hour, 30, 0, tzinfo=timezone.utc)


def run(tmp_path, responses, day, failing=(), hour=14, **kw):
    return pipeline.run(SOURCES, make_fetcher(responses, failing), tmp_path, now=at(day, hour), **kw)


def test_a_normal_run_writes_raw_files_history_and_status(tmp_path, responses):
    status = run(tmp_path, responses, "2026-11-13")
    files = list_raw(tmp_path / "raw")["2026-11-13"]
    assert {p.name for p in files.values()} == {"telluride.html.gz", "snotel.json.gz", "nws.json.gz"}
    assert (tmp_path / "history.csv").exists() and (tmp_path / "status.json").exists()
    assert status["items"] == 189


def test_the_raw_file_is_exactly_what_the_source_returned(tmp_path, responses):
    run(tmp_path, responses, "2026-11-13")
    files = list_raw(tmp_path / "raw")["2026-11-13"]
    assert read_raw(files["telluride"]) == responses["telluride"]
    assert read_raw(files["snotel"]) == responses["snotel"]


def test_status_has_exactly_the_specified_keys(tmp_path, responses):
    run(tmp_path, responses, "2026-11-13")
    status = json.loads((tmp_path / "status.json").read_text())
    assert set(status) == {"run_time", "first_run_date", "days_with_success", "items", "new_today", "gone_today", "sources"}
    assert status["run_time"] == "2026-11-13T14:30:00Z" and status["first_run_date"] == "2026-11-13"
    assert status["sources"] == [{"name": "nws", "ok": True, "count": 1}, {"name": "snotel", "ok": True, "count": 9},
                                 {"name": "telluride", "ok": True, "count": 179}]


def test_a_failed_source_writes_no_file_but_the_run_still_succeeds(tmp_path, responses):
    status = run(tmp_path, responses, "2026-11-13", failing={"snotel"})
    assert sorted(list_raw(tmp_path / "raw")["2026-11-13"]) == ["nws", "telluride"]
    assert {"name": "snotel", "ok": False, "count": 0} in status["sources"]
    assert status["items"] == 180 and (tmp_path / "history.csv").exists()


def test_a_response_we_cannot_read_counts_as_a_failure_and_writes_no_file(tmp_path, responses):
    bad = dict(responses, telluride=b"<html>Just a moment...</html>")
    status = run(tmp_path, bad, "2026-11-13")
    assert "telluride" not in list_raw(tmp_path / "raw")["2026-11-13"]
    assert next(s for s in status["sources"] if s["name"] == "telluride")["ok"] is False


def test_every_source_failing_still_commits_a_status(tmp_path, responses):
    status = run(tmp_path, responses, "2026-11-13", failing={"telluride", "snotel", "nws"})
    assert status["items"] == 0 and status["days_with_success"] == 0 and (tmp_path / "status.json").exists()


def test_second_run_on_the_same_day_replaces_the_files_and_counts_the_day_once(tmp_path, responses):
    run(tmp_path, responses, "2026-11-13", hour=8)
    later = dict(responses, telluride=report_with_open_lifts(2))
    status = run(tmp_path, later, "2026-11-13", hour=20)
    assert status["days_with_success"] == 1 and status["run_time"] == "2026-11-13T20:30:00Z"
    assert len(list_raw(tmp_path / "raw")["2026-11-13"]) == 3
    rows = [r for r in read_history(tmp_path / "history.csv") if r["category"] == "lift"]
    assert sum(1 for r in rows if r["is_open"] == "1") == 2 and len(rows) == 17  # one row per lift, replaced values


def test_a_failed_second_run_keeps_the_days_earlier_file(tmp_path, responses):
    run(tmp_path, responses, "2026-11-13", hour=8)
    status = run(tmp_path, responses, "2026-11-13", hour=20, failing={"telluride"})
    assert "telluride" in list_raw(tmp_path / "raw")["2026-11-13"]
    assert next(s for s in status["sources"] if s["name"] == "telluride")["ok"] is False


def test_the_next_day_reports_what_moved(tmp_path, responses):
    run(tmp_path, responses, "2026-11-13")
    next_day = dict(responses, telluride=report_with_open_lifts(3), snotel=snotel_with_depth("713:CO:SNTL", 40))
    status = run(tmp_path, next_day, "2026-11-14")
    assert status["days_with_success"] == 2 and status["first_run_date"] == "2026-11-13"
    assert status["items"] == 189 and status["new_today"] == 0 and status["gone_today"] == 0


def test_an_item_that_vanishes_is_counted_as_gone(tmp_path, responses):
    run(tmp_path, responses, "2026-11-13")
    page = responses["telluride"].decode("utf-8")
    start = page.index("<tr>", page.index("tsr-report-app-lift-table") + 200)
    trimmed = (page[:start] + page[page.index("</tr>", start) + 5:]).encode("utf-8")  # drop the first lift row
    status = run(tmp_path, dict(responses, telluride=trimmed), "2026-11-14")
    assert status["gone_today"] == 1 and status["items"] == 188


def test_history_is_rebuilt_from_raw_files_alone(tmp_path, responses):
    from telltracker.history import build_history, write_history
    run(tmp_path, responses, "2026-11-13")
    run(tmp_path, dict(responses, telluride=report_with_open_lifts(1)), "2026-11-14")
    first = (tmp_path / "history.csv").read_bytes()
    (tmp_path / "history.csv").unlink()
    write_history(build_history(tmp_path / "raw"), tmp_path / "history.csv")
    assert (tmp_path / "history.csv").read_bytes() == first


def test_the_issue_is_published_with_the_date_as_its_title(tmp_path, responses, monkeypatch):
    seen = {}
    monkeypatch.setattr(pipeline, "publish_issue", lambda t, b: seen.update(title=t, body=b))
    run(tmp_path, responses, "2026-11-13", issue=True)
    assert seen["title"] == "2026-11-13" and "Biggest moves" in seen["body"]


def test_a_failing_issue_publish_does_not_stop_the_run(tmp_path, responses, monkeypatch):
    def boom(title, body):
        raise RuntimeError("gh is down")
    monkeypatch.setattr(pipeline, "publish_issue", boom)
    assert run(tmp_path, responses, "2026-11-13", issue=True)["items"] == 189
