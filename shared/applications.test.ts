// Run: node --test shared/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  effectiveStatus,
  parseJobTitle,
  parsePostingUrl,
  sortByPriority,
  urlPostingKey,
  type Application,
  type Status,
} from './applications.ts';

const NOW = new Date('2026-10-15T12:00:00Z').getTime();
const daysAgo = (n: number) => new Date(NOW - n * 86400000).toISOString();
const app = (id: string, status: Status, applied: number, updated = applied): Application => ({
  id, user_id: 'u', company: id, role: null, url: null, posting_key: id, source: 'manual',
  status, applied_at: daysAgo(applied), status_updated_at: daysAgo(updated), notes: null, created_at: daysAgo(applied),
});

test('auto-ghost after 30 days at applied only', () => {
  assert.equal(effectiveStatus(app('a', 'applied', 31), NOW), 'ghosted');
  assert.equal(effectiveStatus(app('a', 'applied', 29), NOW), 'applied');
  assert.equal(effectiveStatus(app('a', 'applied', 40, 2), NOW), 'applied'); // "still alive" reset
  assert.equal(effectiveStatus(app('a', 'oa', 60), NOW), 'oa');
});

test('priority sort: offer, interview, OA, applied, ghosted, rejected; newest first', () => {
  const sorted = sortByPriority(
    [
      app('rej', 'rejected', 1),
      app('old-applied', 'applied', 20),
      app('ghost', 'applied', 45),
      app('new-applied', 'applied', 2),
      app('oa', 'oa', 10),
      app('offer', 'offer', 50),
      app('int', 'interview', 30),
    ],
    NOW,
  ).map((a) => a.id);
  assert.deepEqual(sorted, ['offer', 'int', 'oa', 'new-applied', 'old-applied', 'ghost', 'rej']);
});

test('Greenhouse URLs: hosted, confirmation, embed, embed confirmation', () => {
  const key = 'greenhouse:anthropic:4461450008';
  for (const u of [
    'https://job-boards.greenhouse.io/anthropic/jobs/4461450008',
    'https://job-boards.greenhouse.io/anthropic/jobs/4461450008/confirmation',
    'https://boards.greenhouse.io/anthropic/jobs/4461450008?gh_src=abc',
    'https://job-boards.greenhouse.io/embed/job_app?for=anthropic&token=4461450008',
    'https://job-boards.greenhouse.io/embed/job_app/confirmation?for=anthropic&token=4461450008',
  ]) assert.equal(parsePostingUrl(u)?.key, key, u);
  assert.equal(parsePostingUrl('https://job-boards.greenhouse.io/anthropic'), null);
});

test('Ashby URLs', () => {
  const id = '34413f8d-26bf-4bbc-8ade-eb309a0e2245';
  const ref = parsePostingUrl(`https://jobs.ashbyhq.com/ramp/${id}/application`);
  assert.equal(ref?.key, `ashby:ramp:${id}`);
  assert.equal(ref?.canonicalUrl, `https://jobs.ashbyhq.com/ramp/${id}`);
  assert.equal(parsePostingUrl('https://jobs.ashbyhq.com/ramp'), null);
});

test('job titles from real pages', () => {
  assert.deepEqual(parseJobTitle('Job Application for Account Executive, AI Native at Anthropic'), {
    role: 'Account Executive, AI Native', company: 'Anthropic',
  });
  assert.deepEqual(parseJobTitle(' Security Engineer, Cloud @ Ramp'), { role: 'Security Engineer, Cloud', company: 'Ramp' });
  assert.deepEqual(parseJobTitle('Stripe Careers | Abuse Investigator'), { role: 'Abuse Investigator', company: 'Stripe' });
});

test('URL keys drop tracking params but keep job ids', () => {
  assert.equal(
    urlPostingKey('https://www.stripe.com/jobs/search?gh_jid=8172510&utm_source=x'),
    urlPostingKey('https://stripe.com/jobs/search/?gh_jid=8172510'),
  );
  assert.notEqual(urlPostingKey('https://a.com/j?gh_jid=1'), urlPostingKey('https://a.com/j?gh_jid=2'));
});
