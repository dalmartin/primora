import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'
import {
  GHOST_AFTER_DAYS,
  PRIORITY,
  STATUSES,
  STATUS_LABEL,
  TABLE,
  daysSince,
  effectiveStatus,
  groupByPriority,
  isAutoGhosted,
  parsePostingUrl,
  urlPostingKey,
  type Application,
  type Status,
} from '../../shared/applications'
import { THEMES, applyTheme, savedTheme, type ThemeName } from '../../shared/theme'

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  if (session === undefined) return <div className="page muted">Loading…</div>
  return session ? <Dashboard session={session} /> : <SignIn />
}

function SignIn() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null)

  const run = async (mode: 'in' | 'up') => {
    setBusy(true)
    setMsg(null)
    const { data, error } =
      mode === 'in'
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password })
    setBusy(false)
    if (error) setMsg({ text: error.message, error: true })
    else if (mode === 'up' && !data.session) setMsg({ text: 'Check your email to confirm, then sign in.' })
  }

  const google = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) setMsg({ text: error.message, error: true })
  }

  return (
    <div className="signin-wrap">
      <form
        className="signin card"
        onSubmit={(e) => {
          e.preventDefault()
          void run('in')
        }}
      >
        <h1>Primora</h1>
        <p className="muted">Every application you submit, logged. The promising ones on top.</p>
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
    </div>
  )
}

function Dashboard({ session }: { session: Session }) {
  const [apps, setApps] = useState<Application[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Status | 'all'>('all')
  const [adding, setAdding] = useState(false)

  const load = useCallback(async () => {
    const { data, error } = await supabase.from(TABLE).select('*')
    if (error) setError(error.message)
    else {
      setError(null)
      setApps(data as Application[])
    }
  }, [])

  useEffect(() => {
    void load()
    // Pick up applications the extension logged while this tab was in the background.
    const onFocus = () => void load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [load])

  const patch = async (id: string, changes: Partial<Application>) => {
    setApps((prev) => prev?.map((a) => (a.id === id ? { ...a, ...changes } : a)) ?? null)
    const { error } = await supabase.from(TABLE).update(changes).eq('id', id)
    if (error) {
      setError(error.message)
      void load()
    }
  }

  // Always restart the clock, so picking "Applied" on an auto-ghosted row revives it.
  const setStatus = (id: string, status: Status) =>
    patch(id, { status, status_updated_at: new Date().toISOString() })

  const remove = async (id: string) => {
    setApps((prev) => prev?.filter((a) => a.id !== id) ?? null)
    const { error } = await supabase.from(TABLE).delete().eq('id', id)
    if (error) {
      setError(error.message)
      void load()
    }
  }

  const counts = useMemo(() => {
    const c = Object.fromEntries(STATUSES.map((s) => [s, 0])) as Record<Status, number>
    for (const a of apps ?? []) c[effectiveStatus(a)]++
    return c
  }, [apps])

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    const visible = (apps ?? []).filter(
      (a) =>
        (filter === 'all' || effectiveStatus(a) === filter) &&
        (!q || a.company.toLowerCase().includes(q) || (a.role ?? '').toLowerCase().includes(q)),
    )
    return groupByPriority(visible)
  }, [apps, query, filter])

  return (
    <div className="page">
      <header className="topbar">
        <h1>Primora</h1>
        <div className="row">
          <ThemePicker />
          <span className="muted small">{session.user.email}</span>
          <button className="btn btn-ghost" onClick={() => supabase.auth.signOut()}>
            Sign out
          </button>
        </div>
      </header>

      <div className="summary">
        <button className={`chip ${filter === 'all' ? 'chip-on' : ''}`} onClick={() => setFilter('all')}>
          All <b>{apps?.length ?? 0}</b>
        </button>
        {PRIORITY.map((s) => (
          <button
            key={s}
            className={`chip st-${s} ${filter === s ? 'chip-on' : ''}`}
            onClick={() => setFilter(filter === s ? 'all' : s)}
          >
            {STATUS_LABEL[s]} <b>{counts[s]}</b>
          </button>
        ))}
      </div>

      <div className="toolbar">
        <input
          className="search"
          placeholder="Search company or role"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn btn-primary" onClick={() => setAdding(true)} disabled={adding}>
          + Add application
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {adding && (
        <EditForm
          title="Add an application"
          onCancel={() => setAdding(false)}
          onSave={async (v) => {
            const ref = v.url ? parsePostingUrl(v.url) : null
            const { error } = await supabase.from(TABLE).insert({
              user_id: session.user.id,
              company: v.company,
              role: v.role,
              url: v.url,
              notes: v.notes,
              applied_at: v.applied_at,
              // The ghost clock starts when you applied, not when you logged it.
              status_updated_at: v.applied_at,
              status: v.status,
              posting_key: ref?.key ?? (v.url ? urlPostingKey(v.url) : `manual:${crypto.randomUUID()}`),
              source: 'manual',
            })
            if (error) return error.code === '23505' ? 'You already logged this posting.' : error.message
            setAdding(false)
            void load()
            return null
          }}
        />
      )}

      {apps === null ? (
        <p className="muted">Loading…</p>
      ) : apps.length === 0 ? (
        <EmptyState />
      ) : groups.length === 0 ? (
        <p className="muted">Nothing matches.</p>
      ) : (
        groups.map((g) => (
          <section key={g.status} className="group">
            <h2>
              <span className={`status-pill st-${g.status}`}>{STATUS_LABEL[g.status]}</span>
              <span className="muted">{g.apps.length}</span>
            </h2>
            <ul className="rows">
              {g.apps.map((a) => (
                <Row key={a.id} app={a} onStatus={setStatus} onPatch={patch} onDelete={remove} />
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}

function ThemePicker() {
  const [theme, setTheme] = useState<ThemeName>(savedTheme)
  return (
    <select
      className="theme-select small"
      value={theme}
      aria-label="Theme"
      onChange={(e) => {
        const t = e.target.value as ThemeName
        applyTheme(t, true)
        setTheme(t)
      }}
    >
      {(Object.keys(THEMES) as ThemeName[]).map((t) => (
        <option key={t} value={t}>
          {THEMES[t].label}
        </option>
      ))}
    </select>
  )
}

function EmptyState() {
  return (
    <div className="card empty">
      <h2>No applications yet</h2>
      <p className="muted">
        With the extension installed, submit an application on a Greenhouse or Ashby page and it shows up here on
        its own. Anywhere else, click the Primora icon and hit "I applied". You can also add one by hand above.
      </p>
    </div>
  )
}

const dateFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' })

function Row({
  app,
  onStatus,
  onPatch,
  onDelete,
}: {
  app: Application
  onStatus: (id: string, s: Status) => void
  onPatch: (id: string, c: Partial<Application>) => Promise<void>
  onDelete: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const shown = effectiveStatus(app)
  const days = daysSince(app.applied_at)

  if (editing) {
    return (
      <li>
        <EditForm
          title="Edit application"
          initial={app}
          onCancel={() => setEditing(false)}
          onSave={async (v) => {
            // Status changed: restart the clock. Untouched since applying: the clock follows the new date.
            const clock =
              v.status !== app.status
                ? { status_updated_at: new Date().toISOString() }
                : app.status_updated_at === app.applied_at
                  ? { status_updated_at: v.applied_at }
                  : {}
            await onPatch(app.id, { ...v, ...clock })
            setEditing(false)
            return null
          }}
        />
      </li>
    )
  }

  return (
    <li className="row-item">
      <div className="row-main">
        <div className="company">{app.company}</div>
        <div className="role">
          {app.url ? (
            <a href={app.url} target="_blank" rel="noreferrer">
              {app.role || 'Posting'}
            </a>
          ) : (
            app.role || <span className="muted">Role not set</span>
          )}
        </div>
        {app.notes && <div className="notes muted small">{app.notes}</div>}
      </div>
      <div className="row-meta muted small">
        <span title={new Date(app.applied_at).toLocaleString()}>
          {dateFmt.format(new Date(app.applied_at))} · {days === 0 ? 'today' : `${days}d ago`}
        </span>
        <span className="source">{app.source === 'manual' ? 'manual' : app.source}</span>
      </div>
      <div className="row-actions">
        <select
          className={`status-select st-${shown}`}
          value={shown}
          onChange={(e) => onStatus(app.id, e.target.value as Status)}
          aria-label="Status"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
        {isAutoGhosted(app) && (
          <span className="ghost-note small">
            No update in {daysSince(app.status_updated_at)} days{' '}
            <button
              className="btn btn-ghost small"
              title={`Reset the ${GHOST_AFTER_DAYS}-day clock`}
              onClick={() => onPatch(app.id, { status_updated_at: new Date().toISOString() })}
            >
              Still alive
            </button>
          </span>
        )}
        {confirmDelete ? (
          <span className="row">
            <button className="btn btn-danger small" onClick={() => onDelete(app.id)}>
              Delete
            </button>
            <button className="btn btn-ghost small" onClick={() => setConfirmDelete(false)}>
              Keep
            </button>
          </span>
        ) : (
          <span className="row">
            <button className="btn btn-ghost small" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button className="btn btn-ghost small" onClick={() => setConfirmDelete(true)}>
              Delete
            </button>
          </span>
        )}
      </div>
    </li>
  )
}

interface FormValues {
  company: string
  role: string | null
  url: string | null
  notes: string | null
  applied_at: string
  status: Status
}

function toDateInput(iso: string) {
  const d = new Date(iso)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function EditForm({
  title,
  initial,
  onSave,
  onCancel,
}: {
  title: string
  initial?: Application
  onSave: (v: FormValues) => Promise<string | null>
  onCancel: () => void
}) {
  const [company, setCompany] = useState(initial?.company ?? '')
  const [role, setRole] = useState(initial?.role ?? '')
  const [url, setUrl] = useState(initial?.url ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [date, setDate] = useState(toDateInput(initial?.applied_at ?? new Date().toISOString()))
  const [status, setStatus] = useState<Status>(initial?.status ?? 'applied')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  return (
    <form
      className="card edit-form"
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        // Keep the original time of day when only the date changes.
        const base = initial ? new Date(initial.applied_at) : new Date()
        const [y, m, d] = date.split('-').map(Number)
        base.setFullYear(y, m - 1, d)
        const err = await onSave({
          company: company.trim(),
          role: role.trim() || null,
          url: url.trim() || null,
          notes: notes.trim() || null,
          applied_at: base.toISOString(),
          status,
        })
        setBusy(false)
        setError(err)
      }}
    >
      <h3>{title}</h3>
      <div className="form-grid">
        <label>
          Company
          <input value={company} onChange={(e) => setCompany(e.target.value)} required autoFocus />
        </label>
        <label>
          Role
          <input value={role} onChange={(e) => setRole(e.target.value)} />
        </label>
        <label className="wide">
          Posting link
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
        </label>
        <label>
          Applied on
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value as Status)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        <label className="wide">
          Notes
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="row end">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={busy || !company.trim()}>
          Save
        </button>
      </div>
    </form>
  )
}
