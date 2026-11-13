"""Build data/history.csv from the raw files alone.

    python -m telltracker.history

For each day that has raw files, each source's file is converted to item rows (one common set
of columns) and added to the history. A day with no raw file for a source has no rows from that
source. The rows are sorted by date, then by item_id. Nothing but the raw files is read, so
running this again gives the same file, and a change to a rule applies to every day of the history.
"""
import csv
import sys
from datetime import date
from pathlib import Path

from . import sources
from .rawio import list_raw, read_raw

FIXED = ["date", "item_id", "item", "source"]
COLUMNS = FIXED + sources.TEXT + sources.NUMERIC


def fmt(value):
    """Numbers are written without trailing zeros; a missing value is an empty cell."""
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def build_history(raw_dir):
    rows = []
    days = list_raw(raw_dir)
    for day in sorted(days):
        run_date = date.fromisoformat(day)
        for name in sorted(days[day]):
            source = sources.BY_NAME.get(name)
            if source is None:
                continue  # a raw file for a source that is no longer tracked
            seen = set()
            for item in source["convert"](read_raw(days[day][name]), run_date):
                if item["item_id"] in seen:
                    continue
                seen.add(item["item_id"])
                row = {c: fmt(item.get(c)) for c in COLUMNS}
                row.update(date=day, source=name, item_id=item["item_id"], item=item["item"])
                rows.append(row)
    rows.sort(key=lambda r: (r["date"], r["item_id"]))
    return rows


def write_history(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_history(path):
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    root = Path(__file__).resolve().parent.parent / "data"
    rows = build_history(root / "raw")
    write_history(rows, root / "history.csv")
    print(f"wrote {len(rows)} rows to {root / 'history.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
