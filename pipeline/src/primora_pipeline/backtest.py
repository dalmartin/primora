"""Tracker 1.7: backtest harness + baselines.

For each test cycle k: a model sees only cycles before k (`train`) and predicts, for every
company, an opening window for cycle k as day-of-season quantiles p10 / p50 / p90 (doy = days from
Jan 1 of the year before the Summer; the window is 0..516). Scored on companies that actually
opened in cycle k (status "opened"; left-censored "opened_by" and "none" aren't scored).

Metrics, per model x test cycle x subset (all / tiered = prestige + pipeline / has_history):
  n            companies scored (that opened in k and the model gave a prediction for)
  mae_days     median |p50 - actual|, days
  within_14    share with |p50 - actual| <= 14 days
  coverage_80  share with p10 <= actual <= p90 (target: 0.80)
  width_80     median p90 - p10, days (narrower is better, at the same coverage)
  missing      companies that opened in k with no prediction from the model

Test cycles: 2025 (train 2024) and 2026 (train 2024-2025). 2027 is still open: not scored yet.
Summer 2024 is half-observed (history starts 2023-08-02), so its openings skew late; models
should treat it with care.

A model is a function (train, targets, k) -> DataFrame[company_key, p10, p50, p90]:
  train    openings rows with cycle < k, plus company tier and group
  targets  one row per company to predict (company_key, tier, group)
Register it in MODELS.

Run:  uv run python -m primora_pipeline.backtest      (writes docs/backtests/results.csv)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from primora_pipeline.paths import DATA_DIR

TEST_CYCLES = (2025, 2026)
RESULTS = Path(__file__).resolve().parents[3] / "docs" / "backtests" / "results.csv"
Model = Callable[[pd.DataFrame, pd.DataFrame, int], pd.DataFrame]


def load() -> pd.DataFrame:
    o = pd.read_parquet(DATA_DIR / "openings.parquet")
    co = pd.read_parquet(DATA_DIR / "companies.parquet")[["company_key", "tier", "group"]]
    return o.merge(co, on="company_key")


# --- baselines ---------------------------------------------------------------------------------

def _last_opening(train: pd.DataFrame) -> pd.Series:
    """Each company's most recent observed opening doy (status opened)."""
    t = train[train.status == "opened"].sort_values("cycle")
    return t.groupby("company_key").opened_doy.last()


def _pair_errors(train: pd.DataFrame) -> pd.DataFrame:
    """this year - last year (`err`), with group, for consecutive cycles inside train."""
    t = train[train.status == "opened"][["company_key", "cycle", "opened_doy", "group"]]
    p = t.merge(t.drop(columns="group").assign(cycle=t.cycle + 1), on=["company_key", "cycle"],
                suffixes=("", "_prev"))
    return p.assign(err=p.opened_doy - p.opened_doy_prev)


def last_year(train, targets, k):
    """p50 = the company's last opening date. Window = p50 +/- the 80th percentile of |year-over-year
    error| in train for the company's group (all groups pooled if the group has < 10 pairs).
    Needs 2 train cycles, so there's no window for k=2025."""
    last = _last_opening(train)
    pairs = _pair_errors(train)
    pooled = np.quantile(pairs.err.abs(), 0.8) if len(pairs) else np.nan
    by_group = pairs.groupby("group").err.agg(
        lambda e: np.quantile(e.abs(), 0.8) if len(e) >= 10 else np.nan)
    p = targets[["company_key", "group"]].assign(p50=lambda d: d.company_key.map(last)).dropna(subset=["p50"])
    h = p.group.map(by_group).fillna(pooled)
    return p.drop(columns="group").assign(p10=(p.p50 - h).clip(0, 516), p90=(p.p50 + h).clip(0, 516))


def group_season(train, targets, k):
    """Ignore the company; predict its group's opening-date spread in train (p10 / p50 / p90)."""
    t = train[train.status == "opened"]
    q = t.groupby("group").opened_doy.quantile([0.1, 0.5, 0.9]).unstack()
    q.columns = ["p10", "p50", "p90"]
    allq = t.opened_doy.quantile([0.1, 0.5, 0.9]).to_numpy()
    p = targets[["company_key", "group"]].join(q, on="group")
    p[["p10", "p50", "p90"]] = p[["p10", "p50", "p90"]].fillna(pd.Series(allq, index=["p10", "p50", "p90"]))
    return p.drop(columns="group")


def last_year_or_group(train, targets, k):
    """last_year where the company has history and a window exists, else group_season."""
    g = group_season(train, targets, k).set_index("company_key")
    ly = last_year(train, targets, k).set_index("company_key")
    ly = ly[ly.p10.notna()] if len(ly) else ly
    return g.drop(index=ly.index, errors="ignore").pipe(lambda d: pd.concat([d, ly])).reset_index()


MODELS: dict[str, Model] = {
    "last_year": last_year,
    "group_season": group_season,
    "last_year_or_group": last_year_or_group,
}


# --- harness -----------------------------------------------------------------------------------

def score(pred: pd.DataFrame, actual: pd.DataFrame) -> dict:
    s = actual.merge(pred, on="company_key", how="left")
    have = s.dropna(subset=["p50"])
    err = (have.p50 - have.opened_doy).abs()
    windowed = have.dropna(subset=["p10", "p90"])
    return {
        "n": len(have),
        "mae_days": float(err.median()) if len(have) else np.nan,
        "within_14": float((err <= 14).mean()) if len(have) else np.nan,
        "coverage_80": float(windowed.opened_doy.between(windowed.p10, windowed.p90).mean())
                       if len(windowed) else np.nan,
        "width_80": float((windowed.p90 - windowed.p10).median()) if len(windowed) else np.nan,
        "missing": int(s.p50.isna().sum()),
    }


def run(models: dict[str, Model] = MODELS, test_cycles=TEST_CYCLES,
        o: pd.DataFrame | None = None) -> pd.DataFrame:
    o = load() if o is None else o
    targets = o.drop_duplicates("company_key")[["company_key", "tier", "group"]]
    rows = []
    for k in test_cycles:
        train = o[o.cycle < k]
        actual = o[(o.cycle == k) & (o.status == "opened")]
        history = set(train[train.status == "opened"].company_key)
        subsets = {
            "all": actual,
            "tiered": actual[actual.tier != "none"],
            "has_history": actual[actual.company_key.isin(history)],
        }
        for name, model in models.items():
            pred = model(train, targets, k)
            for subset, a in subsets.items():
                rows.append({"model": name, "test_cycle": k, "subset": subset, **score(pred, a)})
    return pd.DataFrame(rows)


def main() -> None:
    r = run()
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    r.to_csv(RESULTS, index=False, float_format="%.3f")
    with pd.option_context("display.width", 160, "display.max_rows", None):
        print(r.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print(f"-> {RESULTS}")


if __name__ == "__main__":
    main()
