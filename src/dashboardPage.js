import { fetchDashboardOverview, formatDashboardNumber, clearDashboardCache } from './dashboardData.js'
import { dashboardCache } from './disasterStatsApi.js'
import { refreshAiSummaryBubble } from './aiSummaryBubble.js'
import { renderBackToMainMenu } from './terminalNav.js'

let state = {
  loading: true,
  error: null,
  overview: null,
  onNavigate: null,
  onLogout: null,
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderSectionError(sectionKey, overview) {
  if (!overview?.sectionErrors?.[sectionKey]) return ''
  return '<p class="situation-section-error">&gt; 该模块同步失败，请稍后重试。</p>'
}

function renderMetrics(summary) {
  if (summary.sectionErrors?.dashboardStats) {
    return `<div class="situation-metrics">${renderSectionError('dashboardStats', summary)}</div>`
  }
  return `
    <div class="situation-metrics">
      <article class="situation-metric">
        <span>灾害事件总数</span>
        <strong>${formatDashboardNumber(summary.totalEvents)}</strong>
      </article>
      <article class="situation-metric">
        <span>涉及国家数量</span>
        <strong>${formatDashboardNumber(summary.countryCount)}</strong>
      </article>
      <article class="situation-metric situation-metric--alert">
        <span>重大灾害数量</span>
        <strong>${formatDashboardNumber(summary.criticalCount)}</strong>
      </article>
      <article class="situation-metric">
        <span>总受影响人数</span>
        <strong>${formatDashboardNumber(summary.totalAffected)}</strong>
      </article>
      <article class="situation-metric">
        <span>总死亡人数</span>
        <strong>${formatDashboardNumber(summary.totalCasualties)}</strong>
      </article>
    </div>
  `
}

function renderGlobalSummaryPanel(summary) {
  return `
    <section class="situation-panel situation-panel--summary" aria-label="全球灾害事件摘要">
      <h3>[ GLOBAL SUMMARY / 全球灾害事件摘要 ]</h3>
      <div class="situation-summary-grid">
        <article class="situation-summary-card">
          <span class="situation-summary-card__label">受灾最严重地区</span>
          <strong class="situation-summary-card__value">${escapeHtml(summary.topAffectedCountry || '--')}</strong>
          <span class="situation-summary-card__hint">累计受影响 ${formatDashboardNumber(summary.topAffectedPopulation)}</span>
        </article>
        <article class="situation-summary-card">
          <span class="situation-summary-card__label">灾害数量最多类型</span>
          <strong class="situation-summary-card__value">${escapeHtml(summary.topTypeLabel || '--')}</strong>
        </article>
        <article class="situation-summary-card situation-summary-card--alert">
          <span class="situation-summary-card__label">重大灾害数量</span>
          <strong class="situation-summary-card__value">${formatDashboardNumber(summary.criticalCount)}</strong>
        </article>
        <article class="situation-summary-card">
          <span class="situation-summary-card__label">数据库最后同步</span>
          <strong class="situation-summary-card__value situation-summary-card__value--mono">${escapeHtml(summary.lastSync)}</strong>
        </article>
      </div>
    </section>
  `
}

function renderTypeBars(rows, overview) {
  if (overview?.sectionErrors?.disasterTypeStats) {
    return renderSectionError('disasterTypeStats', overview)
  }
  if (!rows?.length) {
    return '<p class="situation-panel-empty">暂无类型分布数据</p>'
  }

  const visible = rows.filter((row) => row.count > 0)
  const explicit = visible
    .filter((row) => row.key !== 'other')
    .sort((a, b) => b.count - a.count)
  const otherRow = visible.find((row) => row.key === 'other')
  const ordered = otherRow ? [...explicit, otherRow] : explicit
  const scaleMax = Math.max(...explicit.map((r) => r.count), 1)

  return `
    <div class="situation-type-bars">
      ${ordered
        .map((row) => {
          const isOther = row.key === 'other'
          const width = isOther
            ? Math.min(100, Math.max(2, (row.count / scaleMax) * 100))
            : Math.max(2, (row.count / scaleMax) * 100)
          const barClass = isOther ? ' situation-type-bar--unclassified' : ''
          return `
        <div class="situation-type-bar${barClass}">
          <span class="situation-type-bar__label">${escapeHtml(row.label)}</span>
          <div class="situation-type-bar__track">
            <div class="situation-type-bar__fill" style="width:${width}%"></div>
          </div>
          <strong>${formatDashboardNumber(row.count)}</strong>
        </div>
      `
        })
        .join('')}
    </div>
  `
}

function renderLatestEvents(events, overview) {
  if (overview?.sectionErrors?.latestEvents) {
    return renderSectionError('latestEvents', overview)
  }
  if (!events?.length) {
    return '<p class="situation-panel-empty">暂无最新事件记录</p>'
  }

  return `
    <ul class="situation-latest-list">
      ${events
        .map(
          (row) => `
        <li class="situation-latest-list__item">
          <span class="situation-latest-list__date">${escapeHtml(row.date)}</span>
          <span class="situation-latest-list__meta">${escapeHtml(row.type)} · ${escapeHtml(row.country)}</span>
          <strong class="situation-latest-list__title">${escapeHtml(row.title)}</strong>
        </li>
      `,
        )
        .join('')}
    </ul>
  `
}

function renderLiveFeed(events, overview) {
  if (overview?.sectionErrors?.latestEvents) {
    return renderSectionError('latestEvents', overview)
  }
  if (!events?.length) {
    return '<p class="situation-live-feed__empty">&gt; 暂无实时事件记录</p>'
  }

  return events
    .map((row) => {
      const alertClass =
        row.severity === 'critical' || row.severity === 'high'
          ? ` situation-feed-line--${row.severity}`
          : ''
      return `
    <article class="situation-feed-line${alertClass}">
      <p class="situation-feed-line__meta">
        <span class="situation-feed-line__prefix" aria-hidden="true">&gt;</span>
        [${escapeHtml(row.date)}] ${escapeHtml(row.type)} / ${escapeHtml(row.country)} / ${escapeHtml(row.severityLabel)}
      </p>
      <p class="situation-feed-line__title">${escapeHtml(row.title)}</p>
    </article>
  `
    })
    .join('')
}

function renderTopImpact(events, overview) {
  if (overview?.sectionErrors?.topImpactEvents) {
    return renderSectionError('topImpactEvents', overview)
  }
  if (!events?.length) {
    return '<p class="situation-panel-empty">暂无排行数据</p>'
  }

  return `
    <ol class="situation-top-list">
      ${events
        .map(
          (row, index) => `
        <li class="situation-top-list__item ${index === 0 ? 'situation-top-list__item--top' : ''}">
          <span class="situation-top-list__rank">#${index + 1}</span>
          <div class="situation-top-list__body">
            <strong>${escapeHtml(row.title)}</strong>
            <span>${escapeHtml(row.country)} · ${escapeHtml(row.type)}</span>
            <span>受影响人数：${formatDashboardNumber(row.affected)} · 死亡人数：${formatDashboardNumber(row.casualties)}</span>
          </div>
        </li>
      `,
        )
        .join('')}
    </ol>
  `
}

function renderSeverityBars(rows, overview) {
  if (overview?.sectionErrors?.severityStats) {
    return renderSectionError('severityStats', overview)
  }
  if (!rows?.length) {
    return '<p class="situation-panel-empty">暂无风险分布数据</p>'
  }

  const max = Math.max(...rows.map((r) => r.value), 1)
  return `
    <div class="situation-severity-bars">
      ${rows
        .map((row) => {
          const width = Math.max(2, (row.value / max) * 100)
          const alertClass = row.key === 'critical' || row.key === 'high' ? ` situation-severity-bar--${row.key}` : ''
          return `
        <div class="situation-severity-bar${alertClass}">
          <span class="situation-severity-bar__label">${escapeHtml(row.label)}</span>
          <div class="situation-severity-bar__track">
            <div class="situation-severity-bar__fill" style="width:${width}%"></div>
          </div>
          <strong>${formatDashboardNumber(row.value)}</strong>
        </div>
      `
        })
        .join('')}
    </div>
  `
}

function renderNavDock() {
  return `
    <nav class="situation-dashboard__nav-dock" aria-label="Dashboard navigation">
      <div class="situation-dashboard__nav-group situation-dashboard__nav-group--primary">
        <button type="button" class="situation-nav-btn" data-route="query">→ 灾害事件查询</button>
        <button type="button" class="situation-nav-btn" data-route="analytics">→ 数据分析中心</button>
      </div>
      <div class="situation-dashboard__nav-group situation-dashboard__nav-group--secondary">
        <button type="button" class="situation-nav-btn" data-route="knowledge">[ 灾害知识库 ]</button>
        <button type="button" class="situation-nav-btn situation-nav-btn--warn" id="dashboard-logout-btn">[ 退出登录 ]</button>
      </div>
    </nav>
  `
}

export function renderSituationDashboard() {
  if (state.loading) {
    return `
      <section class="vault-console vault-console--subpage" aria-label="灾害事件总览">
        <div class="situation-dashboard">
          <div class="situation-dashboard__body">
            <p class="situation-loading">&gt; 正在同步灾害数据库…</p>
          </div>
        </div>
      </section>
    `
  }

  if (state.error) {
    return `
      <section class="vault-console vault-console--subpage" aria-label="灾害事件总览">
        <div class="situation-dashboard">
          <div class="situation-dashboard__body">
            ${renderBackToMainMenu()}
            <p class="situation-error">&gt; [错误] ${escapeHtml(state.error)}</p>
            <div class="situation-dashboard__nav-dock situation-dashboard__nav-dock--inline">
              <button type="button" class="situation-nav-btn" id="dashboard-retry-btn">[ 重新同步 ]</button>
            </div>
          </div>
        </div>
      </section>
    `
  }

  const o = state.overview

  return `
    <section class="vault-console vault-console--subpage" aria-label="灾害事件总览">
      <div class="situation-dashboard">
        <div class="situation-dashboard__body">
          ${renderBackToMainMenu()}

          <header class="situation-dashboard__hero">
            <h1>GLOBAL DISASTER EVENT DATABASE</h1>
            <h2>灾害事件总览</h2>
            <p class="situation-dashboard__tagline">全球灾害事件数据库 · 实时统计与档案监测</p>
            <div class="situation-dashboard__status">
              <span>系统状态：<strong>${escapeHtml(o.systemStatus)}</strong></span>
              <span>数据库状态：<strong>${escapeHtml(o.databaseStatus)}</strong></span>
            </div>
          </header>

          <div class="situation-dashboard__stack">
            ${renderMetrics(o)}
            ${renderGlobalSummaryPanel(o)}

            <div class="situation-distribution-layout">
              <section class="situation-panel situation-panel--distribution">
                <h3>[ DISASTER TYPE / 灾害类型分布 ]</h3>
                ${renderTypeBars(o.typeOverview, o)}
              </section>
              <section class="situation-panel situation-panel--distribution">
                <h3>[ RISK LEVEL / 风险等级分布 ]</h3>
                ${renderSeverityBars(o.severityDistribution, o)}
              </section>
            </div>

            <div class="situation-content-layout">
              <section class="situation-panel situation-panel--events">
                <h3>[ LATEST EVENTS / 最新灾害事件 ]</h3>
                ${renderLatestEvents(o.latestEvents, o)}
              </section>

              <div class="situation-content-layout__side">
                <section class="situation-panel">
                  <h3>[ TOP IMPACT / 影响最大事件 Top 5 ]</h3>
                  ${renderTopImpact(o.topImpact, o)}
                </section>
                <section class="situation-panel situation-live-feed" aria-label="实时事件流">
                  <h3>[ LIVE FEED / 实时事件流 ]</h3>
                  <div class="situation-live-feed__stream">
                    ${renderLiveFeed(o.liveFeed, o)}
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>

        ${renderNavDock()}
      </div>
    </section>
  `
}

function bindDashboardActions() {
  document.getElementById('dashboard-logout-btn')?.addEventListener('click', () => {
    state.onLogout?.()
  })

  document.getElementById('dashboard-retry-btn')?.addEventListener('click', () => {
    clearDashboardCache()
    loadOverview({ force: true })
  })

  document.querySelectorAll('.situation-dashboard [data-route]').forEach((button) => {
    button.addEventListener('click', () => state.onNavigate?.(button.dataset.route))
  })
}

async function loadOverview({ force = false } = {}) {
  if (force) clearDashboardCache()

  if (!force && dashboardCache) {
    const { overview } = await fetchDashboardOverview({ force: false })
    if (overview) {
      state.loading = false
      state.error = null
      state.overview = overview
      rerender()
      refreshAiSummaryBubble()
      return
    }
  }

  state.loading = true
  state.error = null
  state.overview = null
  rerender()

  const { overview, error } = await fetchDashboardOverview({ force })

  if (error) {
    state.loading = false
    state.error = error.message || '灾害数据加载失败'
    state.overview = null
    rerender()
    return
  }

  state.loading = false
  state.error = null
  state.overview = overview
  rerender()
  if (!state.loading && !state.error) {
    refreshAiSummaryBubble()
  }
}

function rerender() {
  const app = document.getElementById('app')
  if (!app) return
  app.innerHTML = renderSituationDashboard()
  bindDashboardActions()
}

export async function initSituationDashboard({ onNavigate, onLogout }) {
  state.onNavigate = onNavigate
  state.onLogout = onLogout
  await loadOverview()
}

export function bindSituationDashboard({ onNavigate, onLogout }) {
  state.onNavigate = onNavigate
  state.onLogout = onLogout
  bindDashboardActions()
}
