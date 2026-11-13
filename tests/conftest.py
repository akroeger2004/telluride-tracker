import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(name):
    return (FIXTURES / name).read_bytes()


def report_with_open_lifts(n):
    """The real snow report page with the first n lifts switched from closed to open."""
    html = fixture_bytes("snow_report.html").decode("utf-8")
    start = html.index("tsr-report-app-lift-table")
    head, table = html[:start], html[start:]
    table = table.replace("tsr-report-app-icon-closed", "tsr-report-app-icon-open", n)
    return (head + table).encode("utf-8")


def snotel_with_depth(triplet, depth):
    """The real SNOTEL response with one station's newest snow depth changed."""
    data = json.loads(fixture_bytes("snotel.json"))
    for station in data:
        if station["stationTriplet"] == triplet:
            for series in station["data"]:
                if series["stationElement"]["elementCode"] == "SNWD":
                    series["values"][-1]["value"] = depth
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def responses():
    """What each real source returns (from the saved fixtures), keyed by source name."""
    return {"telluride": fixture_bytes("snow_report.html"), "snotel": fixture_bytes("snotel.json"),
            "nws": fixture_bytes("nws_grid.json")}


def make_fetcher(responses, failing=()):
    def fetch(source):
        if source["name"] in failing:
            raise OSError("boom")
        return responses[source["name"]]
    return fetch


@pytest.fixture
def fake_source(monkeypatch):
    """A tiny source for the history tests. Its 'raw file' is JSON: [[item_id, status, is_open], ...]."""
    from telltracker import sources

    def convert(content, run_date):
        return [{"item_id": i, "item": i.title(), "category": "lift", "status": s, "is_open": o}
                for i, s, o in json.loads(content)]

    src = {"name": "fake", "label": "Fake", "format": "json", "convert": convert, "fetch": lambda: b"[]"}
    monkeypatch.setitem(sources.BY_NAME, "fake", src)
    return src
