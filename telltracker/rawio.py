"""Reading and writing the compressed raw files: data/raw/<date>/<source>.<format>.gz

A raw file holds exactly what the source returned (HTML stays HTML, JSON stays JSON),
compressed. Nothing is added to it, so the history can be rebuilt from raw files alone.
"""
import gzip
import io
import re
from pathlib import Path

DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def raw_path(raw_dir, day, source, fmt):
    return Path(raw_dir) / day / f"{source}.{fmt}.gz"


def write_raw(raw_dir, day, source, fmt, content):
    """Save what a source returned. A file for the same source and day is replaced."""
    path = raw_path(raw_dir, day, source, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:  # mtime=0: stable bytes
        gz.write(content)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(buf.getvalue())
    tmp.replace(path)
    return path


def read_raw(path):
    with gzip.open(path, "rb") as fh:
        return fh.read()


def list_raw(raw_dir):
    """{'2026-11-13': {'telluride': Path, ...}, ...} for every raw file on disk."""
    days = {}
    root = Path(raw_dir)
    if not root.is_dir():
        return days
    for day_dir in sorted(root.iterdir()):
        if not (day_dir.is_dir() and DATE_DIR.match(day_dir.name)):
            continue
        files = {}
        for p in sorted(day_dir.glob("*.gz")):
            parts = p.name.split(".")  # <source>.<format>.gz
            if len(parts) == 3:
                files[parts[0]] = p
        if files:
            days[day_dir.name] = files
    return days
