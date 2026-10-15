# Primora

A Chrome extension that logs your internship applications when you submit them, and a dashboard that keeps the promising ones on top.

- **Scope:** [`docs/PRD.md`](docs/PRD.md) (v2, 2026-10-15)
- **Build progress:** [`docs/BUILD-TRACKER.md`](docs/BUILD-TRACKER.md)
- **Try it in your browser:** [`docs/TESTING.md`](docs/TESTING.md)

## Layout
| Folder | What | Stack |
|---|---|---|
| `extension/` | Detects submits on Greenhouse + Ashby; popup with "I applied" and quick status | WXT + React + TypeScript (MV3) |
| `web/` | Dashboard: applications sorted by how promising, status edits | React + Vite + TypeScript |
| `shared/` | Types, statuses, priority sort, auto-ghost rule, posting keys, theme tokens (`theme.css`) | TypeScript, CSS |
| `supabase/` | Schema (`job_applications` + row-level security) | Supabase Postgres + Auth |
| `pipeline/`, `api/`, `modal_app.py` | **Parked** (v1 prediction work). Kept for future "opens soon" reminders | Python |

No API server: both clients talk to Supabase directly; RLS keeps each user's rows private.

## Getting started
```bash
supabase db push                                  # apply migrations to the linked project
cp web/.env.example web/.env.local                # fill in URL + anon key
cp extension/.env.example extension/.env.local    # same values

cd web && npm install && npm run dev              # dashboard at localhost:5173
cd extension && npm install && npm run build      # then load extension/.output/chrome-mv3 unpacked
node --test shared/*.test.ts                      # shared logic tests
```

## Data
The parked pipeline uses posting history from [SimplifyJobs](https://github.com/SimplifyJobs/Summer2027-Internships) and [speedyapply](https://github.com/speedyapply/2027-SWE-College-Jobs).
