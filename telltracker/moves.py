"""The move rule: what moved since the previous run.

Every item has one primary value, chosen by its category:

    lift, trail, terrain   is_open               (1 open, 0 closed or on hold)
    mountain, station      snow_depth_in         (inches)
    forecast               forecast_snow_72h_in  (inches of snow forecast for the next 72 hours)

An item's move is the change in its primary value since the previous run of its source:
new minus old. Moves in different units are made comparable with a score:

    score = |move| / scale,   scale = 1 for is_open, 6 inches for snow depth and forecast snow

so a lift opening or closing (score 1.0) ranks the same as six inches of snow depth change.
Moves are ranked by score, highest first, ties broken by item_id. The previous run of a source
is the latest earlier day that has a raw file for that source, so a source that failed on some
day does not make its items look like they disappeared.

An item has appeared if it is in the latest run but not in the previous run of its source, and
has gone if it was in the previous run but not in the latest. The first run of a source has no
previous run, so nothing appears, disappears or moves in it.
"""
from collections import defaultdict

PRIMARY = {
    "lift": "is_open", "trail": "is_open", "terrain": "is_open",
    "mountain": "snow_depth_in", "station": "snow_depth_in",
    "forecast": "forecast_snow_72h_in",
}
SCALE = {"is_open": 1.0, "snow_depth_in": 6.0, "forecast_snow_72h_in": 6.0}


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare(rows, day):
    """Compare the items of `day` with the previous run of each source.

    Returns {'day', 'previous': {source: previous_day}, 'moves': [...], 'appeared': [...], 'gone': [...]}.
    """
    index = defaultdict(dict)  # (source, date) -> {item_id: row}
    for r in rows:
        index[(r["source"], r["date"])][r["item_id"]] = r
    days_of = defaultdict(set)
    for source, d in index:
        days_of[source].add(d)

    previous, moves, appeared, gone = {}, [], [], []
    for source in sorted(days_of):
        current = index.get((source, day))
        earlier = [d for d in days_of[source] if d < day]
        if not current or not earlier:
            continue
        prev_day = max(earlier)
        previous[source] = prev_day
        before = index[(source, prev_day)]
        for item_id, row in current.items():
            if item_id not in before:
                appeared.append(row)
                continue
            field = PRIMARY.get(row["category"])
            old, new = num(before[item_id].get(field)), num(row.get(field))
            if field and old is not None and new is not None and new != old:
                moves.append({
                    "item_id": item_id, "item": row["item"], "category": row["category"], "source": source,
                    "field": field, "old": old, "new": new, "delta": new - old,
                    "score": abs(new - old) / SCALE[field],
                    "old_status": before[item_id].get("status", ""), "new_status": row.get("status", ""),
                })
        gone.extend(row for item_id, row in before.items() if item_id not in current)
    moves.sort(key=lambda m: (-m["score"], m["item_id"]))
    appeared.sort(key=lambda r: r["item_id"])
    gone.sort(key=lambda r: r["item_id"])
    return {"day": day, "previous": previous, "moves": moves, "appeared": appeared, "gone": gone}
