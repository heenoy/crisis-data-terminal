-- Fourth Stage 4.2-A: Data API grants and RLS hardening.
-- Prepared against the read-only inspected 2026-08-26 schema.
-- Do not apply to the linked project until 4.2-B approval and backup.

-- ---------------------------------------------------------------------------
-- Legacy account table: isolate it without dropping data or the password column.
-- ---------------------------------------------------------------------------
alter table public.app_users enable row level security;

drop policy if exists "anon can insert app users" on public.app_users;
drop policy if exists "anon can read app users" on public.app_users;
drop policy if exists "anon can read app_users" on public.app_users;
drop policy if exists "anon can insert app_users" on public.app_users;

revoke all privileges on table public.app_users from anon, authenticated;

-- ---------------------------------------------------------------------------
-- Disaster archive: signed-in read; administrators write.
-- ---------------------------------------------------------------------------
alter table public.disaster_events enable row level security;

drop policy if exists "Anon can delete disaster events" on public.disaster_events;
drop policy if exists "Anon can insert disaster events" on public.disaster_events;
drop policy if exists "Anon can read disaster events" on public.disaster_events;
drop policy if exists "Anon can update disaster events" on public.disaster_events;
drop policy if exists "anon can delete disaster_events" on public.disaster_events;
drop policy if exists "anon can insert disaster_events" on public.disaster_events;
drop policy if exists "anon can read disaster_events" on public.disaster_events;
drop policy if exists "anon can update disaster_events" on public.disaster_events;
drop policy if exists "Authenticated users can delete own disaster events" on public.disaster_events;
drop policy if exists "Authenticated users can insert disaster events" on public.disaster_events;
drop policy if exists "Authenticated users can read disaster events" on public.disaster_events;
drop policy if exists "Authenticated users can update own disaster events" on public.disaster_events;

revoke all privileges on table public.disaster_events from anon, authenticated;
grant select, insert, update, delete on table public.disaster_events to authenticated;

create policy "authenticated can read disaster events"
  on public.disaster_events
  for select
  to authenticated
  using (true);

create policy "admins can insert disaster events"
  on public.disaster_events
  for insert
  to authenticated
  with check (
    coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin'
    and created_by_auth = (select auth.uid())
  );

create policy "admins can update disaster events"
  on public.disaster_events
  for update
  to authenticated
  using (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin')
  with check (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');

create policy "admins can delete disaster events"
  on public.disaster_events
  for delete
  to authenticated
  using (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');

-- ---------------------------------------------------------------------------
-- Related lookup/link tables: signed-in read; administrators mutate.
-- ---------------------------------------------------------------------------
alter table public.tags enable row level security;

drop policy if exists "Anon can insert tags" on public.tags;
drop policy if exists "Anon can read tags" on public.tags;
drop policy if exists "Authenticated users can insert tags" on public.tags;
drop policy if exists "Authenticated users can read tags" on public.tags;

revoke all privileges on table public.tags from anon, authenticated;
grant select, insert, update, delete on table public.tags to authenticated;

create policy "authenticated can read tags"
  on public.tags for select to authenticated using (true);
create policy "admins can insert tags"
  on public.tags for insert to authenticated
  with check (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');
create policy "admins can update tags"
  on public.tags for update to authenticated
  using (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin')
  with check (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');
create policy "admins can delete tags"
  on public.tags for delete to authenticated
  using (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');

alter table public.event_tags enable row level security;

drop policy if exists "Anon can delete event tags" on public.event_tags;
drop policy if exists "Anon can insert event tags" on public.event_tags;
drop policy if exists "Anon can read event tags" on public.event_tags;
drop policy if exists "Authenticated users can delete event tags" on public.event_tags;
drop policy if exists "Authenticated users can insert event tags" on public.event_tags;
drop policy if exists "Authenticated users can read event tags" on public.event_tags;

revoke all privileges on table public.event_tags from anon, authenticated;
grant select, insert, delete on table public.event_tags to authenticated;

create policy "authenticated can read event tags"
  on public.event_tags for select to authenticated using (true);
create policy "admins can insert event tags"
  on public.event_tags for insert to authenticated
  with check (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');
create policy "admins can delete event tags"
  on public.event_tags for delete to authenticated
  using (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');

-- Operation logs are not a public feed. Only administrators can read or append.
alter table public.operation_logs enable row level security;

drop policy if exists "Anon can insert operation logs" on public.operation_logs;
drop policy if exists "Anon can read operation logs" on public.operation_logs;
drop policy if exists "Authenticated users can insert operation logs" on public.operation_logs;
drop policy if exists "Authenticated users can read operation logs" on public.operation_logs;

revoke all privileges on table public.operation_logs from anon, authenticated;
grant select, insert on table public.operation_logs to authenticated;

create policy "admins can read operation logs"
  on public.operation_logs for select to authenticated
  using (coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin');
create policy "admins can insert operation logs"
  on public.operation_logs for insert to authenticated
  with check (
    coalesce((select auth.jwt() -> 'app_metadata' ->> 'role'), '') = 'admin'
    and operator_id = (select auth.uid())
  );

-- ---------------------------------------------------------------------------
-- Statistics views: run with caller privileges so disaster_events RLS applies.
-- ---------------------------------------------------------------------------
alter view public.dashboard_stats set (security_invoker = true);
alter view public.disaster_type_stats set (security_invoker = true);
alter view public.severity_stats set (security_invoker = true);
alter view public.yearly_disaster_stats set (security_invoker = true);
alter view public.top_impact_events set (security_invoker = true);
alter view public.latest_events set (security_invoker = true);
alter view public.map_events_sample set (security_invoker = true);

revoke all privileges on table
  public.dashboard_stats,
  public.disaster_type_stats,
  public.severity_stats,
  public.yearly_disaster_stats,
  public.top_impact_events,
  public.latest_events,
  public.map_events_sample
from anon, authenticated;

grant select on table
  public.dashboard_stats,
  public.disaster_type_stats,
  public.severity_stats,
  public.yearly_disaster_stats,
  public.top_impact_events,
  public.latest_events,
  public.map_events_sample
to authenticated;

-- The trigger function remains SECURITY INVOKER; only fix its mutable search_path.
alter function public.set_updated_at() set search_path = pg_catalog, public;
revoke all privileges on function public.set_updated_at() from public, anon, authenticated;
