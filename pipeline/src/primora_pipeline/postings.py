"""Tracker 1.2: change events -> one row per listing (the postings table).

Reads  DATA_DIR/history/observations.parquet  (from extract_history)
Writes DATA_DIR/postings.parquet

Columns
  listing_id, company_name, title, url, source        latest values seen
  category        Simplify's category, normalized (software / ai_ml_data / hardware / quant /
                  product / other). NULL before May 2025: Simplify had no categories then.
  is_swe          title matches SWE_TITLE_PATTERN. Used for "opening" (Daniel, 2026-10-04: first
                  SWE-intern posting per company per cycle). A title rule, not the category,
                  so every cycle is labeled the same way. See docs/data-notes.md.
  terms           latest terms list; cycle = earliest "Summer YYYY" in it (NULL if none)
  season          summer / off_season / unknown
  multi_cycle     tagged with more than one Summer term (rolling postings, e.g. Amazon's SDE
                  listing tagged Fall 2025..2028 with "2025" in the title). cycle is ambiguous.
  terms_changed   terms differ between first and last sighting (cycle uses the latest terms)
  date_posted     Simplify's date_posted when first seen
  first_seen      commit time the listing first appeared
  first_seen_censored  true if it was already in the very first commit (real first_seen is earlier)
  lag_days        first_seen - date_posted, in days (how long Simplify's date trails the commit)
  closed_at       final close: the last time active went false and it never came back (or
                  first_seen if it was added closed and never opened). NULL if still active.
                  Not the first close: active flaps a lot (median false close ~6.5h, 90%
                  reopen within 8 days), likely Simplify's link checker. See data-notes.
  first_closed_at first time active went false (reference only)
  added_closed    listing first appeared already inactive (backfilled)
  n_reopens       times active went false -> true
  removed_at      commit time the listing was pruned from the file (NULL if still present)

Run:  uv run python -m primora_pipeline.postings
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from primora_pipeline.paths import DATA_DIR

OBSERVATIONS = DATA_DIR / "history" / "observations.parquet"
POSTINGS = DATA_DIR / "postings.parquet"

# Lowercased title match. Tuned against Simplify's categories (May 2025 on); see data-notes.
SWE_TITLE_PATTERN = (
    r"(software|\bswe\b|\bsde\b|developer|programmer|programming|full[- ]?stack|back[- ]?end"
    r"|front[- ]?end|\bweb\b|mobile|\bios\b|android|devops|site reliability|\bsre\b"
    r"|platform eng|infrastructure eng|cloud eng|forward deployed|application develop"
    r"|database eng|compiler)"
)

CATEGORY_MAP = {
    "Software": "software", "Software Engineering": "software",
    "AI/ML/Data": "ai_ml_data", "Data Science, AI & Machine Learning": "ai_ml_data",
    "Hardware": "hardware", "Hardware Engineering": "hardware",
    "Quant": "quant", "Quantitative Finance": "quant",
    "Product": "product", "Product Management": "product",
    "Other": "other", "None": "other",
}


def build(observations: Path = OBSERVATIONS, out: Path = POSTINGS) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"create or replace view obs as select * from read_parquet('{observations}')")
    con.execute("create or replace temp table category_map (raw varchar, category varchar)")
    con.executemany("insert into category_map values (?, ?)", list(CATEGORY_MAP.items()))
    first_commit = con.execute("select min(commit_time) from obs").fetchone()[0]

    con.execute(f"""
    create or replace table postings as
    with ordered as (
        select *,
            lag(active) over (partition by listing_id order by commit_time) as prev_active
        from obs where event <> 'removed'
    ),
    per_listing as (
        select
            listing_id,
            last(company_name order by commit_time) as company_name,
            last(title order by commit_time) as title,
            last(url order by commit_time) as url,
            last(source order by commit_time) as source,
            last(category order by commit_time) filter (where category is not null) as category_raw,
            last(terms order by commit_time) as terms,
            first(terms order by commit_time) as first_terms,
            first(date_posted order by commit_time) as date_posted,
            min(commit_time) as first_seen,
            first(active order by commit_time) as first_active,
            min(commit_time) filter (where not active and prev_active) as first_closed,
            max(commit_time) filter (where not active and prev_active) as last_closed,
            last(active order by commit_time) as final_active,
            count(*) filter (where active and prev_active = false) as n_reopens
        from ordered group by listing_id
    ),
    removed as (
        select listing_id, max(commit_time) as removed_at from obs where event = 'removed' group by 1
    ),
    -- a listing can be removed and come back; only count removal if it's the last event
    last_event as (
        select listing_id, last(event order by commit_time) as last_event from obs group by 1
    )
    select
        p.listing_id, p.company_name, p.title, p.url, p.source,
        m.category,
        regexp_matches(lower(p.title), '{SWE_TITLE_PATTERN}') as is_swe,
        p.terms,
        (select min(cast(regexp_extract(t, 'Summer (\\d{{4}})', 1) as int))
           from unnest(p.terms) as u(t) where t like 'Summer %') as cycle,
        case
            when p.terms is null or len(p.terms) = 0 or p.terms = ['N/A'] then 'unknown'
            when len(list_filter(p.terms, t -> t like 'Summer %')) > 0 then 'summer'
            else 'off_season'
        end as season,
        len(list_filter(p.terms, t -> t like 'Summer %')) > 1 as multi_cycle,
        p.terms is distinct from p.first_terms as terms_changed,
        p.date_posted,
        p.first_seen,
        p.first_seen = timestamptz '{first_commit.isoformat()}' as first_seen_censored,
        round(epoch(p.first_seen - p.date_posted) / 86400.0, 2) as lag_days,
        case
            when p.final_active then null
            when p.last_closed is null then p.first_seen  -- added closed, never opened
            else p.last_closed
        end as closed_at,
        case when not p.first_active then p.first_seen else p.first_closed end as first_closed_at,
        not p.first_active as added_closed,
        p.n_reopens,
        case when le.last_event = 'removed' then r.removed_at end as removed_at
    from per_listing p
    left join category_map m on m.raw = p.category_raw
    left join removed r using (listing_id)
    left join last_event le using (listing_id)
    """)
    con.execute(f"copy postings to '{out}' (format parquet, compression zstd)")
    n = con.execute("select count(*) from postings").fetchone()[0]
    print(f"postings: {n} rows -> {out}", file=sys.stderr)
    return con


if __name__ == "__main__":
    build()
