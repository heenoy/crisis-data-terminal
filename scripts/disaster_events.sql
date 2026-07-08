-- disaster_events table for Crisis Data Terminal
-- Run in Supabase SQL Editor after app_users exists

create table if not exists disaster_events (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  disaster_type text not null,
  country text not null,
  region text,
  event_date date not null,
  severity text not null,
  casualties integer default 0,
  affected_population integer default 0,
  economic_loss numeric(18, 2),
  description text,
  source_name text,
  source_url text,
  status text not null default 'active',
  created_by uuid references app_users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists disaster_events_event_date_idx on disaster_events (event_date desc);
create index if not exists disaster_events_disaster_type_idx on disaster_events (disaster_type);
create index if not exists disaster_events_country_idx on disaster_events (country);
create index if not exists disaster_events_severity_idx on disaster_events (severity);

-- Course demo: allow anon access (same pattern as app_users login)
alter table disaster_events enable row level security;

create policy "anon can read disaster_events"
  on disaster_events for select to anon using (true);

create policy "anon can insert disaster_events"
  on disaster_events for insert to anon with check (true);

create policy "anon can update disaster_events"
  on disaster_events for update to anon using (true) with check (true);

create policy "anon can delete disaster_events"
  on disaster_events for delete to anon using (true);
