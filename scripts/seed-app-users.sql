-- Course demo seed for app_users
-- Run in Supabase SQL Editor

insert into app_users (username, password, display_name, role)
values ('admin', '123456', '系统管理员', 'admin');

-- Demo RLS (adjust for your course environment)
-- alter table app_users enable row level security;
-- create policy "anon can read app_users for login"
--   on app_users for select to anon using (true);
-- create policy "anon can insert app_users for register"
--   on app_users for insert to anon with check (true);
