"""Look at the openings table (tracker 1.4) as a table and a chart.

Writes data/openings_wide.csv: one row per company, one column per cycle (opened date), so it
opens cleanly in Excel / Numbers / Google Sheets. Then prints the top companies and shows a chart.

Markers in the table: "<=" opened on or before that date (history starts 2023-08-02);
"*" date set by a rolling post tagged for several Summers (may be early); "?" date set by a
posting with no season label on Simplify; "+" date from speedyapply (earlier than Simplify, or
Simplify missed it); "-" nothing seen; "not yet" = 2027 not open yet.

Run (from pipeline/):
  uv run python scripts/view_openings.py                  top 40 companies + chart
  uv run python scripts/view_openings.py --top 100        more rows
  uv run python scripts/view_openings.py jane google      only companies matching these words
  uv run python scripts/view_openings.py --no-plot        table only
"""
from __future__ import annotations

import argparse

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from primora_pipeline.paths import DATA_DIR

CYCLES = [2024, 2025, 2026, 2027]
COLORS = {2024: "#9aa5b1", 2025: "#4c78a8", 2026: "#f58518", 2027: "#e45756"}


def cell(r) -> str:
    if r.status == "opened_by":
        return f"<={r.opened_at:%Y-%m-%d}"
    if pd.notna(r.opened_at):
        mark = "*" if r.via_multi_cycle else "?" if r.via_unlabeled else ""
        return f"{r.opened_at:%Y-%m-%d}" + mark + ("+" if r.opened_source == "speedyapply" else "")
    return {"not_yet": "not yet", "backfilled": "seen, no date"}.get(r.status, "-")


def wide(o: pd.DataFrame) -> pd.DataFrame:
    o = o.assign(cell=[cell(r) for r in o.itertuples()])
    w = o.pivot(index="company_key", columns="cycle", values="cell")[CYCLES]
    w.columns = [f"summer_{c}" for c in CYCLES]
    stats = o.groupby("company_key").agg(company_name=("company_name", "first"),
                                         cycles_open=("cycles_open", "first"),
                                         swe_postings=("n_swe_postings", "sum"),
                                         speedyapply_postings=("n_speedyapply_postings", "sum"),
                                         board_misses_2027=("board_misses_2027", "first"))
    return (stats.join(w).reset_index(drop=True)
            .sort_values(["cycles_open", "swe_postings"], ascending=False, ignore_index=True))


def plot(o: pd.DataFrame, companies: list[str]) -> None:
    """Opening date within the season for each cycle, all cycles on one Jul-Jun axis."""
    d = o[o.company_name.isin(companies) & o.opened_at.notna()].copy()
    # shift every cycle onto the Summer 2027 season so dates line up (2027 stays as is)
    d["x"] = d.opened_at.dt.tz_localize(None) + pd.to_timedelta((2027 - d.cycle) * 365, unit="D")
    y = {c: i for i, c in enumerate(reversed(companies))}
    fig, ax = plt.subplots(figsize=(11, 0.28 * len(companies) + 1.5))
    for cyc in CYCLES:
        s = d[d.cycle == cyc]
        for multi, face in ((False, COLORS[cyc]), (True, "none")):
            m = s[s.via_multi_cycle == multi]
            ax.scatter(m.x, m.company_name.map(y), s=36, facecolors=face, edgecolors=COLORS[cyc],
                       label=f"Summer {cyc}" if not multi else None, zorder=3)
    ax.set_yticks(list(y.values()), list(y.keys()), fontsize=8)
    ax.set_xlim(pd.Timestamp("2026-01-01"), pd.Timestamp("2027-07-01"))
    ax.axvline(pd.Timestamp("2027-01-01"), color="gray", lw=0.8, ls="--")  # New Year before Summer
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.grid(axis="x", alpha=0.3)
    ax.set_title("First SWE-intern posting per cycle, by month (dashed = Jan 1 before the Summer;"
                 " hollow = rolling multi-Summer post)", fontsize=10)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    plt.show()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("search", nargs="*", help="words to match in company names")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    o = pd.read_parquet(DATA_DIR / "openings.parquet")
    w = wide(o)
    out = DATA_DIR / "openings_wide.csv"
    w.to_csv(out, index=False)

    if args.search:
        pat = "|".join(args.search)
        shown = w[w.company_name.str.contains(pat, case=False, regex=True)]
    else:
        shown = w.head(args.top)
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(shown.to_string(index=False))
    print(f"\n{len(w)} companies; full table -> {out}")
    if not args.no_plot and len(shown):
        plot(o, shown.company_name.head(60).tolist())


if __name__ == "__main__":
    main()
