"""The daily issue: its text, and how it is created, updated and the previous one closed."""
import json

import pytest

from telltracker import issue
from telltracker.issue import MAX_MOVES, render_issue


def row(day, item_id, category="lift", source="telluride", **v):
    r = {"date": day, "item_id": item_id, "item": item_id.split(":")[1].title(), "source": source,
         "category": category, "status": "", "is_open": "", "snow_depth_in": "", "forecast_snow_72h_in": ""}
    r.update({k: str(x) for k, x in v.items()})
    return r


STATUS = {"run_time": "2026-11-02T14:30:00Z", "items": 3, "days_with_success": 2,
          "sources": [{"name": "telluride", "ok": True, "count": 2}, {"name": "snotel", "ok": False, "count": 0}]}


def test_the_title_is_the_date_and_moves_show_old_and_new_values():
    rows = [row("2026-11-01", "lift:chondola", is_open=0, status="closed"),
            row("2026-11-02", "lift:chondola", is_open=1, status="open"),
            row("2026-11-01", "station:713", "station", snow_depth_in=20),
            row("2026-11-02", "station:713", "station", snow_depth_in=32)]
    title, body = render_issue("2026-11-02", rows, STATUS)
    assert title == "2026-11-02"
    assert "**Chondola** (lift): closed → open" in body
    assert "snow depth 20 → 32 in (+12)" in body
    assert body.index("snow depth 20") < body.index("closed → open")  # 12 in scores 2.0, a lift opening 1.0
    assert "Sources that failed: snotel" in body


def test_items_that_appeared_and_disappeared_are_listed():
    rows = [row("2026-11-01", "trail:old"), row("2026-11-01", "trail:stays"),
            row("2026-11-02", "trail:stays"), row("2026-11-02", "trail:new")]
    _, body = render_issue("2026-11-02", rows, STATUS)
    assert "## Appeared (1)" in body and "- New (lift)" in body
    assert "## Gone (1)" in body and "- Old (lift)" in body


def test_a_day_with_no_changes_still_gets_an_issue_that_says_so():
    rows = [row("2026-11-01", "lift:a", is_open=0), row("2026-11-02", "lift:a", is_open=0)]
    title, body = render_issue("2026-11-02", rows, STATUS)
    assert title == "2026-11-02" and "Nothing moved since the previous run." in body and body.count("None.") == 3


def test_the_first_run_says_there_is_nothing_to_compare_with():
    _, body = render_issue("2026-11-01", [row("2026-11-01", "lift:a", is_open=1)], STATUS)
    assert "first run of every source" in body


def test_only_the_biggest_moves_are_listed():
    rows = []
    for i in range(MAX_MOVES + 7):
        rows += [row("2026-11-01", f"trail:t{i:02d}", is_open=0), row("2026-11-02", f"trail:t{i:02d}", is_open=1)]
    _, body = render_issue("2026-11-02", rows, STATUS)
    assert f"## Biggest moves ({MAX_MOVES + 7})" in body and "…and 7 smaller moves" in body
    assert body.count("· score") == MAX_MOVES


# ---------------------------------------------------------- publishing (gh is faked)


@pytest.fixture
def gh(monkeypatch):
    state = {"issues": [], "calls": []}

    def fake(args, body=None):
        if args[:2] == ["issue", "list"]:
            return json.dumps(state["issues"])
        state["calls"].append((args, body))
        return "https://github.com/x/y/issues/9\n" if args[:2] == ["issue", "create"] else ""

    monkeypatch.setattr(issue, "_gh", fake)
    return state


def verbs(state):
    return [(c[0][1], c[0][2] if len(c[0]) > 2 else None) for c in state["calls"]]


def test_a_new_day_opens_todays_issue_and_closes_the_previous_one(gh):
    gh["issues"] = [{"number": 4, "title": "2026-11-12", "state": "OPEN"},
                    {"number": 3, "title": "2026-11-11", "state": "CLOSED"},
                    {"number": 2, "title": "Something someone filed", "state": "OPEN"}]
    issue.publish_issue("2026-11-13", "body")
    creates = [c for c in gh["calls"] if c[0][1] == "create"]
    assert len(creates) == 1 and creates[0][0][3] == "2026-11-13" and creates[0][1] == "body"
    assert ("close", "4") in verbs(gh) and ("close", "2") not in verbs(gh) and ("close", "3") not in verbs(gh)


def test_a_second_run_on_the_same_day_updates_instead_of_creating(gh):
    gh["issues"] = [{"number": 7, "title": "2026-11-13", "state": "OPEN"}]
    issue.publish_issue("2026-11-13", "new body")
    assert [v[0] for v in verbs(gh)] == ["edit"] and gh["calls"][0][1] == "new body"


def test_a_closed_issue_for_today_is_reopened_on_a_rerun(gh):
    gh["issues"] = [{"number": 7, "title": "2026-11-13", "state": "CLOSED"}]
    issue.publish_issue("2026-11-13", "again")
    assert ("edit", "7") in verbs(gh) and ("reopen", "7") in verbs(gh)


def test_todays_issue_is_never_closed(gh):
    gh["issues"] = [{"number": 7, "title": "2026-11-13", "state": "OPEN"}]
    issue.publish_issue("2026-11-13", "x")
    assert ("close", "7") not in verbs(gh)
