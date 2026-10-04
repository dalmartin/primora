"""Primora on Modal: scheduled pipeline jobs + the FastAPI app.

Deploy:  modal deploy modal_app.py
Run once: modal run modal_app.py::refresh_postings
History:  modal run modal_app.py::extract_history, then
          modal volume get primora-data history data/
"""
import modal

app = modal.App("primora")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .env({"PRIMORA_DATA_DIR": "/data"})
    .pip_install("duckdb", "polars", "pyarrow", "orjson", "pandas", "lifelines", "fastapi[standard]", "supabase", "pyjwt")
    .add_local_python_source("primora_pipeline", "primora_api")
)

data_volume = modal.Volume.from_name("primora-data", create_if_missing=True)
DATA_DIR = "/data"
supabase_secret = modal.Secret.from_name("primora-supabase")


@app.function(image=image, volumes={DATA_DIR: data_volume}, secrets=[supabase_secret], schedule=modal.Cron("0 * * * *"), timeout=1800)
def refresh_postings():
    """Hourly: pull SimplifyJobs history, update postings, emit open-now alerts. (Tracker 1.1, 1.10)"""
    print("refresh_postings: hello from Primora (pipeline not built yet)")


@app.function(image=image, volumes={DATA_DIR: data_volume}, secrets=[supabase_secret], schedule=modal.Cron("0 6 * * *"), timeout=3600)
def retrain_and_predict():
    """Nightly: fit model, check vs baseline, write predictions. (Tracker 1.8, 1.10)"""
    print("retrain_and_predict: hello from Primora (model not built yet)")


@app.function(image=image, volumes={DATA_DIR: data_volume}, timeout=6 * 3600, cpu=4, memory=8192)
def extract_history(refresh: bool = True):
    """One-off / on demand: SimplifyJobs git history -> history/*.parquet on the volume. (Tracker 1.1)"""
    from primora_pipeline.extract_history import extract

    try:
        extract(refresh=refresh)
    finally:
        data_volume.commit()


@app.function(image=image, secrets=[supabase_secret])
@modal.asgi_app()
def api():
    from primora_api.main import app as fastapi_app

    return fastapi_app
