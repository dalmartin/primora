# Internship Radar -- Build Tracker

**PRD:** `docs/PRD.md` (source of truth for scope; this file tracks *doing* it, not *what* it is). Vault copy: `Tauros/projects/internship-radar/PRD.md`.
**Status:** in progress

Takes Internship Radar from an empty repo to a launched Chrome extension + dashboard. Order: a quick scaffolding pass, then **the data and the simple model first** (Daniel's call, 2026-09-24), then the extension and dashboard, then alerts, then the Bayesian model, then launch.

**Hard rules**
- No LLM at the core. The countdown and ghost signal are models built here.
- Never commit secrets (Supabase keys, Modal tokens). Use `.env` locally and Modal Secrets in the cloud.
- Be polite to outside services: no scraping LinkedIn; cache Greenhouse / Ashby job-board API responses; don't poll faster than hourly.
- The backtest decides. A model version ships only if it beats the baseline on held-out cycles.

**Working mode**
- **Scaffolding (Phase 0, most of Phase 2):** Claude Code does it in one pass; Daniel reviews.
- **Model work (Phases 1 and 4):** Daniel drives. Tauros explains, pairs, and reviews rather than writing it all. `[ASSUMPTION: confirm with Daniel]`

---

## Phase 0 -- Foundation (one pass)
- [ ] **0.1 Repo layout.** Monorepo: `pipeline/` (Python, uv), `api/` (FastAPI), `web/` (React + Vite + TS), `extension/` (WXT + React + TS), `docs/`. README, `.gitignore`, `.env.example`. Done: repo structure committed; `pipeline` env installs.
- [ ] **0.2 Python env.** uv project with duckdb, polars (or pandas), lifelines, scikit-survival, matplotlib, jupyter, and MLflow or W&B. Done: a notebook imports everything.
- [ ] **0.3 Supabase.** New project; migration for the 7 tables (companies, postings, openings, predictions, targets, applications, alerts); row-level security on user tables; Google sign-in enabled. Done: tables visible in Supabase; a test sign-in works.
- [ ] **0.4 Modal.** Account + CLI auth; hello-world scheduled function; FastAPI `/health` web endpoint; Supabase keys in Modal Secrets. Done: `modal deploy` gives a URL that returns ok, and the scheduled function shows runs in the dashboard.

## Phase 1 -- Data + simple model (Daniel drives)
- [ ] **1.1 Extract history.** Clone SimplifyJobs; walk every commit touching `.github/scripts/listings.json`; write per-listing observations (listing ID, commit time, active, fields) to Parquet. Done: Parquet exists; listing counts sanity-checked against the current file (about 17k).
- [ ] **1.2 Postings table.** Per listing: company, title, category, first_seen, closed_at, cycle. Compare `date_posted` vs first commit time. Done: DuckDB query returns sensible rows for 5 known companies.
- [ ] **1.3 Measure the Simplify lag.** Sample 20-30 postings; compare Simplify's date to the real posting date (Greenhouse / Ashby job-board APIs where available). Done: median and spread written to `docs/data-notes.md`.
- [ ] **1.4 Define "opening" + openings table.** Decide: first posting of any role vs first SWE-intern posting, per cycle. Build `openings`, with the current cycle's not-yet-opened companies marked censored. Done: decision in `docs/data-notes.md`; table built.
- [ ] **1.5 Company metadata.** Hand-curate `companies.csv` for the top ~100 companies: tier (prestige / pipeline / none) and group (big tech / quant / bank / startup / other). Done: file committed, joined into DuckDB.
- [ ] **1.6 Exploratory analysis.** Notebook: opening dates by group and by cycle; how consistent each company is. Done: plots + 5 written takeaways in `docs/data-notes.md`.
- [ ] **1.7 Baseline + backtest harness.** Baseline = "same date as last cycle." Harness: train on cycles up to k, predict k+1. Metrics: median absolute error (days), 80%-window coverage, window width. Done: harness runs; baseline numbers logged.
- [ ] **1.8 Simple survival model.** lifelines / scikit-survival (for example a Weibull AFT with group, tier, last-cycle date, posting count as features) that handles censoring. Output per company: p10 / p50 / p90 dates + probability-by-date curve. Done: backtested against the baseline; results tracked.
- [ ] **1.9 "Not yet" updating.** Predictions condition on "hasn't opened as of today," so windows move later and narrow. Done: a test case shows the shift.
- [ ] **1.10 Productionize on Modal.** Hourly `refresh_postings` updates postings in Supabase; nightly `retrain_and_predict` writes predictions with a passes-baseline flag. Done: rows update on schedule for 2 days straight.

## Phase 2 -- Extension logging + dashboard
- [ ] **2.1 API.** FastAPI verifies the Supabase JWT; routes: companies, predictions, targets, applications. Done: routes tested with a real signed-in token.
- [ ] **2.2 Dashboard skeleton.** React + Vite + TS, Google sign-in. Done: signs in, shows the user's email.
- [ ] **2.3 Targets view.** Tier, predicted window, open / not yet; star and unstar companies; pre-filled with tiered companies. Done: works in the browser with real predictions.
- [ ] **2.4 Extension skeleton.** WXT; popup sign-in; manual "I applied" button (FR-9). Done: loaded unpacked in Chrome, and a manual log shows up on the dashboard.
- [ ] **2.5 Greenhouse detection (hosted boards).** Check real pages first. Detect submit; log company, role, date, link. Done: a real (or test) application gets logged automatically.
- [ ] **2.6 Greenhouse detection (embedded iframes)** on company career pages. Done: verified on 2 companies that embed Greenhouse.
- [ ] **2.7 Ashby detection.** Done: verified on a real Ashby posting.
- [ ] **2.8 Match to Simplify listing.** Link a logged application to its posting when possible. Done: at least 80% of Daniel's logged applications match.
- [ ] **2.9 Applications view.** Status, date applied, days since; manual statuses (applied / OA / interview / rejected / offer); edit and delete. Done: works end to end.
- [ ] **2.10 On-page badge.** Tier + days open on posting pages (FR-10). Done: shows on Greenhouse and Ashby postings.
- [ ] **2.11 Dogfood checkpoint.** Daniel uses it for his own applications for a week. Done: a list of what annoyed him, and fixes triaged.

## Phase 3 -- Ghost signal + alerts
- [ ] **3.1 Ghost signal (FR-14).** Posting closed + 21 days with no status change → "likely moved on"; user can override. Done: shows on real applications.
- [ ] **3.2 Alert generation.** Modal jobs create `open_now` (new posting from a target) and `coming_soon` (likely opens within 14 days) rows, deduped. Done: rows appear for real targets.
- [ ] **3.3 Extension notifications.** Service worker polls `/alerts` with `chrome.alarms`; shows browser notifications; marks delivered. Done: a real notification fires.
- [ ] **3.4 Company detail page.** Opening-probability chart + past cycles. Done: renders for 5 companies.

## Phase 4 -- Hierarchical Bayesian model (Daniel drives)
- [ ] **4.1 Build it.** PyMC or NumPyro: company-level opening times pooled within groups, with censoring. Done: fits on all cycles; checks look sane (convergence, posterior predictive).
- [ ] **4.2 Head to head.** Backtest vs the simple model and the baseline, on the same held-out cycles. Done: a comparison write-up (where and why each wins); portfolio-ready.
- [ ] **4.3 Swap in if it wins.** New `model_version` in the nightly job. Done: dashboard shows the new windows.
- [ ] **4.4 Optional: GPU-cluster sweeps** of model variants. Done: results tracked.

## Phase 5 -- Launch prep
- [ ] **5.1 Data terms.** Check the SimplifyJobs license; add attribution. Done: noted in README and the dashboard footer.
- [ ] **5.2 Privacy policy.** What the extension reads and stores. Done: published page.
- [ ] **5.3 Deploy dashboard** (Vercel or Cloudflare Pages). Done: public URL.
- [ ] **5.4 Chrome Web Store.** Developer account (one-time fee), listing, review. Done: approved and installable.
- [ ] **5.5 First users.** Onboard 5 AI Club members; collect feedback. Done: 5 active users + notes.
- [ ] **5.6 Success check** against PRD section 6. Done: numbers written down.

## After MVP (v1.1+, from PRD)
Workday detection (FR-11), Gmail outcome classifier (FR-16, GPU cluster for fine-tuning), prep plan (FR-17), referral reminder (FR-18), ghost clock + wave detection (FR-19, v2).

---

## Progress log
- 2026-09-24: Tracker created from PRD. Build order set by Daniel: data + simple model first.

---

## Resuming this build

Default: pick the same session back up with `claude --continue` (same folder) or `claude --resume` (choose this build's session from the list). Claude Code remembers the conversation; most of the time that's the entire hand-off.

Start a fresh session only when continuing isn't convenient (new terminal, new day, different machine) or a long session has clearly degraded. Either way: read this tracker top to bottom, skim `docs/PRD.md`, check `git log` / `git status` against what the tracker says is done, then start at the first unchecked box.

Sessions started from the Tauros vault can also work here: orient with this file first, do the work in this repo, and write durable notes back to the vault.
