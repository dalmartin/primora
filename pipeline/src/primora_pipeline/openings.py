"""Tracker 1.4: postings -> one row per company per Summer cycle (the openings table).

Reads  DATA_DIR/history/observations.parquet, DATA_DIR/postings.parquet,
       DATA_DIR/speedyapply_postings.parquet (second source, optional),
       DATA_DIR/simplify_lag.parquet + board_coverage.parquet (from lag, optional)
Writes DATA_DIR/openings.parquet, DATA_DIR/openings.csv

Opening = first SWE-intern posting per company per Summer cycle (Daniel, 2026-10-04).
Rules (Daniel, 2026-10-08; see docs/data-notes.md):
  1. A posting counts toward every Summer cycle in its latest terms, from the first commit that
     tagged it with that cycle (`tagged_at`). This covers multi_cycle postings (rolling, tagged
     for several Summers) and terms_changed postings (reused, counted from the relabel date).
  2. Openings already in the very first commit (2023-08-02) are left-censored: "on or before".
     Same for speedyapply's first snapshot (2024-01-01) when its Age doesn't give a date.
  3. Nothing is dropped for coverage; `board_misses_2027` and `cycles_open` flag it instead.
  4. A tag only counts inside the cycle's window, Jan 1 of the year before through Aug 31 of the
     cycle year. Outside it the tag is a data error or a rolling post, not an opening: e.g.
     General Motors tagged Summer 2024 in Jan 2026, Amazon's rolling post tagged Summer 2027 in
     Oct 2024. Counted in `n_out_of_window`.
  5. SWE intern postings with no season (terms "N/A", common from 2026) count toward the Summer
     after them: first seen Jul 1 of the year before the cycle through Jun 30 of the cycle, from
     first_seen. E.g. Jane Street's Summer 2027 SWE intern, posted 2026-08-03 with terms N/A.
  6. speedyapply (Daniel, 2026-10-08) is a second source; a cycle's opening is the earliest
     date in either list. Its USA internship postings only, same SWE title rule, minus titles
     naming another season (Fall / Spring / Winter, no Summer). Date = speedyapply's posted
     date (first_seen - Age) when Age <= SPEEDY_MAX_AGE days, else first_seen (old postings
     added late are often evergreen). Cycle = the Summer year in the title, else the Summer
     after the date (Jul-Jun). Rule 4's window applies.
Companies are matched across lists by a normalized name (`company_key`: lowercase, punctuation
and suffixes like Inc / LLC / Corp dropped), then merged by the hand-checked alias list
`reference/company_aliases.csv` ("JP Morgan Chase" -> "JPMorgan Chase"), plus a unique
word-prefix match for speedyapply names Simplify spells longer or shorter, when the extra words
are generic (PREFIX_SUFFIXES: "Dell" / "Dell Technologies", not "Southern" / "Southern Poverty
Law Center").
Postings added already closed (backfilled; first_seen says when Simplify found it, not when it
opened) don't set an opening date.

Columns
  company_key, cycle            one row per company (any SWE posting counted in CYCLES) x cycle
  company_name    display name: the alias list's canonical, else Simplify's most common
                  spelling, else speedyapply's
  status          opened / opened_by (left-censored) / not_yet (current cycle, right-censored)
                  / none (past cycle, nothing seen: didn't hire, or Simplify missed it)
                  / backfilled (only postings Simplify added already closed; no usable date)
  opened_at       first tagged_at among the company's SWE postings for the cycle, either list
  opened_source   simplify / speedyapply: which list set opened_at
  opened_at_simplify, opened_at_speedyapply   each list's own opening date
  opened_doy      days from Jan 1 of the year before the cycle (Summer 2027 -> from 2026-01-01);
                  comparable across cycles. Negative = opened more than a year before Summer.
  first_listing_id, first_title, first_url    the posting that set opened_at
  via_multi_cycle (Simplify) the opening posting is tagged for several Summers (date may be early)
  via_relabel     the opening posting was relabeled into this cycle
  opened_at_excl_multi  opened_at ignoring multi_cycle postings (rolling posts can set a cycle's
                  opening years early, e.g. Amazon Summer 2027 via an Oct 2024 rolling post)
  via_unlabeled   the opening posting had no season (rule 5)
  n_swe_postings  SWE postings for the company in the cycle (Simplify)
  n_speedyapply_postings  same, speedyapply
  n_out_of_window of all those, dated outside the cycle's window (rule 4; not used for opened_at)
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
from primora_pipeline.postings import SWE_TITLE_PATTERN

OBSERVATIONS = DATA_DIR / "history" / "observations.parquet"
POSTINGS = DATA_DIR / "postings.parquet"
LAG = DATA_DIR / "simplify_lag.parquet"
COVERAGE = DATA_DIR / "board_coverage.parquet"
SPEEDYAPPLY = DATA_DIR / "speedyapply_postings.parquet"
OPENINGS = DATA_DIR / "openings.parquet"
ALIASES = Path(__file__).resolve().parents[2] / "reference" / "company_aliases.csv"

# Full Summer cycles in the history (starts 2023-08-02) plus the current one. 2023 and 2028
# have only stray postings.
CYCLES = (2024, 2025, 2026, 2027)
CURRENT_CYCLE = 2027
SPEEDY_MAX_AGE = 14

PREFIX_SUFFIXES = (r"^( (technologies|technology|tech|systems|group|international|holdings|industries"
                   r"|global|motors|software|solutions|corporation|communications|financial|services"
                   r"|labs|health|usa|us|america|north america|ai|research|networks|semiconductor"
                   r"|aerospace|robotics|therapeutics|biosciences|energy|capital|studios|games"
                   r"|interactive|digital|enterprises|medical|pharmaceuticals?|automation|engineering))+$")

COMPANY_KEY = r"""trim(regexp_replace(regexp_replace(regexp_replace(
    lower(replace({col}, '&', ' and ')), '[^a-z0-9 ]', ' ', 'g'),
    '\b(inc|llc|ltd|corp|corporation|co|company|plc|the|lp|llp|gmbh|limited|incorporated)\b',
    '', 'g'), ' +', ' ', 'g'))"""


def build(observations: Path = OBSERVATIONS, postings: Path = POSTINGS, out: Path = OPENINGS,
          lag: Path = LAG, coverage: Path = COVERAGE,
          speedyapply: Path = SPEEDYAPPLY, aliases: Path = ALIASES) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"create or replace view obs as select * from read_parquet('{observations}')")
    con.execute(f"""
    create or replace table aliases as
    select distinct {COMPANY_KEY.format(col='alias')} as alias_key,
                    {COMPANY_KEY.format(col='canonical')} as canonical_key, trim(canonical) as canonical
    from read_csv('{aliases}', header = true, all_varchar = true)
    """)
    key = (f"coalesce((select canonical_key from aliases where alias_key = "
           f"{COMPANY_KEY.format(col='company_name')}), {COMPANY_KEY.format(col='company_name')})")
    con.execute(f"create or replace table postings as select *, {key} as company_key "
                f"from read_parquet('{postings}')")
    if speedyapply.exists():
        con.execute(f"create or replace table speedy as select *, {key} as raw_key "
                    f"from read_parquet('{speedyapply}') where region = 'usa'")
    else:
        con.execute("create or replace table speedy (url varchar, company_name varchar, title varchar, "
                    "raw_key varchar, first_seen timestamptz, posted_est timestamptz, age_days int)")
    # speedyapply name -> Simplify company_key: exact, else the one Simplify key it word-prefixes
    con.execute(f"""
    create or replace table speedy_keys as
    with sk as (select distinct raw_key from speedy),
         pk as (select distinct company_key from postings),
         prefix as (
            select raw_key, min(company_key) as company_key
            from sk join pk on (pk.company_key like sk.raw_key || ' %' or sk.raw_key like pk.company_key || ' %')
            where least(length(raw_key), length(company_key)) >= 4
              and regexp_matches(
                    case when length(raw_key) > length(company_key)
                         then substr(raw_key, length(company_key) + 1)
                         else substr(company_key, length(raw_key) + 1) end,
                    '{PREFIX_SUFFIXES}')
              and raw_key not in (select company_key from pk)
            group by 1 having count(*) = 1)
    select sk.raw_key, coalesce(pk.company_key, prefix.company_key, sk.raw_key) as company_key
    from sk left join pk on pk.company_key = sk.raw_key left join prefix using (raw_key)
    """)
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
    speedy_swe as (
        select s.*, k.company_key,
               case when age_days <= {SPEEDY_MAX_AGE} then posted_est else first_seen end as dated,
               s.first_seen = (select min(first_seen) from speedy)
                   and coalesce(age_days > {SPEEDY_MAX_AGE}, true) as censored
        from speedy s join speedy_keys k using (raw_key)
        where regexp_matches(lower(title), '{SWE_TITLE_PATTERN}')
          and not (regexp_matches(lower(title), '\\b(fall|autumn|spring|winter)\\b')
                   and not regexp_matches(lower(title), '\\bsummer\\b'))
    ),
    swe as (  -- SWE postings x every Summer cycle in their latest terms
        select p.listing_id, p.company_key, p.company_name, p.title, p.url, p.multi_cycle,
               p.added_closed, t.cycle, t.tagged_at,
               t.tagged_at > p.first_seen as relabeled, false as unlabeled, 'simplify' as source,
               t.tagged_at = timestamptz '{first_commit.isoformat()}' as censored
        from postings p
        join tags t on t.listing_id = p.listing_id
            and list_contains(p.terms, 'Summer ' || t.cycle)
        where p.is_swe and t.cycle in ({cycles})
        union all  -- no season: the Summer after first_seen (Jul-Jun)
        select listing_id, company_key, company_name, title, url, false, added_closed,
               year(first_seen) + (month(first_seen) >= 7)::int as cycle, first_seen,
               false, true, 'simplify', first_seen = timestamptz '{first_commit.isoformat()}'
        from postings
        where is_swe and season = 'unknown' and regexp_matches(lower(title), 'intern|co-?op')
          and year(first_seen) + (month(first_seen) >= 7)::int in ({cycles})
        union all
        select url, company_key, company_name, title, url, false, false,
               coalesce(try_cast(regexp_extract(lower(title), 'summer\\D{{0,3}}(20\\d\\d)', 1) as int),
                        year(dated) + (month(dated) >= 7)::int) as cycle,
               dated, false, false, 'speedyapply', censored
        from speedy_swe
    ),
    windowed as (
        select *, tagged_at >= make_date(cycle - 1, 1, 1) and tagged_at < make_date(cycle, 9, 1)
                  and not added_closed as usable
        from swe
    ),
    firsts as (
        select company_key, cycle,
               count(*) filter (where source = 'simplify') as n_swe_postings,
               count(*) filter (where source = 'speedyapply') as n_speedyapply_postings,
               count(*) filter (where not usable and not added_closed) as n_out_of_window,
               arg_min(listing_id, tagged_at) filter (where usable) as first_listing_id,
               arg_min(source, tagged_at) filter (where usable) as opened_source,
               arg_min(censored, tagged_at) filter (where usable) as opened_censored,
               min(tagged_at) filter (where usable) as opened_at,
               min(tagged_at) filter (where usable and source = 'simplify') as opened_at_simplify,
               min(tagged_at) filter (where usable and source = 'speedyapply') as opened_at_speedyapply,
               min(tagged_at) filter (where usable and not multi_cycle) as opened_at_excl_multi
        from windowed group by 1, 2
    ),
    names as (  -- display name: the alias list's, else Simplify's most common, else speedyapply's
        select company_key,
               coalesce(any_value(a.canonical), arg_max(company_name, n)) as company_name from (
            select company_key, company_name,
                   count(*) filter (where source = 'simplify') * 1000000 + count(*) as n
            from swe group by 1, 2) left join aliases a on a.canonical_key = company_key group by 1
    ),
    grid as (
        select c.company_key, y.cycle
        from (select distinct company_key from swe) c,
             (select unnest([{cycles}]) as cycle) y
    )
    select
        g.company_key, n.company_name, g.cycle,
        case
            when f.opened_censored then 'opened_by'
            when f.opened_at is not null then 'opened'
            when f.n_swe_postings + f.n_speedyapply_postings > f.n_out_of_window then 'backfilled'
            when g.cycle = {CURRENT_CYCLE} then 'not_yet'
            else 'none'
        end as status,
        f.opened_at, f.opened_source, f.opened_at_simplify, f.opened_at_speedyapply,
        date_diff('day', make_date(g.cycle - 1, 1, 1), f.opened_at::date) as opened_doy,
        f.first_listing_id, s.title as first_title, s.url as first_url,
        coalesce(s.multi_cycle, false) as via_multi_cycle,
        coalesce(s.relabeled, false) as via_relabel,
        coalesce(s.unlabeled, false) as via_unlabeled,
        f.opened_at_excl_multi,
        coalesce(f.n_swe_postings, 0) as n_swe_postings,
        coalesce(f.n_speedyapply_postings, 0) as n_speedyapply_postings,
        coalesce(f.n_out_of_window, 0) as n_out_of_window,
        count(f.opened_at) over (partition by g.company_key) as cycles_open,
        n.company_name in (select company_name from gaps) as board_misses_2027,
        timestamptz '{as_of.isoformat()}' as as_of
    from grid g
    left join firsts f using (company_key, cycle)
    left join names n using (company_key)
    left join swe s on s.listing_id = f.first_listing_id and s.cycle = g.cycle
        and s.source = f.opened_source
    order by g.company_key, g.cycle
    """)
    con.execute(f"copy openings to '{out}' (format parquet, compression zstd)")
    con.execute(f"copy openings to '{out.with_suffix('.csv')}' (header)")
    n, n_co = con.execute("select count(*), count(distinct company_key) from openings").fetchone()
    print(f"openings: {n} rows, {n_co} companies -> {out}", file=sys.stderr)
    return con


def report(con: duckdb.DuckDBPyConnection) -> None:
    print(con.sql("""
        select cycle, status, count(*) as companies,
               count(*) filter (where via_multi_cycle) as via_multi_cycle,
               count(*) filter (where via_relabel) as via_relabel,
               count(*) filter (where via_unlabeled) as via_unlabeled,
               count(*) filter (where opened_source = 'speedyapply') as via_speedyapply
        from openings group by all order by all"""))


if __name__ == "__main__":
    report(build())
