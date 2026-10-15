-- Primora v2 (2026-10-15): the app is an application tracker with one user table.
-- The v1 tables (companies, postings, openings, predictions, targets, applications,
-- alerts) are left in place and unused by v2; drop them by hand if you want them gone.

create table public.job_applications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  company text not null,
  role text,
  url text,
  -- Stable identity of the posting, for the duplicate guard:
  -- 'greenhouse:<board>:<job id>', 'ashby:<org>:<job id>', or a normalized URL.
  posting_key text not null,
  source text not null default 'manual' check (source in ('greenhouse', 'ashby', 'manual')),
  status text not null default 'applied'
    check (status in ('applied', 'oa', 'interview', 'offer', 'rejected', 'ghosted')),
  applied_at timestamptz not null default now(),
  status_updated_at timestamptz not null default now(),
  notes text,
  created_at timestamptz not null default now(),
  unique (user_id, posting_key)
);

create index job_applications_user_idx on public.job_applications (user_id, applied_at desc);

-- Changing the status restarts the ghost clock, whichever client made the change.
create function public.touch_status_updated_at() returns trigger
language plpgsql as $$
begin
  if new.status is distinct from old.status then
    new.status_updated_at := now();
  end if;
  return new;
end;
$$;

create trigger job_applications_touch_status
  before update on public.job_applications
  for each row execute function public.touch_status_updated_at();

alter table public.job_applications enable row level security;

create policy "own job applications" on public.job_applications
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());
