import {
  fetchAnalyticsData,
  formatCompactNumber,
  INTELLIGENCE_MODULES,
  clearAnalyticsCache,
} from './disasterAnalytics.js'
import { analyticsCache } from './disasterStatsApi.js'
import { showTerminalNotice } from './terminalNotice.js'
import { bindTerminalNavigation, renderBackToMainMenu } from './terminalNav.js'
import {
  renderDonutChart,
  renderDualLineChart,
  renderImpactBarChart,
  renderMapLegend,
} from './intelligenceCharts.js'
import { renderEchartsWorldMap } from './intelligenceEchartsMap.js'

const TOTAL_PAGES = INTELLIGENCE_MODULES.length
const TRANSITION_MS = 520

const MODULE_DISPLAY = {
  map: { label: 'GLOBAL DISASTER MAP', zh: '全球灾害空间分布' },
  trend: { label: 'DISASTER TREND', zh: '灾害年度趋势分析' },
  category: { label: 'DISASTER CATEGORY', zh: '灾害类型分布' },
  impact: { label: 'IMPACT ANALYSIS', zh: '灾害影响规模排行' },
  timeline: { label: 'EVENT TIMELINE', zh: '灾害事件时间轴' },
}

let state = {
  loading: true,
  transitioning: false,
  error: null,
  analytics: null,
  moduleErrors: {},
  currentPage: 1,
  onNavigate: null,
  mapCleanup: null,
}

const MODULE_ERROR_TEXT = '&gt; 该模块同步失败，请稍后重试。'

function renderModuleError(moduleKey) {
  if (!state.moduleErrors?.[moduleKey]) return ''
  return `<p class="intel-module-error">${MODULE_ERROR_TEXT}</p>`
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function padPage(n) {
  return String(n).padStart(2, '0')
}

function currentModule() {
  return INTELLIGENCE_MODULES.find((m) => m.page === state.currentPage) || INTELLIGENCE_MODULES[0]
}

function moduleDisplay() {
  return MODULE_DISPLAY[currentModule().key] || { label: '', zh: '' }
}

function renderSummaryStrip() {
  const summary = state.analytics?.summary
  if (!summary) return ''

  return `
    <div class="intel-center__summary" aria-label="数据库实时统计">
      <span>档案总量 <strong>${formatCompactNumber(summary.totalEvents)}</strong></span>
      <span>涉及国家 <strong>${formatCompactNumber(summary.countryCount)}</strong></span>
      <span>重大灾害 <strong>${formatCompactNumber(summary.criticalCount)}</strong></span>
      <span>累计受影响 <strong>${formatCompactNumber(summary.totalAffected)}</strong></span>
      <span>同步时间 <strong>${escapeHtml(summary.lastSync)}</strong></span>
    </div>
  `
}

function renderIntelHeader() {
  const display = moduleDisplay()
  return `
    <header class="intel-center__header">
      <p class="intel-center__brand">应急灾害档案 · 数据分析中心</p>
      <h1 class="intel-center__module-en">${escapeHtml(display.zh)}</h1>
      <p class="intel-center__page-label">第 ${padPage(state.currentPage)} 页 / 共 ${padPage(TOTAL_PAGES)} 页</p>
      ${state.analytics ? renderSummaryStrip() : ''}
    </header>
  `
}

function renderTimeline(events) {
  if (!events?.length) {
    return '<p class="intel-timeline-empty">暂无时间轴记录</p>'
  }

  return `
    <div class="intel-timeline-axis">
      ${events
        .map((event, index) => {
          const isCritical = event.severity === 'critical'
          const cardClass = isCritical ? 'intel-timeline-card--critical' : 'intel-timeline-card--normal'
          const isLast = index === events.length - 1
          return `
        <div class="intel-timeline-entry">
          <div class="intel-timeline-rail" aria-hidden="true">
            <span class="intel-timeline-dot ${isCritical ? 'intel-timeline-dot--critical' : ''}"></span>
            ${isLast ? '' : '<span class="intel-timeline-line"></span>'}
          </div>
          <article class="intel-timeline-card ${cardClass}">
            <dl class="intel-timeline-card__grid">
              <div><dt>日期</dt><dd>${escapeHtml(event.date)}</dd></div>
              <div class="intel-timeline-card__span-2"><dt>事件</dt><dd>${escapeHtml(event.title)}</dd></div>
              <div><dt>国家</dt><dd>${escapeHtml(event.country)}</dd></div>
              <div><dt>灾害类型</dt><dd>${escapeHtml(event.typeLabel)}</dd></div>
              <div><dt>影响等级</dt><dd>${escapeHtml(event.severityLabel)}</dd></div>
              <div class="intel-timeline-card__span-2">
                <dt>影响规模</dt>
                <dd>死亡人数：${formatCompactNumber(event.casualties)} · 受影响人数：${formatCompactNumber(event.affected_population)}</dd>
              </div>
            </dl>
          </article>
        </div>
      `
        })
        .join('')}
    </div>
  `
}

function renderModuleBody() {
  const mod = currentModule()
  const data = state.analytics
  const moduleError = renderModuleError(mod.key)
  if (moduleError) return `<div class="intel-module">${moduleError}</div>`

  switch (mod.key) {
    case 'map':
      return `
        <div class="intel-module intel-module--map">
          <div class="intel-module__meta">
            <span>已标注事件：<strong>${formatCompactNumber(data.summary.mappedEvents)}</strong></span>
            <span>地图展示：<strong>${formatCompactNumber(data.mapPoints.length)}</strong>${data.mapPointsTotal > data.mapPoints.length ? ` / ${formatCompactNumber(data.mapPointsTotal)}` : ''}</span>
            <span>档案总量：<strong>${formatCompactNumber(data.summary.totalEvents)}</strong></span>
          </div>
          <div class="terminal-chart intel-chart intel-chart--map" id="intel-chart-map"></div>
          <div class="intel-map-legend" id="intel-map-legend"></div>
        </div>
      `
    case 'trend':
      return `
        <div class="intel-module intel-module--trend">
          <div class="intel-module__meta">
            <span>年份跨度：<strong>${escapeHtml(data.summary.yearSpan)}</strong></span>
            <span>实线：年度事件数 · 虚线：年度死亡人数</span>
          </div>
          <div class="terminal-chart intel-chart" id="intel-chart-trend"></div>
        </div>
      `
    case 'category':
      return `
        <div class="intel-module intel-module--category">
          <div class="intel-module__meta">
            <span>按灾害类型统计档案数量</span>
          </div>
          <div class="terminal-chart intel-chart" id="intel-chart-category"></div>
        </div>
      `
    case 'impact':
      return `
        <div class="intel-module intel-module--impact">
          <div class="intel-module__meta">
            <span>影响规模排行前十（综合死亡人数与受影响人数）</span>
          </div>
          <div class="terminal-chart intel-chart intel-chart--wide" id="intel-chart-impact"></div>
        </div>
      `
    case 'timeline':
      return `
        <div class="intel-module intel-module--timeline">
          ${renderTimeline(data.eventTimeline)}
        </div>
      `
    default:
      return ''
  }
}

function renderPager() {
  const prevDisabled = state.currentPage <= 1
  const nextDisabled = state.currentPage >= TOTAL_PAGES
  return `
    <nav class="intel-pager" aria-label="分析模块分页">
      <button type="button" class="intel-pager__arrow" id="intel-prev" aria-label="上一页" ${prevDisabled ? 'disabled' : ''}>◀</button>
      <span class="intel-pager__status">第 ${padPage(state.currentPage)} 页 / 共 ${padPage(TOTAL_PAGES)} 页</span>
      <button type="button" class="intel-pager__arrow" id="intel-next" aria-label="下一页" ${nextDisabled ? 'disabled' : ''}>▶</button>
    </nav>
  `
}

export function renderAnalyticsPage() {
  if (state.loading) {
    return `
      <section class="vault-console vault-console--subpage" aria-label="数据分析中心">
        ${renderBackToMainMenu()}
        <div class="intel-center">
          ${renderIntelHeader()}
          <p class="intel-center__loading">&gt; 正在同步灾害数据库...</p>
        </div>
      </section>
    `
  }

  if (state.error) {
    return `
      <section class="vault-console vault-console--subpage" aria-label="数据分析中心">
        ${renderBackToMainMenu()}
        <div class="intel-center">
          ${renderIntelHeader()}
          <p class="intel-center__error">&gt; [错误] ${escapeHtml(state.error)}</p>
          <div class="intel-center__actions">
            <button type="button" class="intel-pager__arrow" id="analytics-refresh">↻</button>
          </div>
        </div>
      </section>
    `
  }

  const viewportClass = state.transitioning
    ? 'intel-viewport intel-viewport--loading'
    : 'intel-viewport intel-viewport--ready'

  return `
    <section class="vault-console vault-console--subpage" aria-label="数据分析中心">
      ${renderBackToMainMenu()}
      <div class="intel-center">
        ${renderIntelHeader()}
        <div class="${viewportClass}">
          ${
            state.transitioning
              ? '<p class="intel-center__module-loading">&gt; 正在同步灾害数据库...</p>'
              : `<div class="intel-viewport__content intel-viewport__content--fade-in">${renderModuleBody()}</div>`
          }
        </div>
        ${renderPager()}
      </div>
    </section>
  `
}

function paintCurrentModule() {
  if (!state.analytics || state.transitioning) return

  state.mapCleanup?.()
  state.mapCleanup = null

  const mod = currentModule()
  const data = state.analytics

  if (mod.key === 'map') {
    const el = document.getElementById('intel-chart-map')
    renderEchartsWorldMap(el, data.mapPoints).then((cleanup) => {
      state.mapCleanup = cleanup
    })
    renderMapLegend(document.getElementById('intel-map-legend'))
  } else if (mod.key === 'trend') {
    renderDualLineChart(
      document.getElementById('intel-chart-trend'),
      data.annualTrend.eventCounts,
      data.annualTrend.deathTotals,
      { labelA: '年度事件数', labelB: '年度死亡人数' },
    )
  } else if (mod.key === 'category') {
    renderDonutChart(document.getElementById('intel-chart-category'), data.categoryDistribution)
  } else if (mod.key === 'impact') {
    renderImpactBarChart(document.getElementById('intel-chart-impact'), data.impactTop10)
  }
}

function updateViewport() {
  const viewport = document.querySelector('.intel-viewport')
  if (!viewport) return

  if (state.transitioning) {
    viewport.className = 'intel-viewport intel-viewport--loading'
    viewport.innerHTML = '<p class="intel-center__module-loading">&gt; 正在同步灾害数据库...</p>'
    return
  }

  viewport.className = 'intel-viewport intel-viewport--ready'
  viewport.innerHTML = `<div class="intel-viewport__content intel-viewport__content--fade-in">${renderModuleBody()}</div>`
  requestAnimationFrame(() => paintCurrentModule())
}

function updateHeaderAndPager() {
  const center = document.querySelector('.intel-center')
  if (!center) return

  const header = center.querySelector('.intel-center__header')
  const pager = center.querySelector('.intel-pager')
  if (header) header.outerHTML = renderIntelHeader()
  if (pager) pager.outerHTML = renderPager()
  bindAnalyticsActions()
}

async function switchPage(nextPage) {
  if (state.transitioning || nextPage < 1 || nextPage > TOTAL_PAGES) return
  if (nextPage === state.currentPage) return

  state.transitioning = true
  updateViewport()

  await new Promise((resolve) => setTimeout(resolve, TRANSITION_MS))

  state.currentPage = nextPage
  state.transitioning = false
  updateHeaderAndPager()
  updateViewport()
}

function rerenderPage() {
  const app = document.getElementById('app')
  if (!app) return
  app.innerHTML = renderAnalyticsPage()
  bindAnalyticsActions()
  if (!state.loading && !state.error && !state.transitioning) {
    requestAnimationFrame(() => paintCurrentModule())
  }
}

function bindAnalyticsActions() {
  document.getElementById('intel-prev')?.addEventListener('click', () => {
    switchPage(state.currentPage - 1)
  })

  document.getElementById('intel-next')?.addEventListener('click', () => {
    switchPage(state.currentPage + 1)
  })

  document.getElementById('analytics-refresh')?.addEventListener('click', () => {
    loadAnalytics({ notify: true, force: true })
  })

  bindTerminalNavigation({
    onNavigate: state.onNavigate,
    root: document.getElementById('app'),
  })
}

async function loadAnalytics({ notify = false, force = false } = {}) {
  if (force) clearAnalyticsCache()

  if (!force && analyticsCache) {
    const { analytics, error } = await fetchAnalyticsData({ force: false })
    if (analytics) {
      state.mapCleanup?.()
      state.mapCleanup = null
      state.analytics = analytics
      state.moduleErrors = analytics.moduleErrors || {}
      state.loading = false
      state.error = null
      rerenderPage()
      return
    }
    if (error && !analyticsCache) {
      state.loading = false
      state.error = error.message || '灾害数据加载失败'
      rerenderPage()
      return
    }
  }

  state.mapCleanup?.()
  state.mapCleanup = null
  state.loading = true
  state.error = null
  state.currentPage = 1
  rerenderPage()

  const { analytics, error } = await fetchAnalyticsData({ force })

  if (error && !analytics) {
    state.loading = false
    state.error = error.message || '灾害数据加载失败'
    state.analytics = null
    state.moduleErrors = {}
    rerenderPage()
    if (notify) showTerminalNotice(state.error, 'error')
    return
  }

  state.analytics = analytics
  state.moduleErrors = analytics?.moduleErrors || {}
  state.loading = false
  state.error = null
  rerenderPage()

  if (notify) {
    showTerminalNotice(`分析数据已刷新 · ${state.analytics.summary.totalEvents} 条记录`)
  }
}

export function bindAnalyticsPage({ onNavigate }) {
  state.onNavigate = onNavigate
  bindAnalyticsActions()
  if (!state.loading && !state.error && !state.transitioning) {
    requestAnimationFrame(() => paintCurrentModule())
  }
}

export async function initAnalyticsPage({ onNavigate }) {
  state.onNavigate = onNavigate
  state.currentPage = 1
  await loadAnalytics({ force: false })
}
