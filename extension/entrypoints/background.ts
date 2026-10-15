import { supabase } from '@/lib/supabase';
import { QUEUE_KEY, type LogResult, type Message } from '@/lib/messages';
import { TABLE, type NewApplication, type PostingRef } from '../../shared/applications';

export default defineBackground(() => {
  browser.runtime.onMessage.addListener((msg: Message, _sender, sendResponse) => {
    if (msg.type === 'log-application') {
      enrich(msg.app, msg.ref)
        .then(logOrQueue)
        .then(sendResponse);
      return true; // async response
    }
    if (msg.type === 'sign-in-google') {
      signInWithGoogle().then(sendResponse, (e) => sendResponse({ error: String(e?.message ?? e) }));
      return true;
    }
    if (msg.type === 'flush-queue') {
      flushQueue().then(sendResponse);
      return true;
    }
  });

  supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_IN') void flushQueue();
  });
  void refreshBadge();
});

/** Fill in clean company / role names from the public job-board APIs; keep page values on failure. */
async function enrich(app: NewApplication, ref: PostingRef | null): Promise<NewApplication> {
  if (!ref) return app;
  try {
    if (ref.ats === 'greenhouse') {
      const res = await fetchWithTimeout(`https://boards-api.greenhouse.io/v1/boards/${ref.org}/jobs/${ref.jobId}`);
      if (res.ok) {
        const job = (await res.json()) as { title?: string; company_name?: string };
        return { ...app, role: job.title?.trim() || app.role, company: job.company_name?.trim() || app.company };
      }
    } else {
      const res = await fetchWithTimeout(`https://api.ashbyhq.com/posting-api/job-board/${ref.org}`);
      if (res.ok) {
        const board = (await res.json()) as { jobs?: { id: string; title: string }[] };
        const job = board.jobs?.find((j) => j.id.toLowerCase() === ref.jobId.toLowerCase());
        return { ...app, role: job?.title?.trim() || app.role };
      }
    }
  } catch {
    // Offline or blocked: the page-scraped names are good enough.
  }
  return app;
}

async function fetchWithTimeout(url: string, ms = 4000): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function insert(app: NewApplication, userId: string): Promise<{ duplicate: boolean }> {
  const { data, error } = await supabase
    .from(TABLE)
    .upsert({ ...app, user_id: userId }, { onConflict: 'user_id,posting_key', ignoreDuplicates: true })
    .select('id');
  if (error) throw error;
  return { duplicate: (data ?? []).length === 0 };
}

async function logOrQueue(app: NewApplication): Promise<LogResult> {
  const names = { company: app.company, role: app.role ?? null };
  const { data } = await supabase.auth.getSession();
  if (!data.session) {
    await enqueue(app);
    return { ok: false, queued: true, reason: 'signed-out', ...names };
  }
  try {
    const { duplicate } = await insert(app, data.session.user.id);
    await flashBadge(duplicate ? '=' : '✓');
    return { ok: true, duplicate, ...names };
  } catch (e) {
    console.error('Primora: save failed, queued', e);
    await enqueue(app);
    return { ok: false, queued: true, reason: 'error', ...names };
  }
}

async function readQueue(): Promise<NewApplication[]> {
  const got = await browser.storage.local.get(QUEUE_KEY);
  return (got[QUEUE_KEY] as NewApplication[] | undefined) ?? [];
}

async function enqueue(app: NewApplication) {
  const queue = await readQueue();
  if (!queue.some((q) => q.posting_key === app.posting_key)) queue.push(app);
  await browser.storage.local.set({ [QUEUE_KEY]: queue });
  await refreshBadge();
}

async function flushQueue(): Promise<{ saved: number; left: number }> {
  const { data } = await supabase.auth.getSession();
  const queue = await readQueue();
  if (!data.session || queue.length === 0) return { saved: 0, left: queue.length };
  const left: NewApplication[] = [];
  let saved = 0;
  for (const app of queue) {
    try {
      await insert(app, data.session.user.id);
      saved++;
    } catch {
      left.push(app);
    }
  }
  await browser.storage.local.set({ [QUEUE_KEY]: left });
  await refreshBadge();
  return { saved, left: left.length };
}

/** "!" on the toolbar icon while logs are waiting for sign-in. */
async function refreshBadge() {
  const queue = await readQueue();
  await browser.action.setBadgeBackgroundColor({ color: '#b45309' });
  await browser.action.setBadgeText({ text: queue.length ? String(queue.length) : '' });
}

async function flashBadge(text: string) {
  await browser.action.setBadgeBackgroundColor({ color: '#15803d' });
  await browser.action.setBadgeText({ text });
  setTimeout(() => void refreshBadge(), 4000);
}

async function signInWithGoogle() {
  const redirectTo = browser.identity.getRedirectURL();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo, skipBrowserRedirect: true },
  });
  if (error || !data.url) throw error ?? new Error('No sign-in URL');
  const result = await browser.identity.launchWebAuthFlow({ url: data.url, interactive: true });
  if (!result) throw new Error('Sign-in was cancelled');
  const params = new URL(result).searchParams;
  const code = params.get('code');
  if (!code) throw new Error(params.get('error_description') ?? 'Sign-in failed');
  const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
  if (exchangeError) throw exchangeError;
  return { ok: true };
}
