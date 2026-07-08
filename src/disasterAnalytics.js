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
  { page: 5, key: 'relation', title: 'GLOBAL DISASTER RELATION NETWORK', subtitle: '全球灾害关系图谱 · disaster_events' },
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

const RELATION_COUNTRY_LIMIT = 20
const RELATION_TYPES_PER_COUNTRY = 3

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

function buildCategoryDistribution(typeRows) {
  return buildDisasterCategoryDistribution(typeRows)
}

function normalizeKey(value, fallback = 'unknown') {
  const key = String(value || '').trim()
  return key || fallback
}

function incrementMap(map, key, amount = 1) {
  map.set(key, (map.get(key) || 0) + amount)
}

function scaledSize(value, maxValue, min, max) {
  if (!maxValue) return min
  return Math.round(min + Math.sqrt(value / maxValue) * (max - min))
}

function countBy(rows, getKey) {
  const counts = new Map()
  rows.forEach((row) => incrementMap(counts, getKey(row)))
  return counts
}

function mapRelationRow(row) {
  return {
    country: normalizeKey(row.country, 'Unknown'),
    disasterType: normalizeKey(row.disaster_type, 'other').toLowerCase(),
    severity: normalizeKey(row.severity, 'medium').toLowerCase(),
  }
}

function buildRelationNetwork(relationRows) {
  const rows = (relationRows || []).map(mapRelationRow)
  const countryCounts = new Map()
  const typeCounts = new Map()
  const severityCounts = new Map()
  const countryTypeCounts = new Map()

  rows.forEach((row) => {
    incrementMap(countryCounts, row.country)
    incrementMap(countryTypeCounts, `${row.country}|||${row.disasterType}`)
  })

  const selectedCountries = new Set(
    [...countryCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, RELATION_COUNTRY_LIMIT)
      .map(([country]) => country),
  )

  const selectedTypes = new Set()
  const selectedSeverities = new Set()
  const selectedCountryTypeCounts = new Map()
  const selectedTypeSeverityCounts = new Map()
  const countryTypeLabels = new Map()
  const countrySeverityLabels = new Map()

  selectedCountries.forEach((country) => {
    const countryRows = rows.filter((row) => row.country === country)
    const typeRows = [...countBy(countryRows, (row) => row.disasterType).entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, RELATION_TYPES_PER_COUNTRY)

    countryTypeLabels.set(country, typeRows.map(([type]) => labelDisasterType(type)).join('、'))

    const severityLabelSet = new Set()
    typeRows.forEach(([disasterType, count]) => {
      const scopedRows = countryRows.filter((row) => row.disasterType === disasterType)
      const [mainSeverity] = [...countBy(scopedRows, (row) => row.severity).entries()]
        .sort((a, b) => b[1] - a[1])[0] || ['medium', count]

      selectedTypes.add(disasterType)
      incrementMap(typeCounts, disasterType, count)
      selectedCountryTypeCounts.set(`${country}|||${disasterType}`, count)
      severityLabelSet.add(labelSeverity(mainSeverity))
    })

    countrySeverityLabels.set(country, [...severityLabelSet].join('、'))
  })

  selectedTypes.forEach((disasterType) => {
    const scopedRows = rows.filter(
      (row) => selectedCountries.has(row.country) && row.disasterType === disasterType,
    )
    const [mainSeverity, count] = [...countBy(scopedRows, (row) => row.severity).entries()]
      .sort((a, b) => b[1] - a[1])[0] || ['medium', 0]

    selectedSeverities.add(mainSeverity)
    incrementMap(severityCounts, mainSeverity, count)
    selectedTypeSeverityCounts.set(`${disasterType}|||${mainSeverity}`, count)
  })

  const maxCountryCount = Math.max(0, ...[...selectedCountries].map((country) => countryCounts.get(country) || 0))
  const maxTypeCount = Math.max(0, ...[...selectedTypes].map((type) => typeCounts.get(type) || 0))
  const maxSeverityCount = Math.max(0, ...[...selectedSeverities].map((severity) => severityCounts.get(severity) || 0))
  const maxLinkCount = Math.max(
    0,
    ...selectedCountryTypeCounts.values(),
    ...selectedTypeSeverityCounts.values(),
  )

  const nodes = [
    ...[...selectedCountries].map((country) => ({
      id: `country:${country}`,
      name: labelCountry(country),
      value: countryCounts.get(country) || 0,
      kind: 'country',
      category: 0,
      symbolSize: scaledSize(countryCounts.get(country) || 0, maxCountryCount, 26, 58),
      metrics: {
        disasterTypes: countryTypeLabels.get(country) || '--',
        severities: countrySeverityLabels.get(country) || '--',
      },
    })),
    ...[...selectedTypes].map((type) => ({
      id: `type:${type}`,
      name: labelDisasterType(type),
      value: typeCounts.get(type) || 0,
      kind: 'type',
      category: 1,
      symbolSize: scaledSize(typeCounts.get(type) || 0, maxTypeCount, 18, 38),
      metrics: {
        severities: [...selectedTypeSeverityCounts.keys()]
          .filter((key) => key.startsWith(`${type}|||`))
          .map((key) => labelSeverity(key.split('|||')[1]))
          .join('、') || '--',
      },
    })),
    ...[...selectedSeverities].map((severity) => ({
      id: `severity:${severity}`,
      name: labelSeverity(severity),
      value: severityCounts.get(severity) || 0,
      kind: 'severity',
      category: 2,
      symbolSize: scaledSize(severityCounts.get(severity) || 0, maxSeverityCount, 12, 24),
    })),
  ]

  const links = [
    ...[...selectedCountryTypeCounts.entries()].map(([key, count]) => {
      const [country, disasterType] = key.split('|||')
      return {
        source: `country:${country}`,
        target: `type:${disasterType}`,
        value: count,
        lineStyle: {
          width: scaledSize(count, maxLinkCount, 1, 7),
        },
      }
    }),
    ...[...selectedTypeSeverityCounts.entries()].map(([key, count]) => {
      const [disasterType, severity] = key.split('|||')
      return {
        source: `type:${disasterType}`,
        target: `severity:${severity}`,
        value: count,
        lineStyle: {
          width: scaledSize(count, maxLinkCount, 1, 7),
        },
      }
    }),
  ]

  return {
    nodes,
    links,
    categories: [
      { name: '国家', itemStyle: { color: '#39ff88' } },
      { name: '灾害类型', itemStyle: { color: '#ffb347' } },
      { name: '风险等级', itemStyle: { color: '#ff5555' } },
    ],
    metrics: {
      totalEvents: rows.length,
      countryCount: countryCounts.size,
      visibleCountryCount: selectedCountries.size,
      nodeCount: nodes.length,
      linkCount: links.length,
    },
  }
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

  return {
    summary: {
      totalEvents: Number(stats.total_events) || 0,
      criticalCount: Number(stats.critical_events) || 0,
      countryCount: Number(stats.total_countries) || 0,
      totalAffected: statNumberOrZero(stats.total_affected),
      totalCasualties: parseStatNumber(stats.total_deaths),
      mappedEvents: Number(stats.mapped_events) || mapPoints.length,
      yearSpan: years.length ? `${years[0]}-${years[years.length - 1]}` : '--',
      lastSync: bundle.lastSync,
    },
    mapPoints,
    mapPointsTotal: Number(stats.mapped_events) || mapPoints.length,
    annualTrend,
    categoryDistribution: buildCategoryDistribution(bundle.disasterTypeStats),
    relationNetwork: buildRelationNetwork(bundle.relationEvents),
    impactTop10,
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
