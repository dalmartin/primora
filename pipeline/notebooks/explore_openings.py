# %% [markdown]
# # Tracker 1.6: when do SWE internships open?
# Exploratory look at the openings table (1.4) with company tiers and groups (1.5).
# Run top to bottom (`uv run python notebooks/explore_openings.py` from pipeline/) to redraw every
# chart into docs/figures/, or step through the cells in VS Code ("Run Cell").
# Written takeaways: docs/data-notes.md, "Exploratory analysis (tracker 1.6)".
#
# Day-of-season ("doy") = days from Jan 1 of the year before the Summer, so Summer 2027's
# Sep 1 2026 is doy 243 and every cycle shares one axis. The window is doy 0 (Jan 1) to 516 (May 31).

# %%
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from primora_pipeline.paths import DATA_DIR

FIG = Path(__file__).resolve().parents[2] / "docs" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
CYCLE_COLORS = {2024: "#9aa5b1", 2025: "#4c78a8", 2026: "#f58518", 2027: "#e45756"}
TIER_COLORS = {"prestige": "#e45756", "pipeline": "#4c78a8", "none": "#bab0ac"}
TODAY_DOY = (pd.Timestamp("2026-10-08") - pd.Timestamp("2026-01-01")).days

o = pd.read_parquet(DATA_DIR / "openings.parquet")
co = pd.read_parquet(DATA_DIR / "companies.parquet")[["company_key", "tier", "group"]]
o = o.merge(co, on="company_key")
opened = o[o.status == "opened"].copy()


def doy_axis(ax, axis="x"):
    """Label a day-of-season axis with month names (Summer 2027 calendar)."""
    ticks = [(pd.Timestamp(f"{y}-{m:02d}-01") - pd.Timestamp("2026-01-01")).days
             for y, m in [(2026, m) for m in range(1, 13)] + [(2027, m) for m in range(1, 7)]]
    labels = [pd.Timestamp("2026-01-01") + pd.Timedelta(days=t) for t in ticks]
    labels = [d.strftime("%b") + ("\n(yr before)" if d.month == 1 and d.year == 2026 else
                                  "\n(Summer yr)" if d.month == 1 else "") for d in labels]
    (ax.set_xticks if axis == "x" else ax.set_yticks)(ticks, labels, fontsize=8)


# %% [markdown]
# ## 1. When does the season open, and is it moving earlier?

# %%
fig, ax = plt.subplots(figsize=(10, 4))
bins = np.arange(0, 517 + 14, 14)
for cyc, g in opened.groupby("cycle"):
    h, _ = np.histogram(g.opened_doy, bins=bins)
    keep = bins[:-1] + 14 <= TODAY_DOY if cyc == 2027 else bins[:-1] >= 0  # 2027: only up to today
    ax.plot((bins[:-1] + 7)[keep], h[keep], color=CYCLE_COLORS[cyc], lw=2, label=f"Summer {cyc} (n={len(g)})")
ax.axvline(TODAY_DOY, color="gray", ls="--", lw=0.8)
ax.text(TODAY_DOY + 3, ax.get_ylim()[1] * 0.9, "today (2027)", fontsize=8, color="gray")
doy_axis(ax)
ax.set_ylabel("companies opening (per 2 weeks)")
ax.set_title("First SWE-intern posting per company, by date in the season")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "1-season-shape.png", dpi=110)

# Summer 2024 starts mid-season (history begins 2023-08-02), so its Jun-Jul is empty.
print(opened.assign(month=(pd.Timestamp("2026-01-01") + pd.to_timedelta(opened.opened_doy, "D")).dt.strftime("%y-%m"))
      .pivot_table(index="month", columns="cycle", values="company_key", aggfunc="count", fill_value=0))

# %% [markdown]
# ## 2. Do groups open at different times? (Summer 2025 + 2026, the two full cycles)

# %%
full = opened[opened.cycle.isin([2025, 2026])]
order = full.groupby("group").opened_doy.median().sort_values().index
fig, ax = plt.subplots(figsize=(10, 6))
ax.boxplot([full[full.group == g].opened_doy for g in order], vert=False, showfliers=False,
           tick_labels=[f"{g} ({(full.group == g).sum()})" for g in order], widths=0.6)
doy_axis(ax)
ax.invert_yaxis()
ax.set_title("Opening date by group (box = middle half, line = median), Summer 2025 + 2026")
fig.tight_layout()
fig.savefig(FIG / "2-groups.png", dpi=110)
print(full.groupby("tier").opened_doy.describe()[["count", "25%", "50%", "75%"]])

# %% [markdown]
# ## 3. How consistent is a company from one year to the next?

# %%
pairs = (o[o.status == "opened"][["company_key", "company_name", "cycle", "opened_doy", "tier", "group"]]
         .merge(o[o.status == "opened"][["company_key", "cycle", "opened_doy"]]
                .assign(cycle=lambda d: d.cycle - 1), on=["company_key", "cycle"], suffixes=("_prev", "_next")))
pairs = pairs[pairs.cycle + 1 < 2027]  # 2027 is still in progress
pairs["err"] = pairs.opened_doy_next - pairs.opened_doy_prev

fig, ax = plt.subplots(figsize=(7, 7))
for tier in ["none", "pipeline", "prestige"]:
    p = pairs[pairs.tier == tier]
    ax.scatter(p.opened_doy_prev, p.opened_doy_next, s=10 if tier == "none" else 22,
               alpha=0.35 if tier == "none" else 0.8, color=TIER_COLORS[tier], label=f"{tier} ({len(p)})")
lim = [0, 516]
ax.plot(lim, lim, color="black", lw=0.8)
ax.fill_between(lim, [l - 14 for l in lim], [l + 14 for l in lim], color="gray", alpha=0.15,
                label="within 2 weeks")
ax.set_xlim(lim), ax.set_ylim(lim)
doy_axis(ax, "x"), doy_axis(ax, "y")
ax.set_xlabel("opening last year"), ax.set_ylabel("opening this year")
ax.set_title("Same company, consecutive years (2024→25, 2025→26)")
ax.legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(FIG / "3-year-over-year.png", dpi=110)

# %% [markdown]
# ## 4. The baseline to beat in 1.7: "same date as last year"

# %%
fig, ax = plt.subplots(figsize=(8, 4))
for tier in ["prestige", "pipeline", "none"]:
    e = np.sort(pairs[pairs.tier == tier].err.abs())
    ax.plot(e, np.arange(1, len(e) + 1) / len(e), color=TIER_COLORS[tier], lw=2,
            label=f"{tier}: median {np.median(e):.0f} days off")
ax.axvline(14, color="gray", ls="--", lw=0.8)
ax.set_xlim(0, 180)
ax.set_xlabel("days between last year's opening and this year's")
ax.set_ylabel("share of companies")
ax.set_title('How far off "same date as last year" is')
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "4-baseline-error.png", dpi=110)
print(pairs.groupby(pairs.cycle + 1).agg(n=("err", "size"),
                                         median_abs=("err", lambda e: e.abs().median()),
                                         within_2w=("err", lambda e: (e.abs() <= 14).mean()),
                                         median_shift=("err", "median"),
                                         share_earlier=("err", lambda e: (e < 0).mean())))
print(pairs.groupby("group").err.agg(n="size", median_abs=lambda e: e.abs().median())
      .sort_values("median_abs"))

# %% [markdown]
# ## 5. Where is Summer 2027 compared with past years, as of today?

# %%
both = (o[(o.status == "opened") & o.cycle.isin([2025, 2026]) & (o.tier != "none")]
        .groupby("company_key").filter(lambda g: len(g) == 2).company_key.unique())
cohort = o[o.company_key.isin(both)]
fig, ax = plt.subplots(figsize=(10, 4))
grid = np.arange(0, 517)
for cyc in [2025, 2026, 2027]:
    d = cohort[(cohort.cycle == cyc) & cohort.status.isin(["opened", "opened_by"])].opened_doy
    share = [(d <= t).sum() / len(both) for t in grid]
    upto = grid <= (TODAY_DOY if cyc == 2027 else 516)
    ax.plot(grid[upto], np.array(share)[upto], color=CYCLE_COLORS[cyc], lw=2, label=f"Summer {cyc}")
ax.axvline(TODAY_DOY, color="gray", ls="--", lw=0.8)
doy_axis(ax)
ax.set_ylabel("share open")
ax.set_title(f"Prestige + pipeline companies that opened in both 2025 and 2026 ({len(both)}): "
             "share open by date")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "5-2027-progress.png", dpi=110)
for cyc in [2025, 2026, 2027]:
    d = cohort[(cohort.cycle == cyc) & cohort.status.isin(["opened", "opened_by"])].opened_doy
    print(cyc, f"{(d <= TODAY_DOY).mean() * len(d) / len(both):.0%} open by Oct 8")

# %%
if __name__ == "__main__":
    print(f"figures -> {FIG}")
