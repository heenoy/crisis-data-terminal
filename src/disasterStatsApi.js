import { supabase } from './supabase.js'

export let dashboardCache = null
export let analyticsCache = null

async function queryView(viewName, { single = false, limit, order } = {}) {
  let query = supabase.from(viewName).select('*')
  if (order) {
    query = query.order(order.column, { ascending: order.ascending ?? true })
  }
  if (limit != null) query = query.limit(limit)
  if (single) {
    const { data, error } = await query.maybeSingle()
    return { data: data ?? null, error }
  }
  const { data, error } = await query
  return { data: data ?? [], error }
}

async function queryDisasterRelationEvents() {
  const { data, error } = await supabase
    .from('disaster_events')
    .select('country, disaster_type, severity')
    .order('event_date', { ascending: false, nullsFirst: false })
    .limit(5000)

  return { data: data ?? [], error }
}

function settleResult(result, fallback) {
  if (result.status === 'fulfilled') return result.value
  const reason = result.reason
  const error = reason instanceof Error ? reason : new Error(String(reason))
  return { data: fallback, error }
}

function syncTimestamp() {
  return new Date().toISOString().slice(0, 19).replace('T', ' ')
}

export function clearDashboardCache() {
  dashboardCache = null
}

export function clearAnalyticsCache() {
  analyticsCache = null
}

export async function fetchDashboardBundle({ force = false } = {}) {
  if (!force && dashboardCache) {
    return { bundle: dashboardCache, error: null }
  }

  const settled = await Promise.allSettled([
    queryView('dashboard_stats', { single: true }),
    queryView('disaster_type_stats', { order: { column: 'count', ascending: false } }),
    queryView('severity_stats', { order: { column: 'count', ascending: false } }),
    queryView('top_impact_events'),
    queryView('latest_events'),
  ])

  const [statsRes, typeRes, severityRes, topRes, latestRes] = settled.map((item, index) => {
    const fallbacks = [null, [], [], [], []]
    return settleResult(item, fallbacks[index])
  })

  const bundle = {
    dashboardStats: statsRes.data,
    disasterTypeStats: typeRes.data,
    severityStats: severityRes.data,
    topImpactEvents: topRes.data,
    latestEvents: latestRes.data,
    lastSync: syncTimestamp(),
    errors: {
      dashboardStats: statsRes.error?.message || null,
      disasterTypeStats: typeRes.error?.message || null,
      severityStats: severityRes.error?.message || null,
      topImpactEvents: topRes.error?.message || null,
      latestEvents: latestRes.error?.message || null,
    },
  }

  const hasAnyData =
    bundle.dashboardStats ||
    bundle.disasterTypeStats.length ||
    bundle.severityStats.length ||
    bundle.topImpactEvents.length ||
    bundle.latestEvents.length

  if (!hasAnyData) {
    const firstError =
      statsRes.error ||
      typeRes.error ||
      severityRes.error ||
      topRes.error ||
      latestRes.error ||
      new Error('统计视图不可用，请在 Supabase 运行 scripts/disaster_stats_views.sql')
    return { bundle: null, error: firstError }
  }

  dashboardCache = bundle
  return { bundle, error: null }
}

export async function fetchAnalyticsBundle({ force = false } = {}) {
  if (!force && analyticsCache) {
    return { bundle: analyticsCache, error: null }
  }

  const settled = await Promise.allSettled([
    queryView('dashboard_stats', { single: true }),
    queryView('disaster_type_stats', { order: { column: 'count', ascending: false } }),
    queryView('severity_stats', { order: { column: 'count', ascending: false } }),
    queryView('yearly_disaster_stats', { order: { column: 'year', ascending: true } }),
    queryView('top_impact_events'),
    queryView('latest_events'),
    queryView('map_events_sample'),
    queryDisasterRelationEvents(),
  ])

  const [
    statsRes,
    typeRes,
    severityRes,
    yearlyRes,
    topRes,
    latestRes,
    mapRes,
    relationRes,
  ] = settled.map((item, index) => {
    const fallbacks = [null, [], [], [], [], [], [], []]
    return settleResult(item, fallbacks[index])
  })

  const bundle = {
    dashboardStats: statsRes.data,
    disasterTypeStats: typeRes.data,
    severityStats: severityRes.data,
    yearlyDisasterStats: yearlyRes.data,
    topImpactEvents: topRes.data,
    latestEvents: latestRes.data,
    mapEventsSample: mapRes.data,
    relationEvents: relationRes.data,
    lastSync: syncTimestamp(),
    errors: {
      summary: statsRes.error?.message || null,
      map: mapRes.error?.message || null,
      trend: yearlyRes.error?.message || null,
      category: typeRes.error?.message || null,
      impact: topRes.error?.message || null,
      relation: relationRes.error?.message || null,
    },
  }

  const hasAnyData =
    bundle.dashboardStats ||
    bundle.disasterTypeStats.length ||
    bundle.yearlyDisasterStats.length ||
    bundle.topImpactEvents.length ||
    bundle.latestEvents.length ||
    bundle.mapEventsSample.length ||
    bundle.relationEvents.length

  if (!hasAnyData) {
    const firstError =
      statsRes.error ||
      typeRes.error ||
      yearlyRes.error ||
      topRes.error ||
      latestRes.error ||
      mapRes.error ||
      relationRes.error ||
      new Error('统计视图不可用，请在 Supabase 运行 scripts/disaster_stats_views.sql')
    return { bundle: null, error: firstError }
  }

  analyticsCache = bundle
  return { bundle, error: null }
}
