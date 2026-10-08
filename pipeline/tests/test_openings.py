from datetime import timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from primora_pipeline import openings, postings
from primora_pipeline.extract_history import SCHEMA

from test_postings import T0, row


def co(r, company):
    return {**r, "company_name": company}


def test_openings(tmp_path, monkeypatch):
    monkeypatch.setattr(openings, "CYCLES", (2026, 2027))
    rows = [
        co(row("seed", "added", 0), "Early"),                       # first commit -> opened_by
        co(row("a26", "added", 3), "Acme"),
        co(row("a27", "added", 160, terms=("Summer 2027",)), "Acme"),     # 2026-01-08
        # reused 2026 posting relabeled to 2027 on day 170: counts for 2027 from then, not day 2
        co(row("relab", "added", 2), "Relab"),
        co(row("relab", "changed", 170, terms=("Summer 2027",)), "Relab"),
        # rolling posts tagged 2026 + 2027: day 4 is before the 2027 window (Jan 1 2026), day 158 is in it
        co(row("roll", "added", 4, terms=("Summer 2026", "Summer 2027")), "Roll"),
        co(row("roll2", "added", 158, terms=("Summer 2026", "Summer 2027")), "Roll"),
        co(row("plain", "added", 165, terms=("Summer 2027",)), "Roll"),
        co(row("back", "added", 6, active=False), "Back"),          # backfilled closed only
        co(row("na", "added", 8, title="Software Engineer Intern", terms=("N/A",)), "Early"),
        co(row("na2", "added", 8, title="Software Engineer Intern", terms=("N/A",)), "NA"),
    ]
    obs = tmp_path / "obs.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), obs)
    postings.build(obs, tmp_path / "postings.parquet")
    con = openings.build(obs, tmp_path / "postings.parquet", tmp_path / "openings.parquet",
                         lag=tmp_path / "none", coverage=tmp_path / "none")
    o = {(r["company_name"], r["cycle"]): r
         for r in con.execute("select * from openings").to_arrow_table().to_pylist()}

    assert o["Early", 2026]["status"] == "opened_by"
    assert o["Early", 2027]["status"] == "not_yet"
    assert o["Early", 2026]["opened_at"] == T0 and not o["Early", 2026]["via_unlabeled"]
    # no-season intern post on day 8 (Aug 2025) -> Summer 2026; sets the opening when it's first
    assert o["NA", 2026]["opened_at"] == T0 + timedelta(days=8) and o["NA", 2026]["via_unlabeled"]
    assert o["Acme", 2026]["opened_at"] == T0 + timedelta(days=3)
    assert o["Acme", 2027]["opened_at"] == T0 + timedelta(days=160)
    assert o["Relab", 2026]["status"] == "none"                     # latest terms only
    assert o["Relab", 2027]["opened_at"] == T0 + timedelta(days=170) and o["Relab", 2027]["via_relabel"]
    assert o["Roll", 2026]["opened_at"] == T0 + timedelta(days=4)
    assert o["Roll", 2027]["opened_at"] == T0 + timedelta(days=158) and o["Roll", 2027]["via_multi_cycle"]
    assert o["Roll", 2027]["opened_at_excl_multi"] == T0 + timedelta(days=165)
    assert o["Roll", 2027]["n_out_of_window"] == 1
    assert o["Back", 2026]["status"] == "backfilled" and o["Back", 2026]["opened_at"] is None
    assert o["Acme", 2026]["cycles_open"] == 2
