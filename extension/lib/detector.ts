import type { LogApplicationMessage, LogResult } from './messages';
import {
  companyFromHost,
  parseJobTitle,
  parsePostingUrl,
  urlPostingKey,
  type PostingRef,
} from '../../shared/applications';

/**
 * Per-site rules for spotting a finished application. Checked against real pages
 * (2026-10-15):
 * - Greenhouse redirects to `/<board>/jobs/<id>/confirmation` (hosted) or
 *   `/embed/job_app/confirmation?for=&token=` (iframe on a company site).
 * - Ashby stays on `/application` and renders "Your application was successfully
 *   submitted..." (orgs can customize the text).
 */
export interface SiteRules {
  ats: 'greenhouse' | 'ashby';
  /** Strong signal: this URL only appears after a successful submit. */
  isConfirmationUrl?: (url: URL) => boolean;
  /** Strong signal: text only shown after a successful submit, even without seeing the click. */
  strongSuccessText?: RegExp;
  /** Weaker signal: counts only shortly after we saw the user hit submit. */
  successTextAfterSubmit: RegExp;
}

interface Armed {
  ref: PostingRef | null;
  title: string;
  href: string;
  at: number;
}

const ARMED_KEY = 'primora:armed';
const ARMED_WINDOW_MS = 10 * 60 * 1000;

export function runDetector(rules: SiteRules) {
  const reported = new Set<string>();

  const readArmed = (): Armed | null => {
    try {
      const a = JSON.parse(sessionStorage.getItem(ARMED_KEY) ?? 'null') as Armed | null;
      return a && Date.now() - a.at < ARMED_WINDOW_MS ? a : null;
    } catch {
      return null;
    }
  };

  const arm = () => {
    const armed: Armed = { ref: parsePostingUrl(location.href), title: document.title, href: location.href, at: Date.now() };
    try {
      // sessionStorage survives the same-origin redirect to the confirmation page.
      sessionStorage.setItem(ARMED_KEY, JSON.stringify(armed));
    } catch {
      // Storage blocked (some iframes): the URL signal still works.
    }
    memoryArmed = armed;
  };
  let memoryArmed: Armed | null = null;

  // Capture phase so we see it before the page's own handlers.
  document.addEventListener('submit', arm, true);
  document.addEventListener(
    'click',
    (e) => {
      const btn = (e.target as Element | null)?.closest?.('button, input[type="submit"]');
      if (!btn) return;
      const label = (btn.textContent || (btn as HTMLInputElement).value || '').trim();
      if ((btn as HTMLButtonElement).type === 'submit' || /submit/i.test(label)) arm();
    },
    true,
  );

  const check = () => {
    const url = new URL(location.href);
    const armed = readArmed() ?? (memoryArmed && Date.now() - memoryArmed.at < ARMED_WINDOW_MS ? memoryArmed : null);
    const ref = parsePostingUrl(url.href) ?? armed?.ref ?? null;

    let success = false;
    if (rules.isConfirmationUrl?.(url)) success = true;
    else if (rules.strongSuccessText || armed) {
      const text = document.body?.innerText ?? '';
      if (rules.strongSuccessText?.test(text)) success = true;
      else if (armed && rules.successTextAfterSubmit.test(text)) success = true;
    }
    if (!success) return;

    const key = ref?.key ?? url.href;
    if (reported.has(key)) return;
    reported.add(key);
    try {
      sessionStorage.removeItem(ARMED_KEY);
    } catch {
      // ignore
    }
    memoryArmed = null;
    void report(ref, armed);
  };

  let pending: number | undefined;
  const schedule = () => {
    clearTimeout(pending);
    pending = window.setTimeout(check, 300);
  };
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  // SPA navigations don't fire events content scripts can hear; poll the URL.
  let lastHref = location.href;
  setInterval(() => {
    if (location.href !== lastHref) {
      lastHref = location.href;
      schedule();
    }
  }, 500);
  schedule();

  async function report(ref: PostingRef | null, armed: Armed | null) {
    // Confirmation pages are titled "Thank you for applying"; never mistake that for a role.
    const title = armed?.title || (/thank you|confirmation|submitted/i.test(document.title) ? '' : document.title);
    const parsed = parseJobTitle(title);
    const pageUrl = armed?.href ?? location.href;
    const company = parsed.company || (ref ? titleCase(ref.org) : companyFromHost(pageUrl)) || 'Unknown company';
    const msg: LogApplicationMessage = {
      type: 'log-application',
      ref,
      app: {
        company,
        role: parsed.role,
        url: ref?.canonicalUrl ?? pageUrl,
        posting_key: ref?.key ?? urlPostingKey(pageUrl),
        source: rules.ats,
      },
    };
    try {
      const result = (await browser.runtime.sendMessage(msg)) as LogResult;
      showToast(result);
    } catch (e) {
      console.error('Primora: could not reach the extension', e);
    }
  }
}

function titleCase(slug: string): string {
  return slug.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function showToast(result: LogResult) {
  const what = result.role ? `${result.role} at ${result.company}` : result.company;
  const text = result.ok
    ? result.duplicate
      ? `Primora: already logged ${what}`
      : `Primora logged: ${what}`
    : result.reason === 'signed-out'
      ? `Primora saved ${what} for later. Sign in from the toolbar icon to sync it.`
      : `Primora couldn't reach the server; ${what} is queued and will retry.`;

  const host = document.createElement('div');
  host.dataset.primoraToast = '';
  const shadow = host.attachShadow({ mode: 'closed' });
  // Built with DOM calls rather than innerHTML (Firefox add-on review flags innerHTML).
  const style = document.createElement('style');
  style.textContent = `
    .toast { position: fixed; z-index: 2147483647; right: 16px; bottom: 16px; max-width: 360px;
      padding: 12px 14px; border-radius: 4px; font: 14px/1.4 system-ui, sans-serif;
      color: #2f2737; background: ${result.ok ? '#f5bccd' : '#fbe2d3'};
      border: 1px solid #4a3f55; box-shadow: 3px 3px 0 #4a3f55;
      animation: in .2s ease-out; }
    @keyframes in { from { opacity: 0; transform: translateY(8px); } }`;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.setAttribute('role', 'status');
  toast.textContent = text;
  shadow.append(style, toast);
  document.documentElement.appendChild(host);
  setTimeout(() => host.remove(), 6000);
}
