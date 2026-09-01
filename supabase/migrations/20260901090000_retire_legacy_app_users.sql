-- 4.2-C first-step retirement of the legacy client-authentication table.
-- Historical rows and columns are intentionally preserved for a separately approved cleanup.

alter table public.app_users enable row level security;

drop policy if exists "anon can insert app users" on public.app_users;
drop policy if exists "anon can read app users" on public.app_users;
drop policy if exists "anon can read app_users" on public.app_users;
drop policy if exists "anon can insert app_users" on public.app_users;

revoke all privileges on table public.app_users from public, anon, authenticated;

comment on table public.app_users is
  'DEPRECATED: legacy pre-Supabase-Auth accounts. Retained read-only for audit; not used by application authentication.';

comment on column public.app_users.password is
  'DEPRECATED legacy credential field. Never expose, export, copy, or use for authentication.';

comment on column public.app_users.role is
  'DEPRECATED legacy role. Authorization uses auth.users app_metadata.role.';
