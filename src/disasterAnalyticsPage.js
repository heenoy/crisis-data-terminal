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
} from './intelligenceCharts.js'
import { renderEchartsWorldMap } from './intelligenceEchartsMap.js'
import { renderDisasterRelationNetwork } from './intelligenceRelationNetwork.js'

const TOTAL_PAGES = INTELLIGENCE_MODULES.length
const TRANSITION_MS = 520

const MODULE_DISPLAY = {
  map: { label: 'GLOBAL DISASTER MAP', zh: '全球灾害空间分布' },
  trend: { label: 'DISASTER TREND', zh: '灾害年度趋势分析' },
  category: { label: 'DISASTER CATEGORY', zh: '灾害类型分布' },
  impact: { label: 'IMPACT ANALYSIS', zh: '灾害影响规模排行' },
  relation: { label: 'GLOBAL DISASTER RELATION NETWORK', zh: 'GLOBAL DISASTER RELATION NETWORK 全球灾害关系图谱' },
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
  relationCleanup: null,
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
    ${renderSideMetric('TOTAL EVENTS', formatCompactNumber(summary.totalEvents))}
    ${renderSideMetric('COUNTRIES', formatCompactNumber(summary.countryCount))}
    ${renderSideMetric('CRITICAL', formatCompactNumber(summary.criticalCount))}
    ${renderSideMetric('DEATHS', formatCompactNumber(summary.totalCasualties))}
  `
}

function renderSideMetric(label, value) {
  return `
    <article class="intel-side-metric">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `
}

function renderIntelHeader() {
  const display = moduleDisplay()
  return `
    <header class="intel-center__header">
      <div class="intel-frame-label">
        <span>[CRISIS_DATA / ANALYTICS_CENTER]</span>
      </div>
      <div class="intel-frame-line"></div>
      <div class="intel-frame-label intel-frame-label--right">
        <span>[DATABASE: ONLINE]</span>
      </div>
    </header>
  `
}

function renderSidePanel() {
  const summary = state.analytics?.summary
  const display = moduleDisplay()

  return `
    <aside class="intel-side-panel" aria-label="分析中心状态栏">
      <div class="intel-side-actions">
        ${renderBackToMainMenu()}
      </div>
      <div class="intel-side-transmission">
        <p>&gt; DATA_ANALYSIS_MODULE</p>
        <strong>${escapeHtml(display.label)}</strong>
        <span>${escapeHtml(display.zh)}</span>
      </div>
      <div class="intel-side-face" data-ai-face-slot aria-label="AI 状态槽">
        <span>AI CORE</span>
      </div>
      <div class="intel-side-metrics">
        ${summary ? renderSummaryStrip() : ''}
      </div>
      <p class="intel-side-sync">&gt; LAST_SYNC: ${escapeHtml(summary?.lastSync || '--')}</p>
    </aside>
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
            <span>已标注事件数量：<strong>${formatCompactNumber(data.mapPoints.length)}</strong>${data.mapPointsTotal > data.mapPoints.length ? ` / ${formatCompactNumber(data.mapPointsTotal)}` : ''}</span>
            <span>涉及国家数量：<strong>${formatCompactNumber(data.summary.countryCount)}</strong></span>
            <span>重大灾害数量：<strong>${formatCompactNumber(data.summary.criticalCount)}</strong></span>
          </div>
          <div class="terminal-chart intel-chart intel-chart--map">
            <div id="intel-chart-map"></div>
          </div>
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
    case 'relation':
      return `
        <div class="intel-module intel-module--relation">
          <div class="intel-module__meta intel-relation-meta">
            <span>展示事件数量最高国家与主要灾害类型之间的关联。</span>
            <span>节点：<strong>${formatCompactNumber(data.relationNetwork.metrics.nodeCount)}</strong></span>
            <span>关系：<strong>${formatCompactNumber(data.relationNetwork.metrics.linkCount)}</strong></span>
          </div>
          <div class="intel-relation-stage">
            <div class="terminal-chart intel-chart intel-chart--relation" id="intel-chart-relation"></div>
          </div>
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
        <div class="intel-center">
          ${renderIntelHeader()}
          <div class="intel-archive-layout">
            <main class="intel-archive-main">
              <p class="intel-center__loading">&gt; 正在同步灾害数据库...</p>
            </main>
            ${renderSidePanel()}
          </div>
          <footer class="intel-frame-footer">
            <span>[CIVILIZATION_ENGINE: ONLINE]</span>
            <span>[RECORD: PERMANENT]</span>
          </footer>
        </div>
      </section>
    `
  }

  if (state.error) {
    return `
      <section class="vault-console vault-console--subpage" aria-label="数据分析中心">
        <div class="intel-center">
          ${renderIntelHeader()}
          <div class="intel-archive-layout">
            <main class="intel-archive-main">
              <p class="intel-center__error">&gt; [错误] ${escapeHtml(state.error)}</p>
              <div class="intel-center__actions">
                <button type="button" class="intel-pager__arrow" id="analytics-refresh">↻</button>
              </div>
            </main>
            ${renderSidePanel()}
          </div>
          <footer class="intel-frame-footer">
            <span>[CIVILIZATION_ENGINE: ONLINE]</span>
            <span>[RECORD: PERMANENT]</span>
          </footer>
        </div>
      </section>
    `
  }

  const viewportClass = state.transitioning
    ? 'intel-viewport intel-viewport--loading'
    : 'intel-viewport intel-viewport--ready'

  return `
    <section class="vault-console vault-console--subpage" aria-label="数据分析中心">
      <div class="intel-center">
        ${renderIntelHeader()}
        <div class="intel-archive-layout">
          <main class="intel-archive-main">
            <div class="intel-report-kicker">
              <span>${escapeHtml(moduleDisplay().label)}</span>
              <em>/ ${escapeHtml(moduleDisplay().zh)}</em>
            </div>
            <div class="${viewportClass}">
              ${
                state.transitioning
                  ? '<p class="intel-center__module-loading">&gt; 正在同步灾害数据库...</p>'
                  : `<div class="intel-viewport__content intel-viewport__content--fade-in">${renderModuleBody()}</div>`
              }
            </div>
            ${renderPager()}
          </main>
          ${renderSidePanel()}
        </div>
        <footer class="intel-frame-footer">
          <span>[CIVILIZATION_ENGINE: ONLINE]</span>
          <span>[RECORD: PERMANENT]</span>
        </footer>
      </div>
    </section>
  `
}

function paintCurrentModule() {
  if (!state.analytics || state.transitioning) return

  state.mapCleanup?.()
  state.mapCleanup = null
  state.relationCleanup?.()
  state.relationCleanup = null

  const mod = currentModule()
  const data = state.analytics

  if (mod.key === 'map') {
    renderEchartsWorldMap(document.getElementById('intel-chart-map'), data.mapPoints).then((cleanup) => {
      state.mapCleanup = cleanup
    })
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
  } else if (mod.key === 'relation') {
    renderDisasterRelationNetwork(
      document.getElementById('intel-chart-relation'),
      data.relationNetwork,
    ).then((cleanup) => {
      state.relationCleanup = cleanup
    })
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
      state.relationCleanup?.()
      state.relationCleanup = null
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
  state.relationCleanup?.()
  state.relationCleanup = null
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
