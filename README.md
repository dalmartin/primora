# Primora

Know when internships open, log every application automatically, and see which ones are still alive.

- **Scope:** [`docs/PRD.md`](docs/PRD.md)
- **Build progress:** [`docs/BUILD-TRACKER.md`](docs/BUILD-TRACKER.md)

## Layout
| Folder | What | Stack |
|---|---|---|
| `pipeline/` | SimplifyJobs history → DuckDB/Parquet → opening predictions | Python, DuckDB, lifelines / scikit-survival (later PyMC) |
| `api/` | Backend for the dashboard + extension | FastAPI |
| `modal_app.py` | Scheduled jobs (hourly refresh, nightly retrain) + hosts the API | Modal |
| `supabase/` | Database schema (migrations), auth | Supabase Postgres |
| `web/` | Dashboard | React + Vite + TypeScript |
| `extension/` | Chrome extension | WXT + React + TypeScript |

## Getting started
```bash
uv sync                              # Python env (pipeline + api)
uv run jupyter lab pipeline/notebooks
uv run fastapi dev api/src/primora_api/main.py   # API at localhost:8000/health

cd web && npm install && npm run dev             # dashboard
cd extension && npm install && npm run dev       # extension (opens Chrome with it loaded)

uv run modal deploy modal_app.py     # deploy jobs + API to Modal
supabase db push                     # apply migrations to the linked Supabase project
```

## Data
Posting history comes from [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships). Check the license and credit it before launch (tracker 5.1).
