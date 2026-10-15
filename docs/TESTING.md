# Testing Primora in your browser

## One-time setup
1. **Database.** The `primora` Supabase project must be active (free projects pause when idle; restore from the Supabase dashboard). Then from the repo root: `supabase db push`. That creates `job_applications`.
2. **Env files.** `web/.env.local` and `extension/.env.local` hold the project URL + anon key (gitignored; copy from the `.env.example` files).
3. **Dashboard.** `cd web && npm install && npm run dev`, open http://localhost:5173, click **Create account** (email + password).
   - Hosted Supabase emails a confirmation link. Clicking it confirms the account even if the page it lands on doesn't load; then sign in. (Or turn off "Confirm email" under Authentication → Providers → Email while testing.)
4. **Extension.** `cd extension && npm install && npm run build`. In Chrome: `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → pick `extension/.output/chrome-mv3`. Pin the Primora icon. Click it and sign in with the same account.
   - After code changes: `npm run build`, then hit the reload arrow on the extension card. (`npm run dev` also works; it opens a separate Chrome profile with the extension loaded and hot-reloads.)
5. **Firefox (optional).** `cd extension && npm run build:firefox`. In Firefox: `about:debugging` → **This Firefox** → **Load Temporary Add-on…** → pick `extension/.output/firefox-mv3/manifest.json`. It stays loaded until Firefox quits. Pin it from the puzzle-piece (extensions) menu, then click it and sign in.
   - After code changes: `npm run build:firefox`, then **Reload** on the add-on's card. (`npm run dev:firefox` opens a separate Firefox profile with hot reload.)
   - Needs Firefox 142+ (both builds are Manifest V3).

## What to try
- **Greenhouse auto-log without applying anywhere:** open
  https://job-boards.greenhouse.io/anthropic/jobs/4461450008/confirmation
  A green toast should say "Primora logged: Account Executive, AI Native at Anthropic". It appears on the dashboard (refreshes when the tab gets focus). Delete it afterwards. Visiting again says "already logged" (duplicate guard).
- **Embedded Greenhouse:** same with
  https://job-boards.greenhouse.io/embed/job_app/confirmation?for=anthropic&token=4461450008
  (same posting, so it should say "already logged" unless you deleted the first one).
- **Real applications:** apply normally on Greenhouse (`job-boards.greenhouse.io/...` or a company page that embeds it) or Ashby (`jobs.ashbyhq.com/...`). The toast appears after the confirmation shows.
- **Anywhere else (Workday, Lever, company sites):** click the Primora icon → company/role are prefilled from the page → **I applied**.
- **Signed out:** sign out in the popup, visit the confirmation link above. The toast says it's saved for later and the icon shows a count. Sign back in: it syncs.
- **Dashboard:** change statuses (the list re-sorts: offer → interview → OA → applied → likely ghosted → rejected), search, filter chips, edit, delete, "+ Add application". Add one by hand with an "Applied on" date 31+ days ago to see "Likely ghosted" + **Still alive**.

## Automated check (headless)
`extension/e2e/e2e.py` drives headless Firefox or Chrome with the built extension against the real Supabase project: signed-out queue + badge, popup sign-in and sync, Greenhouse API name cleanup, duplicate guard, embedded Greenhouse iframe, popup status change, and (Firefox) manual "I applied". It creates a throwaway user with the service-role key from the root `.env` and deletes it afterwards. Run command is at the top of the file.

## Not set up yet
- **Google sign-in** needs a Google OAuth client and the Google provider enabled in Supabase, with these redirect URLs allowed: `http://localhost:5173` (dashboard) and `https://<extension-id>.chromiumapp.org/` (Chrome extension; the ID is on the `chrome://extensions` card), and `https://ae1479f9372be75efe117634082fe5cd7148462a.extensions.allizom.org/` (Firefox; fixed, derived from the add-on ID `primora@primora.app`). Email + password works without it.
