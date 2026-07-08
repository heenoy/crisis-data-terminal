-- Verify disaster_events.created_by foreign key and admin user
-- Run in Supabase SQL Editor

-- 1. FK target
select
  tc.constraint_name,
  kcu.column_name,
  ccu.table_schema as foreign_table_schema,
  ccu.table_name as foreign_table_name,
  ccu.column_name as foreign_column_name
from information_schema.table_constraints tc
join information_schema.key_column_usage kcu
  on tc.constraint_name = kcu.constraint_name
join information_schema.constraint_column_usage ccu
  on ccu.constraint_name = tc.constraint_name
where tc.table_name = 'disaster_events'
  and tc.constraint_type = 'FOREIGN KEY'
  and kcu.column_name = 'created_by';

-- 2. admin user row
select id, username, display_name, role, created_at
from app_users
where username = 'admin';

-- 3. Ensure anon can read app_users (required for created_by validation)
alter table app_users enable row level security;

drop policy if exists "anon can read app_users" on app_users;
create policy "anon can read app_users"
  on app_users for select to anon using (true);

drop policy if exists "anon can insert app_users" on app_users;
create policy "anon can insert app_users"
  on app_users for insert to anon with check (true);

-- 4. created_by orphans (should return 0 rows)
select de.id, de.title, de.created_by
from disaster_events de
left join app_users au on au.id = de.created_by
where de.created_by is not null
  and au.id is null
limit 20;
