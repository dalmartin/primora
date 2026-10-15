# Primora -- Build Tracker (v2)

**PRD:** `docs/PRD.md` (v2, rescoped 2026-10-15; source of truth for scope). Vault copy: `Tauros/projects/primora/PRD.md`.
**Status:** in progress
**Previous tracker:** `docs/archive/BUILD-TRACKER-v1-2026-10-08.md` (Phase 0 scaffolding + Phase 1 data work through 1.7, with its full progress log).

Takes Primora from the existing scaffold to a launched Chrome extension + dashboard that logs applications automatically and keeps the promising ones on top. Order: Supabase + auth, then the extension logger (the part Daniel needs while applying), then the dashboard, then launch.

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
- [ ] **0.1 Repo cleanup.** README reflects v2 (extension + dashboard + Supabase; pipeline/api/modal marked parked). Done: README updated.
- [ ] **0.2 Supabase + v2 schema.** Supabase project linked; new migration with only `applications` (see PRD section 7) + RLS + unique (user_id, url). Retire the v1 tables. Done: table visible; a signed-in user can insert/read their own rows and can't read another user's.
- [ ] **0.3 Dashboard sign-in.** supabase-js + Google sign-in in `web/`. Done: signs in, shows the user's email.

## Phase 1 -- Extension logging
- [ ] **1.1 Extension sign-in.** Google via `chrome.identity.launchWebAuthFlow` + Supabase OAuth; session stored in `chrome.storage`. Fallback: email + password. Done: popup shows the signed-in email after a browser restart.
- [ ] **1.2 Manual "I applied."** Popup button prefilled from the active tab (company, role, URL); editable before saving. Done: a manual log shows up in Supabase.
- [ ] **1.3 Greenhouse detection (hosted boards).** Inspect real pages; pick the signal (confirmation page, submit request, or form submit). Log company, role, URL, date, source. Done: a real or test application gets logged automatically.
- [ ] **1.4 Greenhouse detection (embedded iframes)** on company career pages. Done: verified on 2 companies that embed Greenhouse.
- [ ] **1.5 Ashby detection.** Done: verified on a real Ashby posting.
- [ ] **1.6 Duplicate guard + feedback.** Same URL twice → one row; a small toast/badge confirms "Logged: Company, Role." Done: double submit gives one row and one confirmation.

## Phase 2 -- Dashboard
- [ ] **2.1 Applications list.** Priority sort (offer → interview → OA → applied → likely ghosted → rejected, newest first within each); auto-ghost display rule (applied + no change in 30 days). Done: renders Daniel's real applications in the right order.
- [ ] **2.2 Status updates.** Change status from the dashboard and the popup; "still alive" resets the ghost clock. Done: an edit in the popup shows on the dashboard.
- [ ] **2.3 Edit, delete, search.** Done: works end to end.
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

---

## Resuming this build
Default: `claude --continue` (same folder) or `claude --resume`. In a fresh session: read this tracker, skim `docs/PRD.md`, check `git log` / `git status` against what's marked done, then start at the first unchecked box. Sessions started from the Tauros vault can work here too: orient with this file first, do the work in this repo, and write durable notes back to the vault.
