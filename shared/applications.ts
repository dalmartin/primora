// Shared by the extension and the dashboard: types, the priority sort, the
// auto-ghost rule, and posting keys for the duplicate guard. No dependencies.

export const TABLE = 'job_applications';

export type Status = 'applied' | 'oa' | 'interview' | 'offer' | 'rejected' | 'ghosted';
export type Source = 'greenhouse' | 'ashby' | 'manual';

export interface Application {
  id: string;
  user_id: string;
  company: string;
  role: string | null;
  url: string | null;
  posting_key: string;
  source: Source;
  status: Status;
  applied_at: string;
  status_updated_at: string;
  notes: string | null;
  created_at: string;
}

export interface NewApplication {
  company: string;
  role?: string | null;
  url?: string | null;
  posting_key: string;
  source: Source;
  applied_at?: string;
  notes?: string | null;
}

/** Statuses a user can pick. "ghosted" doubles as the confirmed "likely ghosted". */
export const STATUSES: Status[] = ['applied', 'oa', 'interview', 'offer', 'rejected', 'ghosted'];

export const STATUS_LABEL: Record<Status, string> = {
  applied: 'Applied',
  oa: 'OA',
  interview: 'Interview',
  offer: 'Offer',
  rejected: 'Rejected',
  ghosted: 'Likely ghosted',
};

/** An application still at "applied" with no change for this long shows as likely ghosted. */
export const GHOST_AFTER_DAYS = 30;

const DAY_MS = 24 * 60 * 60 * 1000;

export function daysSince(iso: string, now = Date.now()): number {
  return Math.floor((now - new Date(iso).getTime()) / DAY_MS);
}

/** True when the app treats it as ghosted but the user hasn't set that status themselves. */
export function isAutoGhosted(a: Pick<Application, 'status' | 'status_updated_at'>, now = Date.now()): boolean {
  return a.status === 'applied' && daysSince(a.status_updated_at, now) >= GHOST_AFTER_DAYS;
}

/** The status shown and sorted on: applies the auto-ghost rule. */
export function effectiveStatus(a: Pick<Application, 'status' | 'status_updated_at'>, now = Date.now()): Status {
  return isAutoGhosted(a, now) ? 'ghosted' : a.status;
}

/** Most promising first. */
export const PRIORITY: Status[] = ['offer', 'interview', 'oa', 'applied', 'ghosted', 'rejected'];

export function sortByPriority<T extends Application>(apps: T[], now = Date.now()): T[] {
  const rank = (a: T) => PRIORITY.indexOf(effectiveStatus(a, now));
  return [...apps].sort(
    (a, b) => rank(a) - rank(b) || new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime(),
  );
}

export function groupByPriority<T extends Application>(apps: T[], now = Date.now()): { status: Status; apps: T[] }[] {
  return PRIORITY.map((status) => ({
    status,
    apps: sortByPriority(apps.filter((a) => effectiveStatus(a, now) === status), now),
  })).filter((g) => g.apps.length > 0);
}

const TRACKING_PARAMS = /^(utm_|gh_src$|ref$|source$|src$|lever-source|ashby_source|trk|fbclid$|gclid$)/i;

/** Key for a manually logged URL: origin + path + meaningful query params (job ids survive). */
export function urlPostingKey(rawUrl: string): string {
  try {
    const u = new URL(rawUrl);
    const params = [...u.searchParams.entries()]
      .filter(([k]) => !TRACKING_PARAMS.test(k))
      .sort(([a], [b]) => a.localeCompare(b));
    const query = params.length ? '?' + new URLSearchParams(params).toString() : '';
    return `url:${u.hostname.replace(/^www\./, '')}${u.pathname.replace(/\/+$/, '')}${query}`.toLowerCase();
  } catch {
    return `url:${rawUrl.trim().toLowerCase()}`;
  }
}

export function greenhouseKey(board: string, jobId: string): string {
  return `greenhouse:${board.toLowerCase()}:${jobId}`;
}

export function ashbyKey(org: string, jobId: string): string {
  return `ashby:${org.toLowerCase()}:${jobId.toLowerCase()}`;
}

export interface PostingRef {
  ats: 'greenhouse' | 'ashby';
  org: string;
  jobId: string;
  key: string;
  canonicalUrl: string;
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/**
 * Recognize a Greenhouse or Ashby posting from a URL (hosted board, embed iframe,
 * or confirmation page). Returns null for anything else.
 */
export function parsePostingUrl(rawUrl: string): PostingRef | null {
  let u: URL;
  try {
    u = new URL(rawUrl);
  } catch {
    return null;
  }
  const host = u.hostname;
  const parts = u.pathname.split('/').filter(Boolean);

  if (/(^|\.)greenhouse\.io$/.test(host)) {
    let board: string | null = null;
    let jobId: string | null = null;
    if (parts[0] === 'embed') {
      board = u.searchParams.get('for');
      jobId = u.searchParams.get('token');
    } else if (parts[1] === 'jobs' && /^\d+$/.test(parts[2] ?? '')) {
      board = parts[0] ?? null;
      jobId = parts[2] ?? null;
    }
    if (!board || !jobId) return null;
    return {
      ats: 'greenhouse',
      org: board,
      jobId,
      key: greenhouseKey(board, jobId),
      canonicalUrl: `https://job-boards.greenhouse.io/${board}/jobs/${jobId}`,
    };
  }

  if (host === 'jobs.ashbyhq.com' && parts[0]) {
    const org = parts[0];
    const jobId = parts.slice(1).find((p) => UUID.test(p)) ?? u.searchParams.get('ashby_jid');
    if (!jobId) return null;
    return {
      ats: 'ashby',
      org,
      jobId,
      key: ashbyKey(org, jobId),
      canonicalUrl: `https://jobs.ashbyhq.com/${org}/${jobId}`,
    };
  }

  return null;
}

/** Pull "Role" and "Company" out of a job page title, for prefilling. */
export function parseJobTitle(title: string): { role: string | null; company: string | null } {
  const t = title.replace(/\s+/g, ' ').trim();
  const pair = (re: RegExp): [string, string] | null => {
    const m = t.match(re);
    return m && m[1] && m[2] ? [m[1].trim(), m[2].trim()] : null;
  };
  let p = pair(/^Job Application for (.+) at (.+)$/i); // Greenhouse
  if (p) return { role: p[0], company: p[1] };
  p = pair(/^(.+?) @ (.+)$/); // Ashby
  if (p) return { role: p[0], company: p[1] };
  p = pair(/^(.+?) - (.+?) - (?:Lever|Workday|Careers)/i);
  if (p) return { role: p[1], company: p[0] };
  p = pair(/^(.+?) \| (.+)$/); // "Company Careers | Role" or "Role | Company"
  if (p) {
    const [a, b] = p;
    if (/careers|jobs/i.test(a)) return { role: b, company: a.replace(/\s*(careers|jobs)\s*/i, '').trim() || null };
    return { role: a, company: b.replace(/\s*(careers|jobs)\s*/i, '').trim() || null };
  }
  return { role: t || null, company: null };
}

/** Best guess at a company name from a hostname: "careers.stripe.com" -> "Stripe". */
export function companyFromHost(rawUrl: string): string | null {
  try {
    const host = new URL(rawUrl).hostname.replace(/^www\./, '');
    const generic = /^(jobs|careers|boards|job-boards|apply|myworkdayjobs|wd\d+|lever|greenhouse|ashbyhq|com|io|co|org|net|ai)$/;
    const word = host.split('.').find((p) => !generic.test(p));
    return word ? word.charAt(0).toUpperCase() + word.slice(1) : null;
  } catch {
    return null;
  }
}
