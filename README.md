# Primora

A browser extension (Chrome + Firefox) that logs your internship applications when you submit them, and a dashboard that keeps the promising ones on top.

- **Scope:** [`docs/PRD.md`](docs/PRD.md) (v2, 2026-10-15)
- **Build progress:** [`docs/BUILD-TRACKER.md`](docs/BUILD-TRACKER.md)
- **Try it in your browser:** [`docs/TESTING.md`](docs/TESTING.md)

## Layout
| Folder | What | Stack |
|---|---|---|
| `extension/` | Detects submits on Greenhouse + Ashby; popup with "I applied" and quick status; full-tab dashboard (`dashboard.html`) sorted by how promising | WXT + React + TypeScript (MV3, Chrome + Firefox) |
| `shared/` | Types, statuses, priority sort, auto-ghost rule, posting keys, themes (`theme.css`, `themes/`; default in `theme.ts`) | TypeScript, CSS |
| `supabase/` | Schema (`job_applications` + row-level security) | Supabase Postgres + Auth |
| `pipeline/`, `api/`, `modal_app.py` | **Parked** (v1 prediction work). Kept for future "opens soon" reminders | Python |

No API server or website: the extension talks to Supabase directly; RLS keeps each user's rows private.

## Getting started
```bash
supabase db push                                  # apply migrations to the linked project
cp extension/.env.example extension/.env.local    # fill in URL + anon key

cd extension && npm install && npm run build      # then load extension/.output/chrome-mv3 unpacked
cd extension && npm run build:firefox             # Firefox: about:debugging → Load Temporary Add-on → .output/firefox-mv3
node --test shared/*.test.ts                      # shared logic tests
```

## Data
The parked pipeline uses posting history from [SimplifyJobs](https://github.com/SimplifyJobs/Summer2027-Internships) and [speedyapply](https://github.com/speedyapply/2027-SWE-College-Jobs).
