"""data/status.json: a description of the latest run."""
import json
from pathlib import Path

from .moves import compare
from .rawio import list_raw


def make_status(rows, raw_dir, run_time, results):
    """run_time is a UTC timestamp like 2026-11-13T14:30:00Z; results is one dict per source
    with name, ok and count (a failed source has ok false and count 0)."""
    days = sorted(list_raw(raw_dir))
    day = run_time[:10]
    changes = compare(rows, day)
    return {
        "run_time": run_time,
        "first_run_date": days[0] if days else day,
        "days_with_success": len(days),
        "items": sum(1 for r in rows if r["date"] == day),
        "new_today": len(changes["appeared"]),
        "gone_today": len(changes["gone"]),
        "sources": [{"name": r["name"], "ok": bool(r["ok"]), "count": int(r["count"])}
                    for r in sorted(results, key=lambda r: r["name"])],
    }


def write_status(status, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
