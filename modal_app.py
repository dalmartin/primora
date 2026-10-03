"""Primora on Modal: scheduled pipeline jobs + the FastAPI app.

Deploy:  modal deploy modal_app.py
Run once: modal run modal_app.py::refresh_postings
"""
import modal

app = modal.App("primora")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install("duckdb", "polars", "pyarrow", "pandas", "lifelines", "fastapi[standard]", "supabase", "pyjwt")
    .add_local_python_source("primora_pipeline", "primora_api")
)

data_volume = modal.Volume.from_name("primora-data", create_if_missing=True)
DATA_DIR = "/data"


@app.function(image=image, volumes={DATA_DIR: data_volume}, schedule=modal.Cron("0 * * * *"), timeout=1800)
def refresh_postings():
    """Hourly: pull SimplifyJobs history, update postings, emit open-now alerts. (Tracker 1.1, 1.10)"""
    print("refresh_postings: hello from Primora (pipeline not built yet)")


@app.function(image=image, volumes={DATA_DIR: data_volume}, schedule=modal.Cron("0 6 * * *"), timeout=3600)
def retrain_and_predict():
    """Nightly: fit model, check vs baseline, write predictions. (Tracker 1.8, 1.10)"""
    print("retrain_and_predict: hello from Primora (model not built yet)")


@app.function(image=image)
@modal.asgi_app()
def api():
    from primora_api.main import app as fastapi_app

    return fastapi_app
