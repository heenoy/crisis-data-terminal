import {
  buildDisasterCategoryDistribution,
  labelCountry,
  labelDisasterType,
  labelSeverity,
  localizeEventTitle,
} from './disasterEvents.js'
import { fetchAnalyticsBundle } from './disasterStatsApi.js'
import { formatStatNumber, parseStatNumber, statNumberOrZero } from './statFormat.js'

export const INTELLIGENCE_MODULES = [
  { page: 1, key: 'map', title: 'GLOBAL DISASTER MAP', subtitle: '全球灾害空间分布 · latitude / longitude' },
  { page: 2, key: 'trend', title: 'DISASTER TREND', subtitle: '年度灾害趋势 · start_year' },
  { page: 3, key: 'category', title: 'DISASTER CATEGORY', subtitle: '灾害类型分布 · disaster_type' },
  { page: 4, key: 'impact', title: 'IMPACT ANALYSIS', subtitle: '影响规模排行 · casualties / affected_population' },
  { page: 5, key: 'timeline', title: 'EVENT TIMELINE', subtitle: '灾害事件时间轴 · 高影响事件' },
]

export const CATEGORY_TYPE_KEYS = [
  'earthquake',
  'flood',
  'typhoon',
  'storm',
  'epidemic',
  'drought',
  'extreme_temperature',
  'landslide',
  'wildfire',
  'volcanic_activity',
  'transport_accident',
  'industrial_accident',
  'hazardous_material',
  'other',
]

export const CATEGORY_TYPES = CATEGORY_TYPE_KEYS.map((key) => ({
  key,
  label: labelDisasterType(key),
}))

export function impactScore(event) {
  const casualties = statNumberOrZero(event.casualties)
  const affected = statNumberOrZero(event.affected_population)
  return casualties * 1000 + affected
}

function parseCoord(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function mapMapPoint(row) {
  const lat = parseCoord(row.latitude)
  const lng = parseCoord(row.longitude)
  if (lat == null || lng == null || lat < -90 || lat > 90 || lng < -180 || lng > 180) return null

  return {
    id: row.id,
    lat,
    lng,
    disaster_type: row.disaster_type || 'other',
    title: localizeEventTitle(row),
    country: labelCountry(row.country),
    casualties: statNumberOrZero(row.casualties),
    affected_population: statNumberOrZero(row.affected_population),
    impact: impactScore(row),
  }
}

function mapTimelineEvent(row) {
  return {
    id: row.id,
    date: String(row.event_date || '').slice(0, 10) || '--',
    country: labelCountry(row.country),
    disaster_type: row.disaster_type || 'other',
    typeLabel: labelDisasterType(row.disaster_type),
    severity: row.severity || 'medium',
    severityLabel: labelSeverity(row.severity),
    title: localizeEventTitle(row),
    impact: impactScore(row),
    casualties: statNumberOrZero(row.casualties),
    affected_population: statNumberOrZero(row.affected_population),
  }
}

function buildCategoryDistribution(typeRows) {
  return buildDisasterCategoryDistribution(typeRows)
}

function buildAnnualTrend(yearlyRows) {
  const years = (yearlyRows || [])
    .map((row) => Number(row.year))
    .filter((year) => Number.isFinite(year))
    .sort((a, b) => a - b)

  const byYear = Object.fromEntries(
    (yearlyRows || []).map((row) => [Number(row.year), row]),
  )

  return {
    years,
    eventCounts: years.map((year) => ({
      key: String(year),
      label: String(year),
      value: Number(byYear[year]?.event_count) || 0,
    })),
    affectedTotals: years.map((year) => ({
      key: String(year),
      label: String(year),
      value: statNumberOrZero(byYear[year]?.total_affected),
    })),
    deathTotals: years.map((year) => ({
      key: String(year),
      label: String(year),
      value: statNumberOrZero(byYear[year]?.total_deaths),
    })),
  }
}

export function mapAnalyticsBundleToModel(bundle) {
  const stats = bundle.dashboardStats || {}
  const mapPoints = (bundle.mapEventsSample || []).map(mapMapPoint).filter(Boolean)
  const annualTrend = buildAnnualTrend(bundle.yearlyDisasterStats)
  const years = annualTrend.years

  const impactTop10 = (bundle.topImpactEvents || []).map((row) => ({
    key: row.id,
    label: localizeEventTitle(row),
    value: impactScore(row),
    country: labelCountry(row.country),
    casualties: statNumberOrZero(row.casualties),
    affected_population: statNumberOrZero(row.affected_population),
  }))

  const eventTimeline = (bundle.topImpactEvents || []).map(mapTimelineEvent)

  return {
    summary: {
      totalEvents: Number(stats.total_events) || 0,
      criticalCount: Number(stats.critical_events) || 0,
      countryCount: Number(stats.total_countries) || 0,
      totalAffected: statNumberOrZero(stats.total_affected),
      totalCasualties: parseStatNumber(stats.total_deaths),
      mappedEvents: Number(stats.mapped_events) || mapPoints.length,
      yearSpan: years.length ? `${years[0]}–${years[years.length - 1]}` : '--',
      lastSync: bundle.lastSync,
    },
    mapPoints,
    mapPointsTotal: Number(stats.mapped_events) || mapPoints.length,
    annualTrend,
    categoryDistribution: buildCategoryDistribution(bundle.disasterTypeStats),
    impactTop10,
    eventTimeline,
    moduleErrors: bundle.errors || {},
  }
}

export async function fetchAnalyticsData({ force = false } = {}) {
  const { bundle, error } = await fetchAnalyticsBundle({ force })
  if (error) return { analytics: null, error }
  return { analytics: mapAnalyticsBundleToModel(bundle), error: null }
}

export function formatCompactNumber(value) {
  return formatStatNumber(value)
}

export { labelDisasterType }
export { clearAnalyticsCache } from './disasterStatsApi.js'
