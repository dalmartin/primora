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

## Decisions
- **2026-10-04 (Daniel): "opening" = the first SWE-intern posting per company per Summer cycle.** Category-level openings can come later.
- **For 1.4 (Daniel's call):** how to treat `multi_cycle` and `terms_changed` postings (exclude, or count from when the term changed); and `first_seen_censored` (297 listings already present on 2023-08-02, so the Summer 2024 cycle is left-censored for early openers).
