"""Tracker 1.4: postings -> one row per company per Summer cycle (the openings table).

Reads  DATA_DIR/history/observations.parquet, DATA_DIR/postings.parquet,
       DATA_DIR/simplify_lag.parquet + board_coverage.parquet (from lag, optional)
Writes DATA_DIR/openings.parquet, DATA_DIR/openings.csv

Opening = first SWE-intern posting per company per Summer cycle (Daniel, 2026-10-04).
Rules (Daniel, 2026-10-08; see docs/data-notes.md):
  1. A posting counts toward every Summer cycle in its latest terms, from the first commit that
     tagged it with that cycle (`tagged_at`). This covers multi_cycle postings (rolling, tagged
     for several Summers) and terms_changed postings (reused, counted from the relabel date).
  2. Openings already in the very first commit (2023-08-02) are left-censored: "on or before".
  3. Nothing is dropped for coverage; `board_misses_2027` and `cycles_open` flag it instead.
  4. A tag only counts inside the cycle's window, Jan 1 of the year before through Aug 31 of the
     cycle year. Outside it the tag is a data error or a rolling post, not an opening: e.g.
     General Motors tagged Summer 2024 in Jan 2026, Amazon's rolling post tagged Summer 2027 in
     Oct 2024. Counted in `n_out_of_window`.
  5. SWE intern postings with no season (terms "N/A", common from 2026) count toward the Summer
     after them: first seen Jul 1 of the year before the cycle through Jun 30 of the cycle, from
     first_seen. E.g. Jane Street's Summer 2027 SWE intern, posted 2026-08-03 with terms N/A.
Postings added already closed (backfilled; first_seen says when Simplify found it, not when it
opened) don't set an opening date.

Columns
  company_name, cycle           one row per company (any SWE posting counted in CYCLES) x cycle
  status          opened / opened_by (left-censored) / not_yet (current cycle, right-censored)
                  / none (past cycle, nothing seen: didn't hire, or Simplify missed it)
                  / backfilled (only postings Simplify added already closed; no usable date)
  opened_at       first tagged_at among the company's SWE postings for the cycle
  opened_doy      days from Jan 1 of the year before the cycle (Summer 2027 -> from 2026-01-01);
                  comparable across cycles. Negative = opened more than a year before Summer.
  first_listing_id, first_title, first_url    the posting that set opened_at
  via_multi_cycle the opening posting is tagged for several Summers (date may be early)
  via_relabel     the opening posting was relabeled into this cycle
  opened_at_excl_multi  opened_at ignoring multi_cycle postings (rolling posts can set a cycle's
                  opening years early, e.g. Amazon Summer 2027 via an Oct 2024 rolling post)
  via_unlabeled   the opening posting had no season (rule 5)
  n_swe_postings  SWE postings for the company in the cycle
  n_out_of_window of those, tagged outside the cycle's window (rule 4; not used for opened_at)
  cycles_open     cycles (of CYCLES) in which the company has an opening
  board_misses_2027  company's Greenhouse/Ashby/Lever board has a 2027-cycle SWE intern post
                  Simplify doesn't (from 1.3; only companies 1.3 could match to a board)
  as_of           last commit in the data (right-censoring time)

Run:  uv run python -m primora_pipeline.openings
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from primora_pipeline.paths import DATA_DIR

OBSERVATIONS = DATA_DIR / "history" / "observations.parquet"
POSTINGS = DATA_DIR / "postings.parquet"
LAG = DATA_DIR / "simplify_lag.parquet"
COVERAGE = DATA_DIR / "board_coverage.parquet"
OPENINGS = DATA_DIR / "openings.parquet"

# Full Summer cycles in the history (starts 2023-08-02) plus the current one. 2023 and 2028
# have only stray postings.
CYCLES = (2024, 2025, 2026, 2027)
CURRENT_CYCLE = 2027


def build(observations: Path = OBSERVATIONS, postings: Path = POSTINGS, out: Path = OPENINGS,
          lag: Path = LAG, coverage: Path = COVERAGE) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"create or replace view obs as select * from read_parquet('{observations}')")
    con.execute(f"create or replace view postings as select * from read_parquet('{postings}')")
    first_commit, as_of = con.execute("select min(commit_time), max(commit_time) from obs").fetchone()
    cycles = ", ".join(map(str, CYCLES))

    # Company's own board has a 2027-cycle SWE intern post that Simplify doesn't have.
    if lag.exists() and coverage.exists():
        con.execute(f"""
        create or replace table gaps as
        select distinct l.company_name
        from read_parquet('{coverage}') c
        join (select distinct company_name, ats, board from read_parquet('{lag}')) l using (ats, board)
        where c.company_date >= '2026-01-01' and not c.in_simplify
        """)
    else:
        con.execute("create or replace table gaps (company_name varchar)")

    con.execute(f"""
    create or replace table openings as
    with tags as (  -- first commit that tagged each listing with each Summer year
        select o.listing_id, try_cast(regexp_extract(t, 'Summer (\\d{{4}})', 1) as int) as cycle,
               min(o.commit_time) as tagged_at
        from obs o, unnest(o.terms) as u(t)
        where o.event <> 'removed' and t like 'Summer %'
        group by 1, 2
    ),
    swe as (  -- SWE postings x every Summer cycle in their latest terms
        select p.listing_id, p.company_name, p.title, p.url, p.multi_cycle, p.added_closed,
               t.cycle, t.tagged_at,
               t.tagged_at > p.first_seen as relabeled, false as unlabeled
        from postings p
        join tags t on t.listing_id = p.listing_id
            and list_contains(p.terms, 'Summer ' || t.cycle)
        where p.is_swe and t.cycle in ({cycles})
        union all  -- no season: the Summer after first_seen (Jul-Jun)
        select listing_id, company_name, title, url, false, added_closed,
               year(first_seen) + (month(first_seen) >= 7)::int as cycle, first_seen,
               false, true
        from postings
        where is_swe and season = 'unknown' and regexp_matches(lower(title), 'intern|co-?op')
          and year(first_seen) + (month(first_seen) >= 7)::int in ({cycles})
    ),
    windowed as (
        select *, tagged_at >= make_date(cycle - 1, 1, 1) and tagged_at < make_date(cycle, 9, 1)
                  and not added_closed as usable
        from swe
    ),
    firsts as (
        select company_name, cycle,
               count(*) as n_swe_postings,
               count(*) filter (where not usable and not added_closed) as n_out_of_window,
               arg_min(listing_id, tagged_at) filter (where usable) as first_listing_id,
               min(tagged_at) filter (where usable) as opened_at,
               min(tagged_at) filter (where usable and not multi_cycle) as opened_at_excl_multi
        from windowed group by 1, 2
    ),
    grid as (
        select c.company_name, y.cycle
        from (select distinct company_name from swe) c,
             (select unnest([{cycles}]) as cycle) y
    )
    select
        g.company_name, g.cycle,
        case
            when f.opened_at = timestamptz '{first_commit.isoformat()}' then 'opened_by'
            when f.opened_at is not null then 'opened'
            when f.n_swe_postings > f.n_out_of_window then 'backfilled'
            when g.cycle = {CURRENT_CYCLE} then 'not_yet'
            else 'none'
        end as status,
        f.opened_at,
        date_diff('day', make_date(g.cycle - 1, 1, 1), f.opened_at::date) as opened_doy,
        f.first_listing_id, s.title as first_title, s.url as first_url,
        coalesce(s.multi_cycle, false) as via_multi_cycle,
        coalesce(s.relabeled, false) as via_relabel,
        coalesce(s.unlabeled, false) as via_unlabeled,
        f.opened_at_excl_multi,
        coalesce(f.n_swe_postings, 0) as n_swe_postings,
        coalesce(f.n_out_of_window, 0) as n_out_of_window,
        count(f.opened_at) over (partition by g.company_name) as cycles_open,
        g.company_name in (select company_name from gaps) as board_misses_2027,
        timestamptz '{as_of.isoformat()}' as as_of
    from grid g
    left join firsts f using (company_name, cycle)
    left join swe s on s.listing_id = f.first_listing_id and s.cycle = g.cycle
    order by g.company_name, g.cycle
    """)
    con.execute(f"copy openings to '{out}' (format parquet, compression zstd)")
    con.execute(f"copy openings to '{out.with_suffix('.csv')}' (header)")
    n, n_co = con.execute("select count(*), count(distinct company_name) from openings").fetchone()
    print(f"openings: {n} rows, {n_co} companies -> {out}", file=sys.stderr)
    return con


def report(con: duckdb.DuckDBPyConnection) -> None:
    print(con.sql("""
        select cycle, status, count(*) as companies,
               count(*) filter (where via_multi_cycle) as via_multi_cycle,
               count(*) filter (where via_relabel) as via_relabel,
               count(*) filter (where via_unlabeled) as via_unlabeled
        from openings group by all order by all"""))


if __name__ == "__main__":
    report(build())
