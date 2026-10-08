"""Second source: speedyapply/2027-SWE-College-Jobs (renamed from 2025-/2026-SWE-College-Jobs).

speedyapply keeps its data in its own database; the repo only has the markdown tables built from
it, about one commit a day since 2024-01-01. So we parse every version of the internship tables
(README.md = USA, INTERN_INTL.md / INTERN_USA.md) and record when each posting first appeared.

Writes DATA_DIR/speedyapply_postings.parquet, one row per posting URL:
  url             the "Apply" link (key)
  company_name, title, location, salary   from the first sighting
  region          usa / intl
  list_year       year in the list's heading ("## 2027 USA SWE Internships") at first sighting.
                  The list is for that Summer; the heading flips to the next year around Aug.
  first_seen      commit time of the first snapshot that has it (daily granularity)
  last_seen       commit time of the last snapshot that has it
  age_days        the table's "Age" column at first sighting (days since the posting went up,
                  per speedyapply). Large when speedyapply adds an old posting.
  posted_est      first_seen - age_days: speedyapply's idea of when the company posted it
  n_snapshots     snapshots it appears in

Run:  uv run python -m primora_pipeline.speedyapply [--refresh]
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from datetime import datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from primora_pipeline.paths import DATA_DIR

REPO_URL = "https://github.com/speedyapply/2027-SWE-College-Jobs.git"
REPO = DATA_DIR / "raw" / "speedyapply.git"
OUT = DATA_DIR / "speedyapply_postings.parquet"
FILES = {"README.md": "usa", "INTERN_USA.md": "usa", "INTERN_INTL.md": "intl"}

HEADING = re.compile(r"^## (\d{4}) (?:USA|International)? ?SWE Internships", re.M)
COMPANY = re.compile(r"<strong>(.*?)</strong>")
HREF = re.compile(r'href="([^"]+)"')
AGE = re.compile(r"^(\d+)d$")


def git(*args: str) -> str:
    return subprocess.run(["git", f"--git-dir={REPO}", *args], check=True,
                          capture_output=True, text=True).stdout


def ensure_repo(refresh: bool) -> None:
    if not REPO.exists():
        REPO.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--bare", "--quiet", REPO_URL, str(REPO)], check=True)
    elif refresh:
        git("fetch", "--quiet", "origin", "+refs/heads/*:refs/heads/*")


def parse_rows(text: str) -> list[dict]:
    """Internship table rows: | company | position | location | [salary |] posting | age |"""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| <a") or "<strong>" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) not in (5, 6):
            continue
        company = COMPANY.search(cells[0])
        link = HREF.search(cells[-2])
        age = AGE.match(cells[-1])
        if not (company and link):
            continue
        rows.append({
            "url": html.unescape(link.group(1)).strip(),
            "company_name": html.unescape(company.group(1)).strip(),
            "title": " ".join(html.unescape(cells[1]).split()),
            "location": html.unescape(cells[2]).strip(),
            "salary": cells[3] if len(cells) == 6 else None,
            "age_days": int(age.group(1)) if age else None,
        })
    return rows


def extract(refresh: bool = False) -> None:
    ensure_repo(refresh)
    log = git("log", "--reverse", "--format=%H %cI", "HEAD", "--", *FILES)
    commits = [(sha, datetime.fromisoformat(t)) for sha, t in (l.split() for l in log.splitlines())]
    seen: dict[str, dict] = {}
    blobs: dict[str, list[dict]] = {}  # blob sha -> parsed rows (most files don't change per commit)
    for sha, t in commits:
        tree = git("ls-tree", sha, "--", *FILES)
        for entry in tree.splitlines():
            meta, path = entry.split("\t")
            blob = meta.split()[2]
            if blob not in blobs:
                text = git("cat-file", "blob", blob)
                year = HEADING.search(text)
                blobs[blob] = [{**r, "list_year": int(year.group(1)) if year else None}
                               for r in parse_rows(text)]
            for r in blobs[blob]:
                s = seen.get(r["url"])
                if s is None:
                    seen[r["url"]] = {**r, "region": FILES[path], "first_seen": t, "last_seen": t,
                                      "snapshots": {sha}}
                else:
                    s["last_seen"] = max(s["last_seen"], t)
                    s["snapshots"].add(sha)
    rows = []
    for s in seen.values():
        n = len(s.pop("snapshots"))
        age = s["age_days"]
        rows.append({**s, "n_snapshots": n,
                     "posted_est": s["first_seen"] - timedelta(days=age) if age is not None else None})
    pq.write_table(pa.Table.from_pylist(rows), OUT, compression="zstd")
    print(f"speedyapply: {len(commits)} commits, {len(blobs)} distinct files, "
          f"{len(rows)} postings -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="fetch new commits first")
    extract(ap.parse_args().refresh)
