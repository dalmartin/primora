import pandas as pd

from primora_pipeline.backtest import last_year, run


def frame():
    rows = []
    for key, group, doys in [("a", "quant", (200, 210, 220)), ("b", "quant", (205, 215, 225)),
                             ("c", "health", (300, 350, None))]:
        for cyc, d in zip((2024, 2025, 2026), doys):
            rows.append({"company_key": key, "cycle": cyc, "status": "opened" if d else "none",
                         "opened_doy": d, "tier": "none", "group": group})
    return pd.DataFrame(rows)


def test_perfect_model_scores_perfectly():
    o = frame()
    truth = lambda train, targets, k: (o[(o.cycle == k) & (o.status == "opened")]
                                       [["company_key", "opened_doy"]].rename(columns={"opened_doy": "p50"})
                                       .assign(p10=lambda d: d.p50 - 5, p90=lambda d: d.p50 + 5))
    r = run({"truth": truth}, o=o).set_index(["test_cycle", "subset"])
    assert r.loc[(2026, "all"), "n"] == 2 and r.loc[(2026, "all"), "mae_days"] == 0
    assert r.loc[(2026, "all"), "coverage_80"] == 1 and r.loc[(2026, "all"), "width_80"] == 10


def test_last_year():
    o = frame()
    p = last_year(o[o.cycle < 2026], o.drop_duplicates("company_key"), 2026).set_index("company_key")
    assert p.loc["a", "p50"] == 210 and p.loc["c", "p50"] == 350
    # pooled |error| 80th percentile from pairs 2024->25: errors 10, 10, 50
    assert p.loc["a", "p90"] - p.loc["a", "p50"] == p.loc["c", "p90"] - p.loc["c", "p50"]
