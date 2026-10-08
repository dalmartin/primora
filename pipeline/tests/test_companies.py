import pyarrow as pa
import pyarrow.parquet as pq

from primora_pipeline.companies import build


def test_companies(tmp_path):
    rows = [  # one openings row per company is enough
        {"company_key": "jpmorgan chase", "company_name": "JPMorgan Chase"},
        {"company_key": "acme bank", "company_name": "Acme Bank"},
        {"company_key": "axcelis technologies", "company_name": "Axcelis"},   # label by display name
        {"company_key": "zyx", "company_name": "Zyx"},
    ]
    pq.write_table(pa.Table.from_pylist([
        {**r, "cycle": 2026, "status": "opened", "opened_doy": 230, "cycles_open": 1,
         "n_swe_postings": 1, "n_speedyapply_postings": 0} for r in rows]), tmp_path / "o.parquet")
    (tmp_path / "labels.csv").write_text(
        "company_name,tier,group\nJP Morgan Chase,pipeline,finance\nAxcelis,none,hardware_semis\n")
    (tmp_path / "aliases.csv").write_text("alias,canonical\nJP Morgan Chase,JPMorgan Chase\n")
    c = {r["company_name"]: r for r in build(tmp_path / "o.parquet", tmp_path / "labels.csv",
                                              tmp_path / "aliases.csv", tmp_path / "c.parquet")
         .execute("select * from companies").to_arrow_table().to_pylist()}
    assert (c["JPMorgan Chase"]["tier"], c["JPMorgan Chase"]["label_source"]) == ("pipeline", "hand")
    assert c["Axcelis"]["group"] == "hardware_semis"
    assert (c["Acme Bank"]["group"], c["Acme Bank"]["label_source"]) == ("finance", "rule")
    assert (c["Zyx"]["group"], c["Zyx"]["tier"], c["Zyx"]["label_source"]) == ("other", "none", "default")
