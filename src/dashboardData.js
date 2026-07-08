import {
  labelCountry,
  labelDisasterType,
  labelSeverity,
  localizeEventTitle,
} from './disasterEvents.js'
import { fetchDashboardBundle } from './disasterStatsApi.js'
import { formatStatNumber, parseStatNumber, statNumberOrZero } from './statFormat.js'

const SEVERITY_KEYS = ['critical', 'high', 'medium', 'low']

const DASHBOARD_PRIORITY_TYPES = [
  'flood',
  'typhoon',
  'storm',
  'epidemic',
  'earthquake',
  'extreme_temperature',
  'landslide',
  'drought',
  'wildfire',
]

const DASHBOARD_OTHER_LABEL = '未细分类事件'

function buildDashboardTypeOverview(typeRows, topN = 8) {
  const counts = new Map()
  for (const row of typeRows || []) {
    const key = String(row.disaster_type || '').trim()
    const count = Number(row.count) || 0
    if (key && count > 0) counts.set(key, count)
  }

  const otherCount = counts.get('other') || 0
  counts.delete('other')

  const explicit = [...counts.entries()].map(([key, count]) => ({ key, count }))
  const byCount = [...explicit].sort((a, b) => b.count - a.count)

  const priorityItems = DASHBOARD_PRIORITY_TYPES
    .map((key) => ({ key, count: counts.get(key) || 0 }))
    .filter((item) => item.count > 0)
    .sort((a, b) => b.count - a.count)

  const selected = []
  const selectedKeys = new Set()

  for (const item of priorityItems) {
    if (selected.length >= topN) break
    selected.push(item)
    selectedKeys.add(item.key)
  }

  for (const item of byCount) {
    if (selected.length >= topN) break
    if (!selectedKeys.has(item.key)) {
      selected.push(item)
      selectedKeys.add(item.key)
    }
  }

  const typeOverview = selected
    .sort((a, b) => b.count - a.count)
    .map(({ key, count }) => ({
      key,
      label: labelDisasterType(key),
      count,
    }))

  if (otherCount > 0) {
    typeOverview.push({
      key: 'other',
      label: DASHBOARD_OTHER_LABEL,
      count: otherCount,
    })
  }

  const topExplicit = typeOverview
    .filter((item) => item.key !== 'other')
    .reduce((best, item) => (item.count > best.count ? item : best), { label: null, count: 0 })

  return {
    typeOverview,
    topTypeLabel: topExplicit.count > 0 ? topExplicit.label : null,
  }
}

function mapEventRow(event) {
  return {
    date: String(event.event_date || '').slice(0, 10) || '--',
    country: labelCountry(event.country),
    type: labelDisasterType(event.disaster_type),
    severity: event.severity || '',
    severityLabel: labelSeverity(event.severity),
    title: localizeEventTitle(event),
    affected: statNumberOrZero(event.affected_population),
    casualties: parseStatNumber(event.casualties),
  }
}

function buildSeverityDistribution(severityRows) {
  const counts = Object.fromEntries(severityRows.map((row) => [row.severity, Number(row.count) || 0]))
  return SEVERITY_KEYS.map((key) => ({
    key,
    label: labelSeverity(key),
    value: counts[key] || 0,
  }))
}

export function mapDashboardBundleToOverview(bundle) {
  const stats = bundle.dashboardStats || {}
  const totalEvents = Number(stats.total_events) || 0
  const { typeOverview, topTypeLabel } = buildDashboardTypeOverview(bundle.disasterTypeStats || [], 8)

  return {
    totalEvents,
    criticalCount: Number(stats.critical_events) || 0,
    countryCount: Number(stats.total_countries) || 0,
    totalAffected: statNumberOrZero(stats.total_affected),
    totalCasualties: parseStatNumber(stats.total_deaths),
    typeOverview,
    topTypeLabel,
    topAffectedCountry: stats.top_affected_country ? labelCountry(stats.top_affected_country) : null,
    topAffectedPopulation: Number(stats.top_affected_population) || 0,
    severityDistribution: buildSeverityDistribution(bundle.severityStats || []),
    latestEvents: (bundle.latestEvents || []).slice(0, 5).map(mapEventRow),
    liveFeed: (bundle.latestEvents || []).slice(0, 5).map(mapEventRow),
    topImpact: (bundle.topImpactEvents || []).slice(0, 5).map(mapEventRow),
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

export function buildAiSummaryText(stats) {
  if (!stats) return '系统分析：数据同步中…'

  const lines = [
    '系统分析：',
    `全球灾害事件数据库现有 ${formatDashboardNumber(stats.totalEvents)} 起记录，`,
    `涉及 ${formatDashboardNumber(stats.countryCount)} 个国家/地区。`,
    `其中重大灾害 ${formatDashboardNumber(stats.criticalCount)} 起。`,
    `受影响人数累计约 ${formatDashboardNumber(stats.totalAffected)}。`,
    `死亡人数累计约 ${formatDashboardNumber(stats.totalCasualties)}。`,
  ]

  if (stats.topTypeLabel) {
    lines.push(`灾害类型分布中，${stats.topTypeLabel}记录数量最多。`)
  }

  return lines.join('\n')
}

export function formatDashboardNumber(value) {
  return formatStatNumber(value)
}

export { clearDashboardCache } from './disasterStatsApi.js'
