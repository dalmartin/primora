"""Tracker 1.5: company metadata (tier + group) for every company in the openings table.

Reads  DATA_DIR/openings.parquet, reference/company_labels.csv, reference/company_aliases.csv
Writes DATA_DIR/companies.parquet, DATA_DIR/companies.csv

Labels come from reference/company_labels.csv (hand-curated; edit it there). Companies it
doesn't cover get a group from GROUP_RULES (keywords in the name) or "other", and tier "none".

Columns
  company_key, company_name    as in openings
  tier            prestige / pipeline / none  (PRD FR-4)
  group           big_tech / quant / finance / fintech / ai / software / hardware_semis /
                  defense_aerospace / auto_mobility / health / consumer_media / industrial_energy /
                  telecom / consulting_services / gov_research / other
  label_source    hand (company_labels.csv) / rule (GROUP_RULES) / default
  cycles_open, swe_postings, speedyapply_postings   from openings
  median_open_doy median opening day across cycles (days from Jan 1 of the year before Summer)

Run:  uv run python -m primora_pipeline.companies
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from primora_pipeline.openings import ALIASES, COMPANY_KEY, OPENINGS
from primora_pipeline.paths import DATA_DIR

LABELS = Path(__file__).resolve().parents[2] / "reference" / "company_labels.csv"
COMPANIES = DATA_DIR / "companies.parquet"

# First match wins; lowercase name, regex. Only for companies without a hand label.
GROUP_RULES = [
    ("quant", r"trading|quant|securities\b"),
    ("gov_research", r"universit|college|national lab|laborator(y|ies)\b.*national|federal reserve"
                     r"|state of |county|city of|commonwealth of|government|institute|foundation\b"),
    ("finance", r"bank|capital\b|financial|insurance|asset management|investment|invest\b|mutual"
                r"|credit|fund\b|funds\b|wealth|lending|mortgage|payments?\b|exchange\b|assurance"),
    ("health", r"health|medical|medic|bio|pharma|therapeutic|clinic|hospital|surgical|genom|diagnos"
               r"|dental|vision care|life ?sciences|molecular|care\b"),
    ("defense_aerospace", r"aerospace|defen[cs]e|space\b|aviation|aero\b|aeronaut|missile|satellite"
                          r"|federal\b|orbital|launch"),
    ("ai", r"\bai\b|\.ai\b|machine learning|intelligence\b"),
    ("hardware_semis", r"semiconductor|silicon|microelectronic|electronics|photonic|chips?\b|instruments"),
    ("auto_mobility", r"motors?\b|automotive|robotic|autonomous|vehicle|mobility|\bauto\b|truck"),
    ("industrial_energy", r"energy|power\b|electric|oil\b|gas\b|nuclear|fusion|solar|manufactur"
                          r"|industr|engineering|construction|logistics|freight|steel|chemical"
                          r"|materials|water\b|utilit|machine"),
    ("telecom", r"telecom|wireless|communications|networks?\b|broadband"),
    ("consulting_services", r"consult|advisors|advisory|partners\b|associates\b|staffing"),
    ("consumer_media", r"games|gaming|studios?\b|entertainment|media|sports|foods?\b|brands|retail"
                       r"|apparel|airlines?\b|hotels?|restaurant|music"),
    ("software", r"software|technolog|tech\b|labs?\b|systems\b|data\b|cloud|digital|\bapps?\b|\.io\b"),
]


def build(openings: Path = OPENINGS, labels: Path = LABELS, aliases: Path = ALIASES,
          out: Path = COMPANIES) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    key = COMPANY_KEY.format(col="company_name")
    con.execute(f"""
    create or replace table aliases as
    select distinct {COMPANY_KEY.format(col='alias')} as alias_key,
                    {COMPANY_KEY.format(col='canonical')} as canonical_key
    from read_csv('{aliases}', header = true, all_varchar = true)
    """)
    con.execute(f"""
    create or replace table labels as
    select coalesce(a.canonical_key, l.k) as company_key, l.company_name as label_name, tier, "group"
    from (select *, {key} as k from read_csv('{labels}', header = true, all_varchar = true)) l
    left join aliases a on a.alias_key = l.k
    """)
    con.execute("create or replace temp table rules (pos int, grp varchar, pattern varchar)")
    con.executemany("insert into rules values (?, ?, ?)",
                    [(i, g, p) for i, (g, p) in enumerate(GROUP_RULES)])
    con.execute(f"""
    create or replace table companies as
    with o as (
        select company_key, any_value(company_name) as company_name,
               max(cycles_open) as cycles_open,
               sum(n_swe_postings) as swe_postings,
               sum(n_speedyapply_postings) as speedyapply_postings,
               median(opened_doy) filter (where status = 'opened') as median_open_doy
        from read_parquet('{openings}') group by 1
    ),
    hand as (  -- a label matches the company's key or its display name
        select o.company_key, any_value(l.tier) as tier, any_value(l."group") as "group"
        from o join labels l on l.company_key in (o.company_key, {key.replace("company_name", "o.company_name")})
        group by 1),
    ruled as (
        select o.company_key, arg_min(r.grp, r.pos) as grp
        from o join rules r on regexp_matches(lower(o.company_name), r.pattern)
        group by 1
    )
    select o.company_key, o.company_name,
           coalesce(h.tier, 'none') as tier,
           coalesce(h."group", r.grp, 'other') as "group",
           case when h.company_key is not null then 'hand'
                when r.grp is not null then 'rule' else 'default' end as label_source,
           o.cycles_open, o.swe_postings, o.speedyapply_postings, o.median_open_doy
    from o left join hand h using (company_key) left join ruled r using (company_key)
    order by o.company_key
    """)
    con.execute(f"copy companies to '{out}' (format parquet, compression zstd)")
    con.execute(f"copy companies to '{out.with_suffix('.csv')}' (header)")
    n = con.execute("select count(*) from companies").fetchone()[0]
    print(f"companies: {n} rows -> {out}", file=sys.stderr)
    return con


def report(con: duckdb.DuckDBPyConnection) -> None:
    print(con.sql("""select label_source, tier, count(*) as companies from companies
                     group by all order by all"""))
    print(con.sql("""select "group", count(*) as companies,
                            count(*) filter (where label_source = 'hand') as hand
                     from companies group by all order by companies desc"""))
    unmatched = con.sql("""select label_name from labels
                           where company_key not in (select company_key from companies)
                           order by 1""").fetchall()
    print(f"{len(unmatched)} hand labels match no company in the data (fine: not hiring on these lists)")


if __name__ == "__main__":
    report(build())
