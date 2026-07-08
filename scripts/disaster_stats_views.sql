-- Disaster statistics views for Crisis Data Terminal
-- Run in Supabase SQL Editor after disaster_events table exists.
-- Aggregations run in Postgres; frontend reads these views only.

-- Optional columns (skip lines if already present; start_year may already be integer)
alter table disaster_events add column if not exists latitude numeric;
alter table disaster_events add column if not exists longitude numeric;
alter table disaster_events add column if not exists start_year integer;

-- Drop existing views when column lists change (CREATE OR REPLACE cannot rename/reorder columns)
drop view if exists map_events_sample cascade;
drop view if exists latest_events cascade;
drop view if exists top_impact_events cascade;
drop view if exists yearly_disaster_stats cascade;
drop view if exists severity_stats cascade;
drop view if exists disaster_type_stats cascade;
drop view if exists dashboard_stats cascade;

-- 1. Dashboard headline stats (single row)
create view dashboard_stats as
select
  count(*)::bigint as total_events,
  count(distinct country) filter (where country is not null and btrim(country) <> '')::bigint as total_countries,
  count(*) filter (where severity = 'critical')::bigint as critical_events,
  coalesce(sum(affected_population), 0)::bigint as total_affected,
  coalesce(sum(casualties), 0)::bigint as total_deaths,
  (
    select de.country
    from disaster_events de
    where de.country is not null and btrim(de.country) <> ''
    group by de.country
    order by sum(coalesce(de.affected_population, 0)) desc
    limit 1
  ) as top_affected_country,
  (
    select sum(coalesce(de.affected_population, 0))::bigint
    from disaster_events de
    where de.country = (
      select de2.country
      from disaster_events de2
      where de2.country is not null and btrim(de2.country) <> ''
      group by de2.country
      order by sum(coalesce(de2.affected_population, 0)) desc
      limit 1
    )
  ) as top_affected_population,
  (
    select count(*)::bigint
    from disaster_events de
    where de.latitude is not null and de.longitude is not null
  ) as mapped_events
from disaster_events;

-- 2. Disaster type distribution
create view disaster_type_stats as
select
  disaster_type,
  count(*)::bigint as count
from disaster_events
group by disaster_type
order by count desc, disaster_type;

-- 3. Severity distribution
create view severity_stats as
select
  severity,
  count(*)::bigint as count
from disaster_events
group by severity
order by count desc, severity;

-- 4. Yearly trend (start_year may be integer or text in disaster_events)
create view yearly_disaster_stats as
select
  coalesce(
    nullif(btrim(start_year::text), '')::integer,
    extract(year from event_date)::integer
  ) as year,
  count(*)::bigint as event_count,
  coalesce(sum(affected_population), 0)::bigint as total_affected,
  coalesce(sum(casualties), 0)::bigint as total_deaths
from disaster_events
group by 1
having coalesce(
  nullif(btrim(start_year::text), '')::integer,
  extract(year from event_date)::integer
) is not null
order by year;

-- 5. Top impact events
create view top_impact_events as
select
  id,
  title,
  country,
  disaster_type,
  event_date,
  affected_population,
  casualties,
  severity
from disaster_events
order by
  coalesce(affected_population, 0) desc,
  coalesce(casualties, 0) desc,
  event_date desc nulls last
limit 10;

-- 6. Latest events
create view latest_events as
select
  id,
  title,
  country,
  disaster_type,
  event_date,
  severity,
  affected_population,
  casualties,
  updated_at
from disaster_events
order by event_date desc nulls last, updated_at desc nulls last
limit 10;

-- 7. Map sample (max 1000 geocoded points, highest impact first)
create view map_events_sample as
select
  id,
  title,
  country,
  disaster_type,
  severity,
  affected_population,
  casualties,
  latitude,
  longitude
from disaster_events
where latitude is not null
  and longitude is not null
order by
  (coalesce(casualties, 0) * 1000 + coalesce(affected_population, 0)) desc,
  event_date desc nulls last
limit 1000;

grant select on dashboard_stats to anon, authenticated;
grant select on disaster_type_stats to anon, authenticated;
grant select on severity_stats to anon, authenticated;
grant select on yearly_disaster_stats to anon, authenticated;
grant select on top_impact_events to anon, authenticated;
grant select on latest_events to anon, authenticated;
grant select on map_events_sample to anon, authenticated;
