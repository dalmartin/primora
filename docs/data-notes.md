# Primora -- Data notes

What we learned about the SimplifyJobs data, and the decisions that follow from it. Newest findings go at the bottom of each section; decisions are dated.

## Source
- `SimplifyJobs/Summer2027-Internships`, file `.github/scripts/listings.json`. The Summer2024/25/26 repo names all redirect here (one renamed repo).
- History of that file starts **2023-08-02**, not Nov 2022 as the PRD assumed: 27,973 commits through 2026-10-03, all parsed. That's about 3 full Summer cycles (2024, 2025, 2026) plus the current one (2027). Earlier history may live at another path (`git log` without `--follow` misses renames); not checked yet.
- The current file is pruned (only back to Feb 2026), so older cycles exist only in git history.

## Extract (tracker 1.1)
- `history/observations.parquet`: 208,541 change events (43,825 added / 137,729 changed / 26,987 removed); 42,981 listings, 5,019 companies. `date_updated`-only edits are ignored.
- Check: replaying events reproduces the latest file exactly (16,838 live listings).

## Postings table (tracker 1.2)
`postings.parquet`, one row per listing; columns documented in `pipeline/src/primora_pipeline/postings.py`.

**Categories only exist from May 2025.** Before that, every listing has a NULL category, which covers most of the 2024 and 2025 cycles. Simplify's categories were also renamed in Aug 2025 (for example "Software" → "Software Engineering"); both are mapped to one normalized set.

**SWE is decided by title, not category** (`SWE_TITLE_PATTERN`), so every cycle is labeled the same way. Against Simplify's own category (listings from May 2025 on): about 78% precision, 74% recall. Many disagreements are Simplify's category being wrong (for example "Software Engineer Intern" filed under Hardware or AI/ML), and many misses are generic titles ("Engineering Intern", "Technology Intern") that aren't clearly SWE. For openings, precision matters more than recall: a company needs only one clearly SWE posting to count as open.

**`active` flaps a lot.** About 48k close→reopen spells: median about 6.5 hours, 75% reopen within a day, 90% within 8 days. Likely Simplify's link checker. So `closed_at` = the **final** close; `first_closed_at` is kept for reference. 32% of listings reopen at least once.

**`date_posted` ≈ first commit time** (median lag about 45 minutes, p90 about 4 days). It's when Simplify added the listing, not when the company posted it. The real lag vs the company's own posting date is tracker 1.3.

**Cycle** = earliest "Summer YYYY" in the listing's latest terms.
- Latest terms, not first: 1,392 listings changed terms, mostly a bulk correction (734 "Winter 2025" → "Summer 2026", 251 "Fall 2025" → "Summer 2026").
- About 56 Summer 2026 listings were relabeled from Summer 2024/2025: reused postings, so their `first_seen` is from an earlier cycle. Flagged as `terms_changed`.
- Rolling postings tagged for several Summer terms are flagged `multi_cycle` (5 to 29 SWE postings per cycle). Example: Amazon's SDE listing tagged Fall 2025 through 2028 with "2025" in the title.

**SWE summer postings per cycle:** 2024: 1,768 (743 companies) · 2025: 2,458 (808) · 2026: 5,189 (1,511) · 2027 so far: 1,083 (417).

**Spot check (first SWE posting seen, by cycle):** Citadel and Jane Street early July; Google and Microsoft mid-to-late August; Capital One Dec/Jan. Sensible. **Coverage gap:** Meta's first Summer 2025 SWE posting in Simplify is 2025-01-04, but Meta usually opens around September. So Simplify can be months late or miss a company entirely; 1.3 should check how often.

## Simplify lag (tracker 1.3)
`pipeline/src/primora_pipeline/lag.py` → `simplify_lag.parquet`, `board_coverage.parquet`. Rerun prints every number below.

**Method.** Instead of a 20-30 sample, every SWE posting hosted on Greenhouse, Ashby or Lever is matched to the company's own job board (one request per board, 1,954 boards). Company date: Greenhouse `first_published`, Ashby `publishedAt`, Lever `createdAt`. Includes 652 postings that link to a company's own careers site with a Greenhouse `gh_jid` (Waymo, Lyft, Roku...), resolved by guessing the board token and keeping it only if the job id is on it. **492 SWE postings matched.**

**Limit: this is mostly the current cycle.** Boards only list open jobs, so closed postings from past cycles can't be checked (382 boards are gone entirely). We are assuming past cycles behaved like this one. EU Greenhouse boards (76 postings, e.g. IMC) have no reachable API; Workday, iCIMS, SmartRecruiters and company-built sites (Meta, Google, Amazon, Tesla, TikTok) have no comparable date at all. So the Meta Summer 2025 gap from 1.2 can't be checked this way.

**Postings fall into four buckets:**
- **Fresh (78%):** a new post Simplify picked up within a week. **Median 4.6 hours behind the company; p75 7h, p90 15h.** Greenhouse and Ashby about 4.5h (p90 under 10h); Lever slower, median 14h, p90 about 5 days (`createdAt` can predate publishing, so Lever may overstate).
- **Late (7%):** picked up 1 week to 3 months after the company posted. Real misses, e.g. Cloudflare SWE Intern posted 9/16, in Simplify 9/28.
- **Evergreen (10%):** posts years older than the cycle, reused cycle after cycle (Palantir's Lever posts from 2016-2022; Jane Street, QuantCo). Their company date says nothing about when this cycle opened; Simplify's first_seen is the better signal for these.
- **Republished (5%, all Ashby):** company date is *after* Simplify saw it, because republishing resets `publishedAt`.

**Coverage (Summer 2027, posts from 2026).** Of 190 explicit Summer 2027 SWE intern posts on boards Simplify already tracks, Simplify has 78%. Posting-level misses don't always matter: a company only needs one SWE posting to count as open.

**Opening-date error, the number that matters.** Per company (95 companies with a Summer 2027 SWE intern post on these boards), compare the board's first such post with Simplify's first SWE cycle-2027 posting from that board:
- 78 of 95 (82%) appear in Simplify. Of those: 63 within a day, 7 within a week, 6 more than a week late, 2 earlier in Simplify (republished posts). **Median error 0.2 days, p90 3.5 days.**
- 17 (18%) have no SWE posting in Simplify at all, mostly small companies (Advanced Space, Armadin, Netic) but also AppLovin, SingleStore and Airwallex. A few may be false misses: Simplify sometimes links a company's own site with no recoverable board (C3.ai is one).

**Takeaways for modeling.**
1. When Simplify has a company, `first_seen` is a good opening date: hours off, not days. No lag correction is needed for the model; treat it as noise of about a day.
2. The real risk is **coverage, not lag.** Something like 1 in 6 companies' openings are missing or more than a week late. An opening never seen looks like a company that didn't open, which biases toward "opens late / doesn't hire." Worth weighing in 1.4 (which companies count) and when choosing the top ~100 in 1.5 (prefer ones with consistent coverage across cycles).
3. Evergreen and multi-cycle postings are the same phenomenon seen from two sides (see `multi_cycle` / `terms_changed` in 1.2). For those, the opening is when Simplify (re)tagged them for the cycle, not the post's own date.

## Openings table (tracker 1.4)
`pipeline/src/primora_pipeline/openings.py` → `openings.parquet` + `openings.csv`: one row per company per Summer cycle (2024-2027), 2,284 companies with any SWE Summer posting. Columns documented in the module. To look at it: `uv run python scripts/view_openings.py` (from `pipeline/`) writes `data/openings_wide.csv` (one row per company, one date column per cycle) and draws a chart.

**Opened per cycle:** 2024: 632 (+61 left-censored "on or before 2023-08-02") · 2025: 807 · 2026: 1,509 · 2027 so far: 442 (1,878 not yet). 2,320 companies.

**Cycle window (Daniel confirmed 2026-10-08).** A tag only counts if it lands between Jan 1 of the year before the cycle and Aug 31 of the cycle year. Without it, rolling and mislabeled posts set absurd dates: Amazon's Summer 2026 and 2027 both "opened" 2024-10-17 via one rolling post; General Motors' Summer 2024 "opened" in Jan 2026; Intuitive Surgical's Summer 2027 in Jan 2025. Out-of-window tags are counted in `n_out_of_window`. The constant is easy to change.

**Spot check now looks right:** Microsoft early-to-mid Aug every year; NVIDIA late Aug / early Sep; American Express, Stryker, Oshkosh within days of the same date each cycle. Some companies wander by months (Tesla, Tradeweb, Applied Materials). That spread is what the model has to learn.

**Unlabeled postings (new finding).** Since 2026, Simplify often leaves `terms` as "N/A" (about 30-75 SWE postings a month). Some are real Summer internships: Jane Street's "Software Engineer Intern" (2026-08-03) has terms N/A, so Jane Street shows "not yet" for 2027 when it has opened. **Decision (Daniel, 2026-10-08): they count.** An SWE intern posting with no season counts toward the Summer after it (first seen Jul 1 of the prior year through Jun 30), flagged `via_unlabeled`. It sets the opening for 21 companies in 2027 (Jane Street: 2026-07-06), 27 in 2025, 17 in 2026.

**Still missing after this:** Meta and Citadel show "not yet" for 2027. Meta's Summer 2027 SWE intern posting is on speedyapply but not Simplify; that's the case for adding speedyapply next.

## Decisions
- **2026-10-04 (Daniel): "opening" = the first SWE-intern posting per company per Summer cycle.** Category-level openings can come later.
- **2026-10-08 (Daniel), rules for the `openings` table (1.4):**
  1. `multi_cycle` postings count toward a cycle from when they were first tagged for that cycle, not from the post's original date.
  2. `terms_changed` postings (about 56 reused from earlier cycles) count from the relabel date.
  3. Summer 2024 is kept. Openings already present on 2023-08-02 (`first_seen_censored`) are marked left-censored ("opened on or before 2023-08-02"), not given a guessed date.
  4. No company is dropped for coverage now. Add a coverage flag; the 1.7 backtests decide whether low-coverage companies hurt predictions.
  5. Cycle window: a tag only counts between Jan 1 of the year before the cycle and Aug 31 of the cycle year.
  6. SWE intern postings with no season (terms N/A) count toward the Summer after them (Jul-Jun).
