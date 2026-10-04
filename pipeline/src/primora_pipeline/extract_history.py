"""Tracker 1.1: SimplifyJobs git history -> per-listing change events in Parquet.

Walks every commit that touched listings.json (oldest first) and writes one row per
change event, not one row per listing per commit:
  - added:   listing appears for the first time (or reappears after being removed)
  - changed: any field other than date_updated differs from the last seen version
  - removed: listing is gone from the file (pruned or deleted)

Outputs (in DATA_DIR/history/):
  observations.parquet  one row per event, with the listing's fields at that commit
  commits.parquet       one row per commit: sha, time, listing count, parse status

Run:  uv run python -m primora_pipeline.extract_history [--refresh]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import orjson
import pyarrow as pa
import pyarrow.parquet as pq

from primora_pipeline.paths import DATA_DIR, LISTINGS_PATH, SIMPLIFY_REPO_URL

REPO_DIR = DATA_DIR / "raw" / "simplify.git"
OUT_DIR = DATA_DIR / "history"

# Fields stored on every event. date_updated is stored but ignored for change detection,
# since it moves on edits that don't matter for openings.
FIELDS = [
    "company_name", "title", "category", "active", "is_visible", "terms", "date_posted",
    "date_updated", "url", "locations", "source", "sponsorship", "company_url",
]
IGNORED_FOR_CHANGES = {"date_updated"}

SCHEMA = pa.schema([
    ("listing_id", pa.string()),
    ("event", pa.string()),
    ("commit_sha", pa.string()),
    ("commit_time", pa.timestamp("s", tz="UTC")),
    ("company_name", pa.string()),
    ("title", pa.string()),
    ("category", pa.string()),
    ("active", pa.bool_()),
    ("is_visible", pa.bool_()),
    ("terms", pa.list_(pa.string())),
    ("date_posted", pa.timestamp("s", tz="UTC")),
    ("date_updated", pa.timestamp("s", tz="UTC")),
    ("url", pa.string()),
    ("locations", pa.list_(pa.string())),
    ("source", pa.string()),
    ("sponsorship", pa.string()),
    ("company_url", pa.string()),
])


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_DIR), *args], check=True, capture_output=True, text=True).stdout


def ensure_repo(refresh: bool) -> None:
    if not REPO_DIR.exists():
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--bare", "-q", SIMPLIFY_REPO_URL, str(REPO_DIR)], check=True)
    elif refresh:
        git("fetch", "-q", "origin", "+refs/heads/*:refs/heads/*")


def listing_commits() -> list[tuple[str, int]]:
    out = git("log", "--reverse", "--format=%H %ct", "HEAD", "--", LISTINGS_PATH)
    return [(sha, int(ts)) for sha, ts in (line.split() for line in out.splitlines())]


def iter_blobs(commits: list[tuple[str, int]]):
    """Stream listings.json at each commit through one `git cat-file --batch` process."""
    proc = subprocess.Popen(
        ["git", "-C", str(REPO_DIR), "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    try:
        for sha, ts in commits:
            proc.stdin.write(f"{sha}:{LISTINGS_PATH}\n".encode())
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            if header[-1] == b"missing":
                yield sha, ts, None
                continue
            size = int(header[2])
            blob = proc.stdout.read(size)
            proc.stdout.read(1)  # trailing newline
            yield sha, ts, blob
    finally:
        proc.stdin.close()
        proc.wait()


def listing_key(item: dict) -> str | None:
    # Older schema versions may lack an id; fall back to the posting URL.
    return item.get("id") or item.get("url") or None


def to_ts(value) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def as_str_list(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


CHANGE_FIELDS = [f for f in FIELDS if f not in IGNORED_FOR_CHANGES]


def fingerprint(item: dict) -> tuple:
    # Plain value comparison (lists and dicts compare by value in C). Much faster than
    # serializing each field, which matters at ~20k listings x ~28k commits.
    return tuple(item.get(f) for f in CHANGE_FIELDS)


def make_row(key: str, event: str, sha: str, commit_time: datetime, item: dict) -> dict:
    return {
        "listing_id": key,
        "event": event,
        "commit_sha": sha,
        "commit_time": commit_time,
        "company_name": item.get("company_name"),
        "title": item.get("title"),
        "category": item.get("category"),
        "active": item.get("active"),
        "is_visible": item.get("is_visible"),
        "terms": as_str_list(item.get("terms")),
        "date_posted": to_ts(item.get("date_posted")),
        "date_updated": to_ts(item.get("date_updated")),
        "url": item.get("url"),
        "locations": as_str_list(item.get("locations")),
        "source": item.get("source"),
        "sponsorship": item.get("sponsorship"),
        "company_url": item.get("company_url"),
    }


def extract(refresh: bool = False) -> None:
    ensure_repo(refresh)
    commits = listing_commits()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{len(commits)} commits touch {LISTINGS_PATH}", file=sys.stderr)

    writer = pq.ParquetWriter(OUT_DIR / "observations.parquet", SCHEMA, compression="zstd")
    state: dict[str, tuple[tuple, dict]] = {}  # key -> (fingerprint, last item)
    batch: list[dict] = []
    commit_rows: list[dict] = []
    n_events = 0

    def flush():
        nonlocal batch
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
            batch = []

    for i, (sha, ts, blob) in enumerate(iter_blobs(commits)):
        commit_time = datetime.fromtimestamp(ts, tz=timezone.utc)
        status, items = "ok", None
        if blob is None:
            status = "missing"
        else:
            try:
                items = orjson.loads(blob)
                if not isinstance(items, list):
                    status, items = "not_a_list", None
            except orjson.JSONDecodeError:
                status = "bad_json"
        commit_rows.append({"commit_sha": sha, "commit_time": commit_time, "status": status,
                            "n_listings": len(items) if items is not None else None})
        if items is None:
            continue  # skip unparseable versions; don't treat them as mass removals

        batch_before = len(batch)
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            key = listing_key(item)
            if key is None or key in seen:
                continue
            seen.add(key)
            fp = fingerprint(item)
            prev = state.get(key)
            if prev is None:
                batch.append(make_row(key, "added", sha, commit_time, item))
            elif prev[0] != fp:
                batch.append(make_row(key, "changed", sha, commit_time, item))
            else:
                continue
            state[key] = (fp, item)

        for key in [k for k in state if k not in seen]:
            batch.append(make_row(key, "removed", sha, commit_time, state.pop(key)[1]))

        n_events += len(batch) - batch_before  # batch carries rows from earlier commits until flushed
        if len(batch) >= 50_000:
            flush()
        if i % 500 == 0:
            print(f"  {i}/{len(commits)} {commit_time:%Y-%m-%d} listings={len(items)} events={n_events}", file=sys.stderr)

    flush()
    writer.close()
    pq.write_table(
        pa.Table.from_pylist(commit_rows, schema=pa.schema([
            ("commit_sha", pa.string()), ("commit_time", pa.timestamp("s", tz="UTC")),
            ("status", pa.string()), ("n_listings", pa.int64()),
        ])),
        OUT_DIR / "commits.parquet",
    )
    print(f"done: {n_events} events from {len(commits)} commits -> {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="git fetch before extracting")
    extract(parser.parse_args().refresh)
