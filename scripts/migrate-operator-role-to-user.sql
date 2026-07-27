-- Manual compatibility migration for Crisis Data Terminal roles.
-- Review and run this file in the Supabase SQL Editor when ready.

begin;

update app_users
set role = 'user'
where role = 'operator';

commit;

-- Verification: this should return only admin and user.
select role, count(*) as user_count
from app_users
group by role
order by role;
