# Primora -- Build Tracker (v2)

**PRD:** `docs/PRD.md` (v2, rescoped 2026-10-15; source of truth for scope). Vault copy: `Tauros/projects/primora/PRD.md`.
**Status:** in progress
**Previous tracker:** `docs/archive/BUILD-TRACKER-v1-2026-10-08.md` (Phase 0 scaffolding + Phase 1 data work through 1.7, with its full progress log).

Takes Primora from the existing scaffold to a launched Chrome extension + dashboard that logs applications automatically and keeps the promising ones on top. Order: Supabase + auth, then the extension logger (the part Daniel needs while applying), then the dashboard, then launch.

**Legend:** `[~]` built, waiting on Daniel's live test; `[x]` verified live.

**Hard rules**
- Never commit secrets. The Supabase anon key is public by design; the service-role key never goes in client code or git.
- RLS on every user table (`user_id = auth.uid()`).
- No scraping beyond the page the user is on. Content scripts read only the application page being submitted.
- Check real pages before writing a detector.

**Working mode** `[ASSUMPTION: confirm with Daniel]`
- Tauros builds each phase in one batch; per-item recap + phase summary in chat and in the progress log; stop and ask on judgment calls.
- Daniel tests live after each phase before the next one starts.

**Parked (not deleted):** `pipeline/` (Phase 1 data: openings, tiers, backtests), `api/`, `modal_app.py`. Kept for later "opens soon" reminders.

---

## Phase 0 -- Foundation
- [~] **0.1 Repo cleanup.** README reflects v2 (extension + dashboard + Supabase; pipeline/api/modal marked parked). Done: README updated.
- [x] **0.2 Supabase + v2 schema.** Supabase project linked; new migration with only `job_applications` (see PRD section 7) + RLS + unique (user_id, url). v1 tables left in place (drop by hand if wanted). Done: table visible; a signed-in user can insert/read their own rows and can't read another user's.
- [x] **0.3 Dashboard sign-in.** supabase-js + Google sign-in in `web/`. Done: signs in, shows the user's email.

## Phase 1 -- Extension logging
- [x] **1.1 Extension sign-in.** Google via `chrome.identity.launchWebAuthFlow` + Supabase OAuth; session stored in `chrome.storage`. Fallback: email + password. Done: popup shows the signed-in email after a browser restart.
- [~] **1.2 Manual "I applied."** Popup button prefilled from the active tab (company, role, URL); editable before saving. Done: a manual log shows up in Supabase.
- [~] **1.3 Greenhouse detection (hosted boards).** Inspect real pages; pick the signal (confirmation page, submit request, or form submit). Log company, role, URL, date, source. Done: a real or test application gets logged automatically.
- [~] **1.4 Greenhouse detection (embedded iframes)** on company career pages. Done: verified on 2 companies that embed Greenhouse.
- [~] **1.5 Ashby detection.** Done: verified on a real Ashby posting.
- [x] **1.6 Duplicate guard + feedback.** Same URL twice → one row; a small toast/badge confirms "Logged: Company, Role." Done: double submit gives one row and one confirmation.
- [ ] **1.7 Firefox port.** Firefox is Daniel's default browser. Build the extension for Firefox with WXT (`wxt build -b firefox`) and fix what differs from Chrome: sign-in (`chrome.identity.launchWebAuthFlow` vs `browser.identity`; the Firefox redirect URL must be allowed in Supabase), content scripts in all frames for embedded Greenhouse, storage, toast + badge. Load via `about:debugging` > This Firefox > Load Temporary Add-on. Done: email sign-in, a Greenhouse confirmation logs with a toast, duplicate guard, and popup status change all work in Firefox; the Chrome build still works.

## Phase 2 -- Dashboard
- [x] **2.1 Applications list.** Priority sort (offer → interview → OA → applied → likely ghosted → rejected, newest first within each); auto-ghost display rule (applied + no change in 30 days). Done: renders Daniel's real applications in the right order.
- [x] **2.2 Status updates.** Change status from the dashboard and the popup; "still alive" resets the ghost clock. Done: an edit in the popup shows on the dashboard.
- [x] **2.3 Edit, delete, search.** Done: works end to end.
- [ ] **2.4 Dogfood week.** Daniel uses it for his own applications for a week. Done: a list of what annoyed him, fixes triaged.

## Phase 3 -- Launch prep
- [ ] **3.1 Privacy policy.** What the extension reads and stores. Done: published page.
- [ ] **3.2 Deploy dashboard** (Vercel or Cloudflare Pages). Done: public URL.
- [ ] **3.3 Chrome Web Store.** Developer account (one-time fee), listing, review. Done: approved and installable.
- [ ] **3.4 First users.** Onboard 5 AI Club members. Done: 5 active users + feedback notes.
- [ ] **3.5 Success check** against PRD section 6. Done: numbers written down.

## Later (from PRD)
"Opens soon" reminders from last year's dates (uses parked Phase 1 data), on-page posting context, Workday detection, Gmail outcome detection, CSV export.

---

## Progress log
- 2026-10-15: **Rescoped to v2** (Daniel's call). Survival model cut: per-company data too thin, and "about when it opened last year" is the useful estimate anyway (1.7 backtest: ~26 days off for tiered companies). Email/Gmail cut for now. MVP = submit interceptor (Greenhouse + Ashby, manual button elsewhere) + applications dashboard + status updates, sorted by how promising. Auto-ghost after 30 days with no change, computed on read. Dropped FastAPI + Modal; both clients talk to Supabase directly with RLS. Phase 1 data work parked for future reminders. Old PRD and tracker archived in `docs/archive/`. **Next:** 0.1-0.3.

- 2026-10-15: **Built 0.1 through 2.3 in one pass** (Daniel: "just build it all now following the PRD"). Waiting on Daniel's live test.
  - 0.1: README rewritten for v2; `docs/TESTING.md` added.
  - 0.2: `supabase/migrations/20261015000000_v2_job_applications.sql`: new table `job_applications` (RLS, unique user+posting_key, trigger restarts the ghost clock on status change). Named `job_applications` because dropping the v1 tables was blocked as destructive; they stay, unused. **Not pushed yet: the `primora` Supabase project is paused** (DNS gone); restore it, then `supabase db push`.
  - 0.3 / 1.1: email + password sign-in in both clients; Google sign-in wired (dashboard redirect; extension via `chrome.identity.launchWebAuthFlow` in the background worker) but needs the Google provider configured in Supabase.
  - 1.2: popup "I applied", prefilled from the tab title (Greenhouse "Job Application for X at Y", Ashby "X @ Y", "Company Careers | Role").
  - 1.3 / 1.4: checked real pages first. Greenhouse confirmation is `/<board>/jobs/<id>/confirmation` (hosted) or `/embed/job_app/confirmation?for=&token=` (iframe); content script runs in all frames. Fallback: "Thank you for applying" after a seen submit click. Names cleaned via the public boards API.
  - 1.5: Ashby stays on `/application` and shows "Your application was successfully submitted" (default text, found in Ashby's bundle); weaker phrases count only after a seen submit.
  - 1.6: posting keys (`greenhouse:board:id`, `ashby:org:id`, normalized URL) + upsert ignore; toast in-page; logs queue while signed out and sync on sign-in (badge shows the count).
  - 2.1 to 2.3: dashboard grouped by priority, filter chips with counts, search, add/edit/delete with inline confirm, "Still alive" on auto-ghosted rows, refresh on tab focus. Shared logic in `shared/applications.ts` (6 tests pass: `node --test shared/*.test.ts`). Theme tokens in `shared/theme.css` for Daniel's theme later.
  - **Next:** Daniel restores Supabase + tests per `docs/TESTING.md`; then 2.4 dogfood week.
- 2026-10-15: Daniel restored the Supabase project; `supabase db push` applied the v2 migration. Database end-to-end check with two throwaway users (deleted after): insert, duplicate ignored, other user can't read or insert, status change restarts the ghost clock, signed-out sees nothing. All 6 pass. 0.2 verified.
- 2026-10-15: **Daniel's live browser test.** Account created + signed in on the dashboard (email/password); extension loaded unpacked and signed in. Greenhouse confirmation URL → toast + row on the dashboard; refresh → "already logged", no duplicate; popup "This page" status change to Interview → dashboard regrouped. Verified: 0.3, 1.1 (email; Google not configured), 1.6, 2.2. 1.3 confirmation-URL path verified; a real submit still to watch.
- 2026-10-15: Live test found a bug: a backdated manual entry never showed as likely ghosted (its clock started at save time). Fixed in `c69920b` (clock starts at the applied date). Retested by Daniel: ghosted + "Still alive" work; add/delete work. Verified 2.1, 2.3. **Still to see live (during the dogfood week):** a real Greenhouse submit, embedded Greenhouse, a real Ashby submit, manual "I applied" on another site, the signed-out queue. **Next:** 2.4 dogfood week; Daniel's theme; Google sign-in setup.

- 2026-10-15: Added **1.7 Firefox port** (Daniel's default browser). **Next session starts here**, then 2.4 dogfood week, Daniel's theme, Google sign-in setup.

---

## Resuming this build
Default: `claude --continue` (same folder) or `claude --resume`. In a fresh session: read this tracker, skim `docs/PRD.md`, check `git log` / `git status` against what's marked done, then start at the first unchecked box. Sessions started from the Tauros vault can work here too: orient with this file first, do the work in this repo, and write durable notes back to the vault.
