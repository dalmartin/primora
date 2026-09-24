# Internship Radar -- PRD

**Status:** final (locked 2026-09-24)
**Stakes:** launch-bound. Daniel is user #1, then other CS students.
**Source:** [[projects/internship-radar/idea-brief-internship-radar]]

## 0. One-liner
A browser extension and dashboard for CS students applying to internships in volume: it predicts when high-value roles will open, gives you a head start to prep, logs each application automatically, and tells you which applications are still alive.

## 1. Problem & why now
"At this point every public internship is a lottery ticket." A student applying in volume can't control whether a given company picks them. They can control three things:
- **How many tickets:** keeping up volume without drowning in tracking. Daniel has sent 100+ applications this cycle and quit his tracking spreadsheet because keeping it up was tedious.
- **How early:** being ready when a good role opens. Today that means setting up alerts on every company's site or checking job boards over and over.
- **Whether you win when your ticket gets pulled:** being prepped for the OA when it lands.

After applying, there's a fourth pain: silence. Most applications end in ghosting, and there's no way to tell whether to keep waiting or move on.

Existing tools cover pieces. Simplify and the GitHub lists track postings *once they're live*, and Simplify autofills forms. None of them predicts when a posting will open, and none tells you what happened to your applications.

**Why now:** the SimplifyJobs `listings.json` git history (structured since Nov 2022, about 27.5k commits) records when each company's postings opened and closed across about 4 cycles. That's enough public data to model opening windows and closures without any users. Daniel is also applying right now, so he's a live user from day one.

## 2. Who it's for
- **Daniel** -- applying in volume for high-prestige and pipeline internships this cycle. Wants to know what's coming, track what he applied to without typing it in, and know when to move on.
- **CS students applying in volume** (AI Club members first, then other students) -- the same job: more tickets, earlier, better prepped, less time wondering.
- **Not for:**
  - Recruiters, career centers, or clubs as organizations. It's an individual tool; no comparing lists between people.
  - Autofilling applications. Simplify does that; this sits next to it.
  - `[ASSUMPTION: internships only for v1, not new-grad full-time roles]`
  - `[ASSUMPTION: coverage = whatever the Simplify lists cover (mostly US tech / quant / finance internships)]`

## 3. Core user journey
1. **Set up (about 2 minutes).** Daniel installs the extension and opens the dashboard. It already shows companies tagged by tier (prestige / pipeline). He stars the ones he's targeting.
2. **Before it opens.** The dashboard shows each target's predicted opening *window* ("Google: likely Jul 10 to Aug 25, 60% by Aug 1"). When a window gets close, he gets a heads-up: "Capital One likely opens in the next 2 weeks." In v1.1 that alert also brings a prep plan (the OA platform they use, suggested LeetCode problems that cover his whole target list) and a nudge: "ask your connection there now."
3. **When it opens.** "Capital One is open, apply now." He clicks through to the posting. The extension shows context on the page: tier and how long it's been open (later: when similar postings usually close).
4. **Applying.** He submits on Greenhouse / Workday / Ashby. The extension notices the submit and logs "applied: Capital One, SWE Intern, Sep 24." No typing.
5. **After applying.** The dashboard is his pipeline: still alive vs moved on. Three weeks later the posting closes on Simplify and he hasn't heard anything, so it's marked "likely moved on." He stops wondering.
6. **Optional, v1.1: connect Gmail.** Outcome emails (OA invite, interview, rejection) update statuses automatically.

`[ASSUMPTION: alerts arrive as browser notifications from the extension, not email; Daniel said email alerts would get lost among job emails]`
`[ASSUMPTION: Chrome (Chromium) extension first]`

## 4. Features
MVP line set 2026-09-24: A, B, D, E, F, I. The ghost signal (E) was moved into the MVP because it shares the countdown's data pipeline and it's what makes journey step 5 work. F launches with Greenhouse + Ashby only.

### Data + countdown (A)
- **FR-1** [MVP] Ingest the SimplifyJobs `listings.json` git history into a postings table: company, title, category, first-seen date, closed date (`active` → false), URL. Keep it updated as new commits land.
- **FR-2** [MVP] For each company, predict the next opening *window* as a probability range (for example, "Jul 10 to Aug 25, 60% by Aug 1"), pooling across similar companies because each company only has about 4 cycles of data.
- **FR-3** [MVP] Validate by backtesting on held-out past cycles. A company's prediction is shown only if the model beats a naive baseline ("same date as last cycle"); otherwise show "not enough data." (Development check, not a user-facing page.)

### Targets + tiers (I)
- **FR-4** [MVP] Ship a hand-curated tier list (prestige / pipeline) for launch-relevant companies.
- **FR-5** [MVP] Users star target companies; the list starts pre-filled with tiered companies, and users can add any company in the Simplify data.

### Alerts (A, B)
- **FR-6** [MVP] "Coming soon" browser notification when a target's predicted window says it's likely to open within 14 days. `[ASSUMPTION: 14-day lead, based on "2 weeks to prep and get a referral"]`
- **FR-7** [MVP] "Open now" browser notification when a target company's new posting appears in the Simplify data. `[ASSUMPTION: checked at least hourly]`

### Application tracking (F)
- **FR-8** [MVP] Detect a submitted application on Greenhouse (hosted boards *and* embedded iframes on company career pages) and Ashby. Log company, role, date, and link, and match it to the Simplify listing when possible.
- **FR-9** [MVP] One-click "I applied" button on any page as a fallback, plus edit and delete for any logged application.
- **FR-10** [MVP] On a posting page, show the company's tier and how many days the posting has been open. `[Later: "postings like this usually close in N days"]`
- **FR-11** [v1.1] Workday detection.

### Pipeline dashboard + ghost signal (D, E)
- **FR-12** [MVP] Dashboard with two views: **targets** (tier, predicted window, open / not yet) and **applications** (status, date applied, days since).
- **FR-13** [MVP] Manual status updates: applied, OA, interview, rejected, offer. (Automatic updates come with G.)
- **FR-14** [MVP] Ghost signal: when a posting has closed and N days pass with no status change, mark the application "likely moved on." The user can override it. `[ASSUMPTION: N = 21 days to start; tune later]`

### Accounts
- **FR-15** [MVP] Accounts with sign-in, so the extension and dashboard share data and other students can use it. `[ASSUMPTION: Google sign-in]`

### Later
- **FR-16** [v1.1] Email outcome classifier (G): connect Gmail and auto-detect OA / interview / rejection. Small model, likely cloud-hosted, not the app's focus.
- **FR-17** [v1.1] Prep plan (C): OA platform per company plus LeetCode problems covering the whole target list, weighted toward the user's weak spots.
- **FR-18** [v1.1] Referral reminder (J) inside the "coming soon" alert.
- **FR-19** [v2] Ghost clock + wave detection (K) from opt-in, anonymous, aggregate-only outcomes.

## 5. Non-goals
- **Autofilling applications.** Simplify does it; this sits next to Simplify.
- **An LLM at the core.** The countdown and ghost signal are models Daniel builds. No LLM-generated features in v1.
- **Social or group features.** No comparing lists, leaderboards, or club dashboards. Individual use only.
- **LinkedIn integration or referral-message writing.** LinkedIn data is walled off (scraping is against its ToS), and a message writer is an LLM wrapper.
- **A public backtest / track-record page.** Backtesting is used during development only.
- **Mobile app.** It lives in the browser, where applying happens.
- **Predicting your personal odds of an offer** in v1. That needs pooled outcomes (v2 at the earliest).

## 6. Success looks like
**The model works (before launch):**
- On the held-out 2025-26 cycle, the actual opening date falls inside the predicted 80% window for at least 80% of covered companies. `[ASSUMPTION: targets to revisit after the first backtest]`
- It beats "same date as last cycle" on median error.

**Daniel uses it (this cycle):**
- He uses it through the end of his current search, and it replaces the spreadsheet he quit.
- At least 90% of his Greenhouse / Ashby applications get logged with no manual entry.

**Others use it (launch):**
- 25 students using it weekly during the next peak recruiting season (starting Summer 2027), starting with AI Club. `[ASSUMPTION: number]`
- At least one person tells Daniel an alert got them in early on a role. (The brief says trust comes from seeing it be right.)

## 7. Build notes

### Stack (locked 2026-09-24)
| Layer | Choice | Why |
|---|---|---|
| Dashboard | React + TypeScript (Vite) | Daniel's preference; shares components and types with the extension. |
| Extension | WXT (or Plasmo) + React + TypeScript, Manifest V3 | Handles extension plumbing; same React skills. |
| API | FastAPI (Python) | Same language as the model and pipeline. |
| Python hosting | **Modal**: scheduled jobs + FastAPI web endpoint | One platform, config in Python, pay per second, free monthly credits. |
| Pipeline / analytics | **DuckDB + Parquet** | Right-sized for about 27k commits; runs inside the Modal job; Parquet in a Modal Volume or object storage. MotherDuck optional later. |
| App database + auth | **Supabase** (Postgres, Auth, row-level security) | Users, targets, applications, and the predictions the app reads. |
| Model | **Simple survival model first** (lifelines / scikit-survival), then **hierarchical Bayesian** (PyMC or NumPyro) | Simple ships fast and is the baseline; Bayesian handles thin per-company data with honest ranges. Compared head to head in backtests. |
| Experiments | MLflow or Weights & Biases | Backtest results as a portfolio artifact. |
| Heavy training | Daniel's GPU cluster | For experiments, backtest sweeps, and the v1.1 email classifier. **Not** in the automated pipeline (job queue, usage rules). |

`[ASSUMPTION: dashboard hosted on Vercel or Cloudflare Pages (static React build)]`

### Architecture
```
SimplifyJobs repo ──(hourly)──> Modal: refresh_postings
                                  git history → DuckDB → Parquet (postings, opening events)
                                  new openings → Supabase `postings` + alert rows
                                         │
                                (nightly) Modal: retrain_and_predict
                                  fit model, backtest check vs baseline,
                                  write windows → Supabase `predictions`
                                         ▼
                          Supabase: Auth + Postgres (RLS)
                                         ▲
                              FastAPI on Modal (verifies Supabase JWT)
                               ▲                         ▲
                 React dashboard                 Extension (WXT)
                 targets, windows,               content scripts: Greenhouse (+ embeds), Ashby
                 applications, ghost flags       service worker: polls /alerts → browser notifications
                                                 popup: sign in, "I applied"
```
Key design choice: **predictions are computed in batch, not on request.** Opening windows only change when new data lands, so the API just reads rows.

### Data model (sketch)
- `companies` -- name, tier (prestige / pipeline / none), group (big tech / quant / bank / startup / ...), main applicant-tracking system
- `postings` -- Simplify ID, company, title, category, URL, cycle, first_seen, closed_at, active
- `openings` (derived) -- company, cycle, first opening date, or "not yet" (censored) for the current cycle
- `predictions` -- company, cycle, model version, p10 / p50 / p90 dates, probability-by-date curve (JSON), passes-baseline flag, generated_at
- `targets` -- user, company
- `applications` -- user, company, posting (nullable), role, URL, applied_at, source (greenhouse / ashby / manual), status, status_updated_at, ghost flag
- `alerts` -- user, company, type (coming_soon / open_now), created_at, delivered_at (dedupe)

### Key screens / routes
- Dashboard: sign-in, **Targets** (tier, window, status), **Applications** (pipeline + ghost flags), **Company** detail (opening-probability chart, past cycles)
- Extension: popup (sign-in, "I applied"), on-page badge on postings (tier, days open), notifications
- API: `GET /companies`, `GET /predictions`, `GET/PUT /targets`, `POST /applications`, `PATCH /applications/{id}`, `GET /alerts?since=`

### Constraints
- Solo build; Daniel is applying right now, so early personal value matters.
- Per-company data is thin (about 4 cycles since Nov 2022); pooling across companies is required.
- Launching publicly means Chrome Web Store review and a privacy policy (the extension reads pages on Greenhouse / Ashby).

## 8. Open questions & assumptions

### Assumptions (correct any in one word)
- `[ASSUMPTION: internships only for v1, not new-grad]`
- `[ASSUMPTION: coverage = whatever the Simplify lists cover]`
- `[ASSUMPTION: alerts are browser notifications, not email]`
- `[ASSUMPTION: Chrome (Chromium) first]`
- `[ASSUMPTION: "coming soon" fires 14 days ahead]`
- `[ASSUMPTION: postings checked at least hourly]`
- `[ASSUMPTION: ghost signal after 21 days of silence post-close]`
- `[ASSUMPTION: Google sign-in]`
- `[ASSUMPTION: success targets (80% window coverage, 90% auto-logging, 25 weekly users)]`
- `[ASSUMPTION: dashboard on Vercel or Cloudflare Pages]`

### Open questions
- **Data lag:** how many days after a real opening does Simplify's `date_posted` lag? Measure early; it shifts every prediction.
- **What counts as an "opening":** the first posting of any role, or the first SWE-intern posting? Per category?
- **Company groups:** who labels big tech / quant / bank / etc.? Probably hand-curated for the top companies, "other" for the rest.
- **Simplify data terms:** check the repo's license and give attribution before launch.
- **Alerts when the browser is closed:** extension polling only works while Chrome runs. Good enough for v1, or add web push / email as a backup?
- **Pre-Nov 2022 history:** worth parsing old README markdown for more cycles? Probably later, if backtests show thin data hurts.
- **Build order:** extension logging first (value for Daniel now) or data + model first (the core)? For `shipmate` to settle.
- **Name:** "Internship Radar" is a placeholder.
