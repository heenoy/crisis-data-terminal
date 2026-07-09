import { fetchDashboardBundle } from './disasterStatsApi.js'
import { formatStatNumber, parseStatNumber, statNumberOrZero } from './statFormat.js'

export function mapDashboardBundleToOverview(bundle) {
  const stats = bundle.dashboardStats || {}

  return {
    totalEvents: Number(stats.total_events) || 0,
    criticalCount: Number(stats.critical_events) || 0,
    countryCount: Number(stats.total_countries) || 0,
    totalAffected: statNumberOrZero(stats.total_affected),
    totalCasualties: parseStatNumber(stats.total_deaths),
    lastSync: bundle.lastSync,
    databaseStatus: '已连接',
    systemStatus: '在线',
    sectionErrors: bundle.errors || {},
  }
}

export async function fetchGlobalDisasterStats({ force = false } = {}) {
  const { bundle, error } = await fetchDashboardBundle({ force })
  if (error) return { error, stats: null }
  return { error: null, stats: mapDashboardBundleToOverview(bundle) }
}

export async function fetchDashboardOverview({ force = false } = {}) {
  const { bundle, error } = await fetchDashboardBundle({ force })
  if (error) return { error, overview: null }
  return { error: null, overview: mapDashboardBundleToOverview(bundle) }
}

export function formatDashboardNumber(value) {
  return formatStatNumber(value)
}

export { clearDashboardCache } from './disasterStatsApi.js'
