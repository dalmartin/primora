# Primora -- PRD (v2, rescoped)

**Status:** final (rescoped and locked 2026-10-15)
**Stakes:** launch-bound. Daniel is user #1, then other CS students.
**Previous version:** `docs/archive/PRD-v1-2026-09-24.md` (prediction + alerts + tracking). Vault copy of this file: `Tauros/projects/primora/PRD.md`.

## Why v2
v1 put a survival model at the center: predict when each company's internship posting opens. The Phase 1 data work (openings table from SimplifyJobs + speedyapply, tiers, backtests) showed the prediction isn't worth the cost yet. Each company has only 2-4 past cycles, and "about when it opened last year" (about 26 days off for tiered companies) is a good enough estimate with no model. The part of v1 that solves Daniel's real, current pain is application tracking: he quit his spreadsheet halfway through 100+ applications because keeping it up was tedious. v2 ships that part alone. Predictions and reminders come back as later updates (section 4, Later).

## 0. One-liner
A Chrome extension that logs your internship applications automatically when you submit them, and a dashboard that keeps the promising ones on top.

## 1. Problem
A student applying in volume sends dozens to hundreds of applications. Tracking them by hand (spreadsheet, notes) is tedious enough that people stop, and then they lose track of what they applied to, where they're still alive, and which interviews or OAs need attention. The few applications that matter (an interview, an OA) get buried under the many that went silent.

Existing tools: Simplify autofills and has a tracker, but logging is tied to its own flow. Spreadsheets need typing. Nothing just notices the submit and keeps a clean, prioritized list.

## 2. Who it's for
- **Daniel**, applying in volume right now.
- **CS students applying in volume** (AI Club members first).
- **Not for:** recruiters or career centers; autofilling applications (Simplify does that); comparing lists between people.

## 3. Core user journey
1. **Set up (about 1 minute).** Install the extension, sign in.
2. **Apply.** Submit on a Greenhouse or Ashby page. The extension notices and logs "Capital One, SWE Intern, Oct 15." No typing. On any other site, one click on "I applied" in the popup logs it (company, role, and link prefilled from the page where possible).
3. **Update.** An OA invite arrives: open the dashboard (or the popup), set the status to OA.
4. **Glance.** The dashboard opens with what matters on top: offers, then interviews, then OAs, then everything still pending. Applications with no update in 30 days drop to "likely ghosted" on their own. Rejections sit at the bottom.

## 4. Features

### MVP
- **FR-1 Auto-log on submit.** Detect a submitted application on Greenhouse (hosted boards and embedded iframes on company career pages) and Ashby. Log company, role, URL, date applied, source.
- **FR-2 Manual log.** "I applied" button in the popup on any page, prefilled from the page title/URL where possible. Edit and delete any application.
- **FR-3 Statuses.** applied, OA, interview, offer, rejected, likely ghosted. Set from the dashboard or the popup.
- **FR-4 Auto-ghost.** An application still at "applied" with no status change for N days shows as "likely ghosted." Computed when the list loads; no background job. The user can mark it "still alive" (resets the clock) or confirm it. `[ASSUMPTION: N = 30 days]`
- **FR-5 Priority sort.** One list ordered offer → interview → OA → applied → likely ghosted → rejected; newest first within each group. Search/filter by company.
- **FR-6 Accounts.** Sign in so the extension and dashboard share data and other students can use it. `[ASSUMPTION: Google sign-in via chrome.identity.launchWebAuthFlow + Supabase OAuth; email + password as the fallback if that fights back]`
- **FR-7 Duplicate guard.** Submitting twice on the same posting URL doesn't create two rows.

### Later
- Reminders / "opens soon" based on last year's opening dates (the parked Phase 1 data).
- On-page context on postings (tier, days open).
- Workday detection.
- Gmail outcome detection (auto OA / interview / rejection). Cut from scope 2026-10-15.
- Export to CSV.

## 5. Non-goals
- **Prediction models or scheduled jobs in the MVP.** It's a CRUD app.
- **Email integration** (for now).
- **Autofill.** Simplify does it.
- **Social features, LLM features, mobile app.**

## 6. Success looks like
- Daniel uses it through the end of his current search, and it replaces the spreadsheet he quit.
- At least 90% of his Greenhouse / Ashby applications get logged with no manual entry.
- `[ASSUMPTION]` 10 AI Club members using it weekly during the next peak recruiting season.

## 7. Build notes

### Stack
| Layer | Choice | Why |
|---|---|---|
| Extension | WXT + React + TypeScript, Manifest V3 | Already scaffolded. |
| Dashboard | React + TypeScript (Vite) | Already scaffolded; shares types with the extension. |
| Database + auth | **Supabase** (Postgres, Auth, row-level security), called directly from both clients | CRUD only, so no separate API. RLS (`user_id = auth.uid()`) keeps each user's rows private. The anon key is public by design. |
| Hosting | Vercel or Cloudflare Pages (static dashboard) | `[ASSUMPTION]` |

**Dropped from v1:** FastAPI, Modal, the scheduled pipeline, the model. Phase 1 code (`pipeline/`) stays in the repo, parked.

### Architecture
```
Extension (WXT)                          Dashboard (React)
  content scripts: Greenhouse (+ iframes), Ashby   list, sort, status edits
  popup: sign in, "I applied", quick status        search, edit, delete
        │                                              │
        └──────────── supabase-js ─────────────────────┘
                              ▼
                 Supabase: Auth + Postgres (RLS)
                 table: job_applications
```

### Data model
- `job_applications` -- id, user_id, company, role, url, applied_at, source (greenhouse / ashby / manual), status (applied / oa / interview / offer / rejected / ghosted), status_updated_at, posting_key, notes (optional). Unique on (user_id, posting_key) for the duplicate guard.
- "Likely ghosted" display = status is `ghosted`, OR status is `applied` and `status_updated_at` is older than N days. "Still alive" just bumps `status_updated_at`.

The v1 migration (`supabase/migrations/20260924000000_initial_schema.sql`) has 7 tables; v2 needs only one table; `supabase/migrations/20261015000000_v2_job_applications.sql` adds `job_applications` and leaves the v1 tables unused.

### Constraints
- Solo build; Daniel is applying now, so the Greenhouse/Ashby logger is the first thing to make real.
- Submit detection is per-site and fragile. Check real pages before writing detectors; keep the manual button as the safety net.
- Chrome Web Store review + a privacy policy before public launch (the extension reads application pages).

## 8. Open questions
- How to detect "submitted" reliably on each site: the confirmation page/URL, the submit network request, or the form submit event? Decide per site from real pages.
- Google sign-in inside the extension: test early; fall back to email + password if it stalls.
- N for auto-ghost: 30 days to start; tune from Daniel's real data.
