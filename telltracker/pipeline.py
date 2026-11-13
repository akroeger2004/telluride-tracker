"""The daily run:  python -m telltracker.pipeline [--issue]

1. call every source and save what it returns, compressed and in the format it came in, to
   data/raw/<date>/<source>.<format>.gz (a source that fails writes no file; its failure is
   recorded in the status file and the run carries on)
2. build data/history.csv from the raw files
3. write data/status.json
4. with --issue, open today's GitHub Issue and close the previous one
The workflow then commits the raw files, the history and the status.
"""
import argparse
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .history import build_history, write_history
from .issue import publish_issue, render_issue
from .rawio import write_raw
from .sources import SOURCES
from .status import make_status, write_status

DATA = Path(__file__).resolve().parent.parent / "data"


def default_fetcher(source):
    return source["fetch"]()


def run(sources=None, fetcher=default_fetcher, data_dir=DATA, now=None, issue=False):
    sources = SOURCES if sources is None else sources
    now = now or datetime.now(timezone.utc)
    run_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    run_date = now.date()
    day = run_date.isoformat()
    raw_dir = Path(data_dir) / "raw"

    def one(src):
        try:
            content = fetcher(src)
            items = src["convert"](content, run_date)  # a response we cannot read is a failure too
        except Exception as exc:  # one source failing must not stop the run
            print(f"FAILED {src['name']}: {exc!r}", file=sys.stderr)
            if not isinstance(exc, OSError):
                traceback.print_exc()
            return {"name": src["name"], "ok": False, "count": 0}
        write_raw(raw_dir, day, src["name"], src["format"], content)
        print(f"ok {src['name']}: {len(items)} items")
        return {"name": src["name"], "ok": True, "count": len(items)}

    with ThreadPoolExecutor(max_workers=len(sources) or 1) as pool:
        results = list(pool.map(one, sources))

    rows = build_history(raw_dir)
    write_history(rows, Path(data_dir) / "history.csv")
    status = make_status(rows, raw_dir, run_time, results)
    write_status(status, Path(data_dir) / "status.json")
    title, body = render_issue(day, rows, status)
    if issue:
        try:
            publish_issue(title, body)
        except Exception as exc:  # the issue must never block the commit
            print(f"WARNING: could not publish the issue: {exc!r}", file=sys.stderr)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--issue", action="store_true", help="open/update today's GitHub Issue")
    args = parser.parse_args(argv)
    status = run(issue=args.issue)
    ok = sum(1 for s in status["sources"] if s["ok"])
    print(f"{ok}/{len(status['sources'])} sources ok; {status['items']} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
