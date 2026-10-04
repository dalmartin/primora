from datetime import datetime, timedelta, timezone

import pyarrow as pa
import pyarrow.parquet as pq

from primora_pipeline import lag
from primora_pipeline.lag import _board_candidates, board_jobs

T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def posting(listing_id, url, company="Acme", title="Software Engineer Intern", hours=5):
    return {"listing_id": listing_id, "company_name": company, "title": title, "url": url,
            "is_swe": True, "cycle": 2027, "first_seen": T0 + timedelta(hours=hours),
            "date_posted": T0 + timedelta(hours=hours)}


def test_board_candidates():
    assert _board_candidates("Waymo", "careers.withwaymo.com") == ["waymo", "withwaymo"]
    assert "epicgames" in _board_candidates("Epic Games", "epicgames.com")


def test_lever_created_at_is_ms():
    jobs = board_jobs("lever", [{"id": "x", "text": "SWE Intern", "createdAt": 1_780_000_000_000}])
    assert jobs[0]["company_date"].startswith("2026-05-28")


def test_build(tmp_path, monkeypatch):
    boards = {
        ("greenhouse", "acme"): [
            {"job_id": "1", "title": "Software Engineer Intern", "company_date": T0.isoformat()},
            {"job_id": "9", "title": "Software Engineer Intern (Summer 2027)", "company_date": T0.isoformat()},
        ],
        ("ashby", "beta"): [  # republished after Simplify saw it
            {"job_id": "0" * 36, "title": "SWE Intern", "company_date": (T0 + timedelta(days=30)).isoformat()},
        ],
        ("greenhouse", "waymo"): [
            {"job_id": "77", "title": "Software Engineering Intern", "company_date": (T0 - timedelta(days=2)).isoformat()},
        ],
    }
    monkeypatch.setattr(lag, "fetch_board", lambda ats, board, refetch=False: boards.get((ats, board)))
    rows = [
        posting("gh", "https://job-boards.greenhouse.io/acme/jobs/1"),
        posting("ab", f"https://jobs.ashbyhq.com/beta/{'0' * 36}/application"),
        posting("own", "https://careers.withwaymo.com/jobs?gh_jid=77", company="Waymo"),
        posting("eu", "https://job-boards.eu.greenhouse.io/acme/jobs/1"),   # EU: skipped
    ]
    src = tmp_path / "postings.parquet"
    pq.write_table(pa.Table.from_pylist(rows), src)
    con = lag.build(src, lag_out=tmp_path / "lag.parquet", coverage_out=tmp_path / "cov.parquet")

    got = dict(con.execute("select listing_id, lag_days from simplify_lag").fetchall())
    assert got == {"gh": round(5 / 24, 2), "ab": round(-30 + 5 / 24, 2), "own": round(2 + 5 / 24, 2)}
    cov = dict(con.execute("select job_id, in_simplify from board_coverage where board = 'acme'").fetchall())
    assert cov == {"1": True, "9": False}
