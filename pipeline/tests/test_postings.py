from datetime import datetime, timedelta, timezone

import pyarrow as pa
import pyarrow.parquet as pq

from primora_pipeline.extract_history import SCHEMA
from primora_pipeline.postings import build

T0 = datetime(2025, 8, 1, tzinfo=timezone.utc)


def row(listing_id, event, day, *, active=True, title="Software Engineer Intern", terms=("Summer 2026",)):
    t = T0 + timedelta(days=day)
    return {"listing_id": listing_id, "event": event, "commit_sha": f"c{day}", "commit_time": t,
            "company_name": "Acme", "title": title, "category": None, "active": active, "is_visible": True,
            "terms": list(terms), "date_posted": t, "date_updated": t, "url": None, "locations": None,
            "source": "Simplify", "sponsorship": None, "company_url": None}


def test_postings(tmp_path):
    rows = [
        row("seed", "added", 0),                                   # in the first commit -> censored
        # flaps closed and reopens twice, then closes for good on day 30
        row("flap", "added", 1), row("flap", "changed", 2, active=False), row("flap", "changed", 3),
        row("flap", "changed", 10, active=False), row("flap", "changed", 11),
        row("flap", "changed", 30, active=False),
        row("late", "added", 5, active=False, title="Mechanical Engineering Intern", terms=("Fall 2025",)),
        row("roll", "added", 6, terms=("Fall 2025", "Summer 2026", "Summer 2027")),
        row("gone", "added", 7), row("gone", "removed", 40),
    ]
    obs = tmp_path / "obs.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), obs)
    p = {r["listing_id"]: r for r in build(obs, tmp_path / "postings.parquet")
         .execute("select * from postings").to_arrow_table().to_pylist()}

    assert p["seed"]["first_seen_censored"] and not p["flap"]["first_seen_censored"]
    assert p["flap"]["closed_at"] == T0 + timedelta(days=30)        # final close, not the first
    assert p["flap"]["first_closed_at"] == T0 + timedelta(days=2)
    assert p["flap"]["n_reopens"] == 2
    assert p["flap"]["is_swe"] and p["flap"]["cycle"] == 2026 and p["flap"]["season"] == "summer"
    assert p["late"]["added_closed"] and p["late"]["closed_at"] == T0 + timedelta(days=5)
    assert not p["late"]["is_swe"] and p["late"]["season"] == "off_season" and p["late"]["cycle"] is None
    assert p["roll"]["multi_cycle"] and p["roll"]["cycle"] == 2026 and p["roll"]["closed_at"] is None
    assert p["gone"]["removed_at"] == T0 + timedelta(days=40) and p["gone"]["closed_at"] is None
