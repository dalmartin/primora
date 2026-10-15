import { useCallback, useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import { QUEUE_KEY } from '@/lib/messages';
import {
  STATUSES,
  STATUS_LABEL,
  TABLE,
  companyFromHost,
  effectiveStatus,
  isAutoGhosted,
  parseJobTitle,
  parsePostingUrl,
  sortByPriority,
  urlPostingKey,
  type Application,
  type Status,
} from '../../../shared/applications';

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  if (session === undefined) return <div className="popup muted">Loading…</div>;
  return (
    <div className="popup">
      <header className="popup-header">
        <strong className="brand">Primora</strong>
        {session && (
          <span className="who">
            <span className="muted">{session.user.email}</span>
            <button className="btn btn-ghost small" onClick={() => supabase.auth.signOut()}>
              Sign out
            </button>
          </span>
        )}
      </header>
      {session ? <SignedIn session={session} /> : <SignIn />}
    </div>
  );
}

/** The dashboard is an extension page (dashboard.html), opened in a full tab. */
function openDashboard(e: React.MouseEvent) {
  e.preventDefault();
  void browser.tabs.create({ url: browser.runtime.getURL('/dashboard.html') });
  window.close();
}

function SignIn() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);

  const run = async (mode: 'in' | 'up') => {
    setBusy(true);
    setMsg(null);
    const { data, error } =
      mode === 'in'
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (error) setMsg({ text: error.message, error: true });
    else if (mode === 'up' && !data.session) setMsg({ text: 'Check your email to confirm, then sign in.' });
  };

  const google = async () => {
    setMsg({ text: 'Opening Google sign-in…' });
    const res = (await browser.runtime.sendMessage({ type: 'sign-in-google' })) as { ok?: boolean; error?: string };
    if (res?.error) setMsg({ text: res.error, error: true });
  };

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        void run('in');
      }}
    >
      <p className="muted">Sign in to start logging applications.</p>
      <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={6}
      />
      <div className="row">
        <button className="btn btn-primary grow" disabled={busy}>
          Sign in
        </button>
        <button type="button" className="btn grow" disabled={busy} onClick={() => run('up')}>
          Create account
        </button>
      </div>
      <button type="button" className="btn" onClick={google}>
        Continue with Google
      </button>
      {msg && <p className={msg.error ? 'error' : 'muted'}>{msg.text}</p>}
    </form>
  );
}

interface TabInfo {
  url: string;
  title: string;
}

function SignedIn({ session }: { session: Session }) {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [tab, setTab] = useState<TabInfo | null>(null);
  const [queued, setQueued] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const { data, error } = await supabase.from(TABLE).select('*');
    if (error) setError(error.message);
    else setApps(data as Application[]);
  }, []);

  useEffect(() => {
    void load();
    browser.tabs.query({ active: true, currentWindow: true }).then(([t]) => {
      if (t?.url?.startsWith('http')) setTab({ url: t.url, title: t.title ?? '' });
    });
    browser.runtime.sendMessage({ type: 'flush-queue' }).then((r: { saved: number; left: number }) => {
      setQueued(r?.left ?? 0);
      if (r?.saved) void load();
    });
  }, [load]);

  const setStatus = async (id: string, status: Status) => {
    // Always restart the clock, so picking "Applied" on an auto-ghosted row revives it.
    const now = new Date().toISOString();
    setApps((prev) => prev?.map((a) => (a.id === id ? { ...a, status, status_updated_at: now } : a)) ?? null);
    const { error } = await supabase.from(TABLE).update({ status, status_updated_at: now }).eq('id', id);
    if (error) setError(error.message);
  };

  const stillAlive = async (id: string) => {
    const now = new Date().toISOString();
    setApps((prev) => prev?.map((a) => (a.id === id ? { ...a, status_updated_at: now } : a)) ?? null);
    const { error } = await supabase.from(TABLE).update({ status_updated_at: now }).eq('id', id);
    if (error) setError(error.message);
  };

  const ref = tab ? parsePostingUrl(tab.url) : null;
  const key = tab ? (ref?.key ?? urlPostingKey(tab.url)) : null;
  const existing = apps?.find((a) => a.posting_key === key);
  const top = apps ? sortByPriority(apps).slice(0, 6) : [];

  return (
    <div className="stack">
      {error && <p className="error">{error}</p>}
      {queued > 0 && <p className="muted">{queued} logged application(s) waiting to sync.</p>}

      {tab && (
        <section className="card">
          <h2>This page</h2>
          {existing ? (
            <AppRow app={existing} onStatus={setStatus} onAlive={stillAlive} />
          ) : (
            <ManualLog tab={tab} userId={session.user.id} postingKey={key!} canonicalUrl={ref?.canonicalUrl} onSaved={load} />
          )}
        </section>
      )}

      <section className="card">
        <div className="row spread">
          <h2>Top of your list</h2>
          <a className="link" href="#" onClick={openDashboard}>
            Open dashboard →
          </a>
        </div>
        {apps === null ? (
          <p className="muted">Loading…</p>
        ) : top.length === 0 ? (
          <p className="muted">Nothing logged yet. Submit an application on Greenhouse or Ashby, or use "I applied" above.</p>
        ) : (
          <ul className="list">
            {top.map((a) => (
              <li key={a.id}>
                <AppRow app={a} onStatus={setStatus} onAlive={stillAlive} />
              </li>
            ))}
          </ul>
        )}
        {apps && apps.length > top.length && <p className="muted small">+ {apps.length - top.length} more on the dashboard</p>}
      </section>
    </div>
  );
}

function ManualLog(props: {
  tab: TabInfo;
  userId: string;
  postingKey: string;
  canonicalUrl?: string;
  onSaved: () => void;
}) {
  const guess = parseJobTitle(props.tab.title);
  const [company, setCompany] = useState(guess.company ?? companyFromHost(props.tab.url) ?? '');
  const [role, setRole] = useState(guess.role ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    const { error } = await supabase.from(TABLE).upsert(
      {
        user_id: props.userId,
        company: company.trim(),
        role: role.trim() || null,
        url: props.canonicalUrl ?? props.tab.url,
        posting_key: props.postingKey,
        source: 'manual',
      },
      { onConflict: 'user_id,posting_key', ignoreDuplicates: true },
    );
    setBusy(false);
    if (error) setError(error.message);
    else props.onSaved();
  };

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <input placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} required />
      <input placeholder="Role" value={role} onChange={(e) => setRole(e.target.value)} />
      <button className="btn btn-primary" disabled={busy || !company.trim()}>
        I applied
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

function AppRow({
  app,
  onStatus,
  onAlive,
}: {
  app: Application;
  onStatus: (id: string, s: Status) => void;
  onAlive: (id: string) => void;
}) {
  const shown = effectiveStatus(app);
  return (
    <div className="app-row">
      <div className="app-main">
        <div className="app-company">{app.company}</div>
        <div className="muted small ellipsis">{app.role ?? 'Role not set'}</div>
      </div>
      <div className="app-side">
        <select
          className={`status-select st-${shown}`}
          value={shown}
          onChange={(e) => onStatus(app.id, e.target.value as Status)}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
        {isAutoGhosted(app) && (
          <button className="btn btn-ghost small" onClick={() => onAlive(app.id)} title="Reset the 30-day clock">
            Still alive
          </button>
        )}
      </div>
    </div>
  );
}
