"""Tracker 1.3: how far Simplify's dates trail the company's own posting date.

Reads  DATA_DIR/postings.parquet  (from postings)
Writes DATA_DIR/raw/boards/<ats>/<board>.json   normalized jobs per board (cache; --refetch to redo)
       DATA_DIR/simplify_lag.parquet            one row per SWE posting matched on its board
       DATA_DIR/board_coverage.parquet          SWE summer-intern jobs on those boards, and whether
                                                Simplify has them

Only Greenhouse, Ashby and Lever expose a company-side date, and only for jobs still on the
board, so closed postings from past cycles mostly can't be checked. Company date per ATS:
  greenhouse  first_published  (when the job post was first published)
  ashby       publishedAt
  lever       createdAt        (when the posting was created; can predate publishing)

Columns (simplify_lag)
  listing_id, company_name, title, cycle, ats, board, job_id
  company_date    the ATS date above
  first_seen      Simplify commit time the listing first appeared (from postings)
  date_posted     Simplify's own date_posted (from postings)
  lag_days        first_seen - company_date, in days. Negative = company date is after Simplify
                  saw it (the post was republished, which resets the date).

Run:  uv run python -m primora_pipeline.lag          (add --refetch to ignore the cache)
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from primora_pipeline.paths import DATA_DIR
from primora_pipeline.postings import POSTINGS, SWE_TITLE_PATTERN

BOARDS_DIR = DATA_DIR / "raw" / "boards"
LAG = DATA_DIR / "simplify_lag.parquet"
COVERAGE = DATA_DIR / "board_coverage.parquet"

# url pattern -> (ats, board, job_id). Board names are case-insensitive on all three.
URL_PATTERNS = {
    "greenhouse": r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?#]+)/jobs/(\d+)",
    "ashby": r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})",
    "lever": r"jobs\.lever\.co/([^/?#]+)/([0-9a-f-]{36})",
}

BOARD_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json",
}


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "primora-research/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": e.code}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"_error": str(e)}


def fetch_board(ats: str, board: str, refetch: bool = False) -> list[dict] | None:
    """Jobs on a board, normalized; None if the board is gone. Caches only the normalized
    fields (full responses carry job descriptions: ~460 MB for all boards)."""
    path = BOARDS_DIR / ats / f"{board}.json"
    if path.exists() and not refetch:
        return json.loads(path.read_text())
    data = _get_json(BOARD_URLS[ats].format(board=board))
    jobs = None if isinstance(data, dict) and "_error" in data else board_jobs(ats, data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs))
    return jobs


def board_jobs(ats: str, data) -> list[dict]:
    """Normalize a board response to [{job_id, title, company_date}]."""
    if ats == "greenhouse":
        return [{"job_id": str(j["id"]), "title": j["title"], "company_date": j.get("first_published")}
                for j in data.get("jobs", [])]
    if ats == "ashby":
        return [{"job_id": j["id"], "title": j["title"], "company_date": j.get("publishedAt")}
                for j in data.get("jobs", [])]
    if ats == "lever":
        return [{"job_id": j["id"], "title": j["text"],
                 "company_date": datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).isoformat()
                 if j.get("createdAt") else None}
                for j in data]
    raise ValueError(ats)


_NOT_BOARD = {"www", "careers", "career", "jobs", "job", "app", "com", "io", "co", "ai", "net",
              "org", "inc", "llc", "technologies", "group", "labs", "the", "us", "en"}


def _board_candidates(company: str, host: str) -> list[str]:
    """Guesses at a Greenhouse board token from the company name and the careers-site host."""
    words = re.findall(r"[a-z0-9]+", company.lower())
    core = [w for w in words if w not in _NOT_BOARD]
    labels = [l for l in re.findall(r"[a-z0-9]+", host.lower()) if l not in _NOT_BOARD]
    cands = ["".join(words), "".join(core), *(core[:1]), *labels]
    return list(dict.fromkeys(c for c in cands if c))


def resolve_own_domain(con: duckdb.DuckDBPyConnection, refetch: bool = False) -> None:
    """Postings linking to a company's own site with a Greenhouse gh_jid (Waymo, Lyft, Roku...):
    find the board by guessing tokens and keep one only if it actually lists one of the jids."""
    groups = con.execute(r"""
        select company_name, regexp_extract(url, 'https?://([^/]+)', 1) as host,
               list(listing_id) as ids, list(regexp_extract(url, 'gh_jid=(\d+)', 1)) as jids
        from postings where url ilike '%gh_jid=%' and url not ilike '%greenhouse.io%'
        group by all""").fetchall()

    def resolve(group):
        company, host, ids, jids = group
        for cand in _board_candidates(company, host):
            jobs = fetch_board("greenhouse", cand, refetch)
            if jobs and set(jids) & {j["job_id"] for j in jobs}:
                return [(i, "greenhouse", cand, j) for i, j in zip(ids, jids)]
        return []

    with ThreadPoolExecutor(max_workers=8) as pool:
        found = [r for rows in pool.map(resolve, groups) for r in rows]
    con.executemany("insert into ats_postings values (?, ?, ?, ?)", found)
    print(f"own-domain Greenhouse: {len(found)} of {sum(len(g[2]) for g in groups)} postings "
          f"resolved to a board", file=sys.stderr)


def build(postings: Path = POSTINGS, refetch: bool = False, lag_out: Path = LAG,
          coverage_out: Path = COVERAGE) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"create or replace view postings as select * from read_parquet('{postings}')")
    parts = [
        f"select listing_id, '{ats}' as ats, lower(regexp_extract(url, '{pat}', 1)) as board, "
        f"regexp_extract(url, '{pat}', 2) as job_id from postings where regexp_matches(url, '{pat}')"
    for ats, pat in URL_PATTERNS.items()]
    con.execute(f"create or replace table ats_postings as {' union all '.join(parts)}")
    # EU Greenhouse boards have no reachable public API (boards-api.eu doesn't resolve).
    con.execute("delete from ats_postings where listing_id in "
                "(select listing_id from postings where url ilike '%.eu.greenhouse.io%')")
    resolve_own_domain(con, refetch)

    boards = con.execute("select distinct ats, board from ats_postings order by all").fetchall()
    print(f"fetching {len(boards)} boards", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda b: (b, fetch_board(*b, refetch=refetch)), boards))

    rows, failed = [], 0
    for (ats, board), jobs in results:
        if jobs is None:
            failed += 1
            continue
        rows += [(ats, board, j["job_id"], j["title"], j["company_date"]) for j in jobs]
    print(f"{len(rows)} jobs on boards; {failed} boards unreachable (gone or renamed)", file=sys.stderr)
    con.execute("create or replace table board_jobs (ats varchar, board varchar, job_id varchar, "
                "title varchar, company_date timestamptz)")
    con.executemany("insert into board_jobs values (?, ?, ?, ?, ?)", rows)

    con.execute("""
    create or replace table simplify_lag as
    select p.listing_id, p.company_name, p.title, p.cycle, a.ats, a.board, a.job_id,
           b.company_date, p.first_seen, p.date_posted,
           round(epoch(p.first_seen - b.company_date) / 86400.0, 2) as lag_days
    from ats_postings a
    join postings p using (listing_id)
    join board_jobs b on b.ats = a.ats and b.board = a.board and b.job_id = a.job_id
    where p.is_swe and b.company_date is not null
    """)

    # Coverage: SWE summer-intern jobs on boards Simplify already tracks; does Simplify have them?
    con.execute(f"""
    create or replace table board_coverage as
    select b.*, exists (select 1 from ats_postings a
                        where a.ats = b.ats and a.board = b.board and a.job_id = b.job_id) as in_simplify
    from board_jobs b
    where regexp_matches(lower(b.title), '{SWE_TITLE_PATTERN}')
      and regexp_matches(lower(b.title), '\\bintern(ship)?s?\\b')
      and not regexp_matches(lower(b.title), '(fall|spring|winter|co-?op)')
    """)

    con.execute(f"copy simplify_lag to '{lag_out}' (format parquet)")
    con.execute(f"copy board_coverage to '{coverage_out}' (format parquet)")
    for t in ("simplify_lag", "board_coverage"):
        print(f"{t}: {con.execute(f'select count(*) from {t}').fetchone()[0]} rows", file=sys.stderr)
    return con


# Lag buckets. fresh: a new post Simplify picked up within a week. late: picked up 1 week to
# 3 months after. evergreen: a years-old post reused for a new cycle (its date says nothing about
# this cycle's opening). republished: the company date reset after Simplify saw it (Ashby).
BUCKET = """case when lag_days < 0 then 'republished' when lag_days <= 7 then 'fresh'
                 when lag_days <= 90 then 'late' else 'evergreen' end"""

# Explicit Summer 2027 SWE intern posts first published this year (the opening question).
SUMMER_2027 = r"""(regexp_matches(lower(title), 'summer\s*2027|2027\s*summer')
    or (regexp_matches(title, '2027') and not regexp_matches(lower(title),
        '(january|jan |june|semester|h1|berlin|london|ireland|india|canada|iap)')))
    and company_date >= '2026-01-01'"""


def report(con: duckdb.DuckDBPyConnection) -> None:
    """The numbers in docs/data-notes.md (tracker 1.3)."""
    q = lambda sql: print(con.sql(sql))
    q(f"select {BUCKET} as bucket, count(*) n, round(count(*) / sum(count(*)) over (), 3) as pct "
      "from simplify_lag group by 1 order by 2 desc")
    q(f"""select ats, count(*) n, round(median(lag_days) * 24, 1) med_h,
          round(quantile_cont(lag_days, .75) * 24, 1) p75_h, round(quantile_cont(lag_days, .9) * 24, 1) p90_h
          from simplify_lag where {BUCKET} = 'fresh' group by rollup(ats) order by 1""")
    q(f"select ats, count(*) n, round(avg(in_simplify::int), 2) rate from board_coverage "
      f"where {SUMMER_2027} group by rollup(ats) order by 1")
    # Company level: board's first Summer 2027 SWE post vs Simplify's first SWE cycle-2027
    # posting on that board. This is what an "opening" date error looks like.
    q(f"""with board_open as (
            select ats, board, min(company_date) as board_open from board_coverage
            where {SUMMER_2027} group by all),
          sim_open as (
            select a.ats, a.board, min(p.first_seen) as sim_open from ats_postings a
            join postings p using (listing_id) where p.is_swe and p.cycle = 2027 group by all),
          cmp as (
            select *, epoch(sim_open - board_open) / 86400 as err_days
            from board_open left join sim_open using (ats, board))
          select count(*) companies, count(sim_open) in_simplify,
            count(*) filter (where err_days between -1 and 1) within_1d,
            count(*) filter (where err_days > 1 and err_days <= 7) d1_7,
            count(*) filter (where err_days > 7) over_7d,
            count(*) filter (where err_days < -1) simplify_earlier,
            round(median(err_days), 2) med_days, round(quantile_cont(err_days, .9), 1) p90_days
          from cmp""")


if __name__ == "__main__":
    report(build(refetch="--refetch" in sys.argv))
