-- Primora initial schema (PRD section 7, tracker 0.3)

-- Shared reference data (written by the pipeline with the service role; readable by signed-in users)
create table public.companies (
  id bigint generated always as identity primary key,
  name text not null unique,
  tier text not null default 'none' check (tier in ('prestige', 'pipeline', 'none')),
  company_group text not null default 'other' check (company_group in ('big_tech', 'quant', 'bank', 'startup', 'other')),
  main_ats text,
  created_at timestamptz not null default now()
);

create table public.postings (
  id text primary key,                         -- Simplify listing id
  company_id bigint not null references public.companies (id),
  title text not null,
  category text,
  url text,
  cycle text not null,                         -- e.g. 'Summer 2027'
  first_seen timestamptz not null,
  closed_at timestamptz,
  active boolean not null default true
);
create index postings_company_cycle_idx on public.postings (company_id, cycle);

create table public.openings (
  company_id bigint not null references public.companies (id),
  cycle text not null,
  opened_on date,                              -- null while not yet opened
  censored boolean not null default false,     -- true = not opened as of computed_at
  computed_at timestamptz not null default now(),
  primary key (company_id, cycle)
);

create table public.predictions (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.companies (id),
  cycle text not null,
  model_version text not null,
  p10 date,
  p50 date,
  p90 date,
  prob_curve jsonb,                            -- [{date, p_opened_by}]
  passes_baseline boolean not null default false,
  generated_at timestamptz not null default now()
);
create index predictions_company_cycle_idx on public.predictions (company_id, cycle, generated_at desc);

-- Per-user data
create table public.targets (
  user_id uuid not null references auth.users (id) on delete cascade,
  company_id bigint not null references public.companies (id),
  created_at timestamptz not null default now(),
  primary key (user_id, company_id)
);

create table public.applications (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  company_id bigint references public.companies (id),
  posting_id text references public.postings (id),
  company_name text not null,                  -- as captured, even if unmatched
  role text,
  url text,
  applied_at timestamptz not null default now(),
  source text not null check (source in ('greenhouse', 'ashby', 'manual')),
  status text not null default 'applied' check (status in ('applied', 'oa', 'interview', 'rejected', 'offer')),
  status_updated_at timestamptz not null default now(),
  ghost_flag boolean not null default false,
  ghost_override boolean not null default false
);
create index applications_user_idx on public.applications (user_id, applied_at desc);

create table public.alerts (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  company_id bigint not null references public.companies (id),
  type text not null check (type in ('coming_soon', 'open_now')),
  cycle text not null,
  created_at timestamptz not null default now(),
  delivered_at timestamptz,
  unique (user_id, company_id, type, cycle)   -- dedupe
);

-- Row-level security
alter table public.companies enable row level security;
alter table public.postings enable row level security;
alter table public.openings enable row level security;
alter table public.predictions enable row level security;
alter table public.targets enable row level security;
alter table public.applications enable row level security;
alter table public.alerts enable row level security;

create policy "read companies" on public.companies for select to authenticated using (true);
create policy "read postings" on public.postings for select to authenticated using (true);
create policy "read openings" on public.openings for select to authenticated using (true);
create policy "read predictions" on public.predictions for select to authenticated using (true);

create policy "own targets" on public.targets for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own applications" on public.applications for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "read own alerts" on public.alerts for select to authenticated using (user_id = auth.uid());
create policy "mark own alerts delivered" on public.alerts for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
