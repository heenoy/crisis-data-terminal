-- Fourth Stage 4.2-A: additive Auth audit field only.
-- Prepared locally; do not apply to the linked project until 4.2-B approval.

alter table public.disaster_events
  add column if not exists created_by_auth uuid;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'disaster_events_created_by_auth_fkey'
      and conrelid = 'public.disaster_events'::regclass
  ) then
    alter table public.disaster_events
      add constraint disaster_events_created_by_auth_fkey
      foreign key (created_by_auth)
      references auth.users (id)
      on delete set null;
  end if;
end
$$;

create index if not exists disaster_events_created_by_auth_idx
  on public.disaster_events (created_by_auth);

comment on column public.disaster_events.created_by_auth is
  'Supabase Auth UUID of the administrator who created the record. Legacy rows may remain NULL.';
