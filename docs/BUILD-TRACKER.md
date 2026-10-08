# Primora -- Build Tracker

**PRD:** `docs/PRD.md` (source of truth for scope; this file tracks *doing* it, not *what* it is). Vault copy: `Tauros/projects/primora/PRD.md`.
**Status:** in progress

Takes Primora from an empty repo to a launched Chrome extension + dashboard. Order: a quick scaffolding pass, then **the data and the simple model first** (Daniel's call, 2026-09-24), then the extension and dashboard, then alerts, then the Bayesian model, then launch.

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
- [x] **0.1 Repo layout.** Monorepo: `pipeline/` (Python, uv), `api/` (FastAPI), `web/` (React + Vite + TS), `extension/` (WXT + React + TS), `docs/`. README, `.gitignore`, `.env.example`. Done: repo structure committed; `pipeline` env installs.
- [x] **0.2 Python env.** uv project with duckdb, polars (or pandas), lifelines, scikit-survival, matplotlib, jupyter, and MLflow or W&B. Done: a notebook imports everything.
- [ ] **0.3 Supabase.** New project; migration for the 7 tables (companies, postings, openings, predictions, targets, applications, alerts); row-level security on user tables; Google sign-in enabled. Done: tables visible in Supabase; a test sign-in works. **Google sign-in deferred to Phase 2 (2026-10-03).**
- [x] **0.4 Modal.** Account + CLI auth; hello-world scheduled function; FastAPI `/health` web endpoint; Supabase keys in Modal Secrets. Done: `modal deploy` gives a URL that returns ok, and the scheduled function shows runs in the dashboard.

## Phase 1 -- Data + simple model (Daniel drives)
- [x] **1.1 Extract history.** Clone SimplifyJobs; walk every commit touching `.github/scripts/listings.json`; write per-listing observations (listing ID, commit time, active, fields) to Parquet. Done: Parquet exists; listing counts sanity-checked against the current file (about 17k).
- [x] **1.2 Postings table.** Per listing: company, title, category, first_seen, closed_at, cycle. Compare `date_posted` vs first commit time. Done: DuckDB query returns sensible rows for 5 known companies.
- [x] **1.3 Measure the Simplify lag.** Sample 20-30 postings; compare Simplify's date to the real posting date (Greenhouse / Ashby job-board APIs where available). Done: median and spread written to `docs/data-notes.md`.
- [x] **1.4 Define "opening" + openings table.** Decide: first posting of any role vs first SWE-intern posting, per cycle. Build `openings`, with the current cycle's not-yet-opened companies marked censored. Done: decision in `docs/data-notes.md`; table built.
- [x] **1.5 Company metadata.** Hand-curate `companies.csv` for the top ~100 companies: tier (prestige / pipeline / none) and group (big tech / quant / bank / startup / other). Done: file committed, joined into DuckDB.
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
- 2026-09-24: Project renamed Primora (was Internship Radar).
- 2026-09-24: 0.1 done. uv workspace (`pipeline/`, `api/`), `modal_app.py`, `web/` (Vite React TS, builds), `extension/` (WXT React, builds as "Primora"), README, .gitignore, .env.example.
- 2026-09-24: 0.2 done. `uv sync` OK; duckdb 1.5.5, lifelines 0.30.3, scikit-survival 0.28.0, mlflow, modal 1.5.5 import; API `/health` returns ok via TestClient.
- 2026-09-24: 0.3 partial. `supabase/` initialized; initial migration (7 tables + RLS) written and parses (25 statements). Still needs: cloud project, `supabase link`, `db push`, Google sign-in.
- 2026-09-24: 0.4 partial. Modal app written (hourly + nightly stubs, API endpoint, `primora-data` volume). Still needs: `modal token new`, then `modal deploy`.
- 2026-10-03: Phase 0 scaffolding committed. Modal authed (workspace `dalmartin`) and deployed: `https://dalmartin--primora-api.modal.run/health` returns ok; `refresh_postings` runs. Remaining for 0.4: Supabase keys in Modal Secrets (after 0.3).
- 2026-10-03: 0.3 mostly done. Supabase org + project `primora` (ref `alwzilzgszpxnjmlqcxx`, us-west-2) created; linked; migration pushed; all 7 tables respond via REST. Keys in local `.env` (ignored) and Modal secret `primora-supabase`. Still needs: Google sign-in provider (Google Cloud OAuth client) + test sign-in.
- 2026-10-03: Google sign-in deferred to Phase 2 (Daniel: layer auth in later). Starting Phase 1.
- 2026-10-03: 0.4 done. Secret attached to all 3 functions; redeployed; `/health` ok.

- 2026-10-03: **1.1 run 1 (paused, Daniel at an OA).** Findings: Summer2024/25/26 repo names redirect to `Summer2027-Internships` (one renamed repo = multiple cycles). Current listings.json only goes back to Feb 2026 (pruned), so older cycles exist only in git history. ~16.9k listings now; schema: id, company_name, title, category, active, is_visible, terms, date_posted, date_updated, url, locations, source, sponsorship, company_url, degrees.
  - Local clone abandoned: >2 GB at ~1 MB/s, hit the 30-min limit; laptop disk is 95% full (23 GB free). Nothing left in `data/raw/`.
  - Wrote `pipeline/src/primora_pipeline/extract_history.py`: streams every listings.json version via `git cat-file --batch`, writes **change events** (added / changed / removed; date_updated ignored) to `history/observations.parquet` + `history/commits.parquet`. Observation definition = Daniel's call to confirm.
  - Added `orjson` (pipeline dep + Modal image), `PRIMORA_DATA_DIR=/data` in the image, and a Modal function `extract_history` (4 CPU, 8 GB, 2h timeout) that bare-clones onto the `primora-data` volume.
  - Launched `modal run --detach modal_app.py::extract_history`. **On resume:** check the run at https://modal.com/apps/dalmartin/main (or `modal app logs`); if it finished, `modal volume get primora-data history data/` and sanity-check counts (latest commit ~16.9k listings; commits.parquet statuses). If it failed, read the traceback. Then: redeploy (`modal deploy`) so the scheduled functions get the new image, commit, and confirm the observation definition with Daniel before 1.2.
  - Uncommitted: extract_history.py, modal_app.py, pipeline/pyproject.toml, uv.lock, this tracker.
- 2026-10-03 (evening, resumed): first Modal run was on track to hit its 2h timeout (22k/28k commits at 1h20m; an unclosed Parquet writer = unreadable file). Its "events" counter was also inflated (counted the unflushed batch every commit; the data itself was fine). Fixes: counter counts only new rows; change detection compares field values directly instead of serializing each field (much faster); timeout raised to 6h. Verified on a synthetic 5-commit repo (date_updated-only edits ignored; added / changed / removed correct). Daniel chose kill + relaunch. Old run stopped; new run `ap-F8uMtPBysSwmuE4FfhFe1q` launched (logs in `logs/`, gitignored). Note: local `modal` CLI is old; use `uv run modal ...` (`app stop --yes`).
- 2026-10-03: **1.1 extract done.** 208,541 events (43,825 added / 137,729 changed / 26,987 removed) from 27,973 commits, all parsed OK; 42,981 listings, 5,019 companies. Replaying events reproduces the latest file exactly (16,838 live listings). Local copy in `data/history/` (gitignored). **Finding:** `listings.json` history starts 2023-08-02, not Nov 2022 as the PRD assumed, so about 3 full cycles plus the current one; 2023 adds are thin (2,479), partly because that cycle is only half covered. Worth checking whether earlier history lived at another path (`git log` without `--follow` misses renames).
  - **Still to do:** Daniel runs `uv run modal deploy modal_app.py` (blocked for Tauros by a permission check) so the scheduled functions get the new image. Daniel confirms the "opening" definition before 1.2.
- 2026-10-04: Daniel redeployed; scheduled functions on the new image. Only open item before 1.2: the "opening" definition.
- 2026-10-04: **Opening definition (Daniel): first SWE-intern posting per company per Summer cycle.** Recorded in `docs/data-notes.md`.
- 2026-10-04: **1.2 done.** `pipeline/src/primora_pipeline/postings.py` → `data/postings.parquet` (42,981 rows); test in `pipeline/tests/test_postings.py`. Findings (details in `docs/data-notes.md`): categories only exist from May 2025, so SWE is decided by a title rule for every cycle (about 78% precision / 74% recall vs Simplify's noisy categories); `active` flaps (median false close about 6.5h), so `closed_at` = final close; `date_posted` ≈ when Simplify added it (1.3 measures the real lag); cycle from latest terms, with `multi_cycle` / `terms_changed` flags. Spot check on 7 known companies looks sensible; Meta Summer 2025 shows up months late (coverage gap for 1.3). **Next:** 1.3 lag measurement, then Daniel takes over at 1.4 (decide how to treat multi_cycle / terms_changed / censored postings).
- 2026-10-04: **1.3 done.** `pipeline/src/primora_pipeline/lag.py` (test `pipeline/tests/test_lag.py`) matches every Greenhouse/Ashby/Lever SWE posting to the company's board instead of a 20-30 sample: 492 matched. Fresh posts: Simplify trails the company by a median 4.6h (p90 15h). Per company for Summer 2027: 82% of openings are in Simplify, median error 0.2 days; 18% have no SWE posting in Simplify. Conclusion: lag is negligible, coverage is the real risk. Limit: only open jobs are checkable, so this is mostly the current cycle. Details in `docs/data-notes.md`. **Next:** Daniel takes over at 1.4.
- 2026-10-08: Daniel agreed to Tauros's defaults for the four 1.4 calls (multi_cycle and relabels count from when tagged for the cycle; keep Summer 2024 with left-censoring; flag coverage, don't drop). Tauros built it (Daniel's call this session). **1.4 done.** `openings.py` + `tests/test_openings.py`; viewer `pipeline/scripts/view_openings.py` (wide CSV + chart). Added a cycle-window rule (tags outside Jan 1 of the prior year to Aug 31 count as errors) for Daniel to confirm. New finding: Simplify's N/A-term postings hide some real openings (Jane Street 2027). Daniel then confirmed the window rule and said no-season SWE intern posts count toward the next Summer (Jane Street 2027 now opens 2026-07-06). **Next:** speedyapply as a second source (fills coverage gaps, incl. company-built career sites), then 1.5.
- 2026-10-08: **speedyapply added as a second source** (Daniel's call). `speedyapply.py` parses all 1,037 versions of its markdown tables (19,303 internship postings since 2024-01-01). Merged into `openings.py` (rule 6 in the module; tests extended). Dates within a day of company boards; fills Simplify's gaps (Meta 2025 moves Jan → Sep 2024; Meta and Apple 2027 now open). 2,700 companies. Viewer marks speedyapply dates with "+". To do at 1.10: add speedyapply to the scheduled Modal job. **Next:** 1.5 company metadata.
- 2026-10-08: **1.5 done, for every company** (Daniel: "do all of them"). `companies.py` + `tests/test_companies.py`; labels in `pipeline/reference/company_labels.csv` (1,510 hand labels, Tauros's first pass for Daniel to correct), merges in `reference/company_aliases.csv`. 86 prestige, 136 pipeline, 16 groups. Tightened the speedyapply prefix match (generic suffixes only). Viewer gained `--tier` / `--group`. **Next:** 1.6 exploratory analysis.

---

## Resuming this build

Default: pick the same session back up with `claude --continue` (same folder) or `claude --resume` (choose this build's session from the list). Claude Code remembers the conversation; most of the time that's the entire hand-off.

Start a fresh session only when continuing isn't convenient (new terminal, new day, different machine) or a long session has clearly degraded. Either way: read this tracker top to bottom, skim `docs/PRD.md`, check `git log` / `git status` against what the tracker says is done, then start at the first unchecked box.

Sessions started from the Tauros vault can also work here: orient with this file first, do the work in this repo, and write durable notes back to the vault.
