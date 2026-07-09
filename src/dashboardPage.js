import { fetchDashboardOverview, formatDashboardNumber, clearDashboardCache } from './dashboardData.js'
import { dashboardCache } from './disasterStatsApi.js'
import { SESSION_KEY } from './auth.js'
import { destroyDashboardGlobe, initDashboardGlobe } from './dashboardGlobe.js'

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

export function destroySituationDashboard() {
  destroyDashboardGlobe()
}

function renderMetric(label, value, { warn = false } = {}) {
  return `
    <article class="situation-home-metric${warn ? ' situation-home-metric--warn' : ''}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `
}

function renderStats(overview) {
  if (overview?.sectionErrors?.dashboardStats) {
    return '<p class="situation-home-error">&gt; dashboard_stats 同步失败，请稍后重试。</p>'
  }

  return `
    <div class="situation-home-stats" aria-label="数据库统计摘要">
      ${renderMetric('当前档案数量', formatDashboardNumber(overview.totalEvents))}
      ${renderMetric('覆盖国家 / 地区数量', formatDashboardNumber(overview.countryCount))}
      ${renderMetric('重大灾害数量', formatDashboardNumber(overview.criticalCount), { warn: true })}
      ${renderMetric('数据库最后同步时间', overview.lastSync || '--')}
    </div>
  `
}

function renderTerminalMenu() {
  return `
    <nav class="situation-home-menu" aria-label="功能入口菜单">
      <button type="button" class="situation-home-menu__item" data-route="query">
        <span>&gt;</span> 灾害事件查询
      </button>
      <button type="button" class="situation-home-menu__item" data-route="analytics">
        <span>&gt;</span> 数据分析中心
      </button>
      <button type="button" class="situation-home-menu__item" data-route="knowledge">
        <span>&gt;</span> 灾害知识库
      </button>
      <button type="button" class="situation-home-menu__item situation-home-menu__item--warn" id="dashboard-logout-btn">
        <span>&gt;</span> 退出登录
      </button>
    </nav>
  `
}

function renderVisualPanel() {
  return `
    <section class="situation-home-visual" aria-label="全球灾害档案主视觉">
      <div class="situation-home-visual__kicker">
        <span>GLOBAL REPORT</span>
        <em>/ 世界灾害总览</em>
      </div>
      <div class="situation-home-map-visual" aria-hidden="true" id="dashboard-globe-visual">
        <p class="situation-home-map-visual__fallback">&gt; INITIALIZING_ARCHIVE_GLOBE...</p>
      </div>
      <div class="situation-home-visual__footer">
        <span>[ARCHIVE_GLOBE: ONLINE]</span>
        <span>[EM-DAT SOURCE]</span>
      </div>
    </section>
  `
}

function renderInfoPanel(overview) {
  return `
    <aside class="situation-home-info" aria-label="系统说明与功能入口">
      <p class="situation-home-terminal-line">&gt; CRISIS_DATA / SYSTEM_INTRODUCTION</p>
      <h1>GLOBAL DISASTER EVENT DATABASE</h1>
      <h2>全球灾害事件数字档案系统</h2>
      <p class="situation-home-copy">
        本系统基于 EM-DAT 国际灾害数据库，记录全球范围内国家层面的灾害事件，包含人员伤亡、受影响人数、经济损失、灾害类型与发生时间等信息。
      </p>
      <div class="situation-home-rules">
        <p>收录事件需至少满足以下条件之一：</p>
        <ul>
          <li>死亡人数 ≥ 10 人</li>
          <li>受影响人数 ≥ 100 人</li>
          <li>宣布进入紧急状态</li>
          <li>呼吁国际社会提供援助</li>
        </ul>
      </div>
      ${renderStats(overview)}
      <p class="situation-home-ai-status">
        <strong>SYSTEM READY</strong>
        <span>数据库连接正常，等待用户指令。</span>
      </p>
      ${renderTerminalMenu()}
    </aside>
  `
}

export function renderSituationDashboard() {
  if (state.loading) {
    return `
      <section class="vault-console vault-console--subpage" aria-label="世界灾害总览">
        <div class="situation-dashboard situation-dashboard--home">
          <p class="situation-loading">&gt; 正在同步灾害数据库...</p>
        </div>
      </section>
    `
  }

  if (state.error) {
    return `
      <section class="vault-console vault-console--subpage" aria-label="世界灾害总览">
        <div class="situation-dashboard situation-dashboard--home">
          <div class="situation-dashboard__body">
            <p class="situation-error">&gt; [错误] ${escapeHtml(state.error)}</p>
            <nav class="situation-dashboard__nav-dock situation-dashboard__nav-dock--inline">
              <button type="button" class="situation-nav-btn" id="dashboard-retry-btn">[ 重新同步 ]</button>
            </nav>
          </div>
        </div>
      </section>
    `
  }

  return `
    <section class="vault-console vault-console--subpage" aria-label="世界灾害总览">
      <div class="situation-dashboard situation-dashboard--home">
        <div class="situation-home-shell">
          <header class="situation-home-frame">
            <span>[CRISIS_DATA / ARCHIVE_SYSTEM]</span>
            <i></i>
            <span>[PROFILE: COMPLETE]</span>
          </header>
          <div class="situation-home-layout">
            ${renderVisualPanel()}
            ${renderInfoPanel(state.overview)}
          </div>
          <footer class="situation-home-frame situation-home-frame--footer">
            <span>[CIVILIZATION_ENGINE: ONLINE]</span>
            <span>[RECORD: PERMANENT]</span>
          </footer>
        </div>
      </div>
    </section>
  `
}

function bindDashboardActions() {
  document.getElementById('dashboard-logout-btn')?.addEventListener('click', () => {
    sessionStorage.removeItem(SESSION_KEY)
    state.onLogout?.()
  })

  document.getElementById('dashboard-retry-btn')?.addEventListener('click', () => {
    clearDashboardCache()
    loadOverview({ force: true })
  })

  document.querySelectorAll('.situation-dashboard [data-route]').forEach((button) => {
    button.addEventListener('click', () => {
      state.onNavigate?.(button.dataset.route)
    })
  })

  initDashboardGlobe(document.getElementById('dashboard-globe-visual'))
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
}

function rerender() {
  const app = document.getElementById('app')
  if (!app) return
  destroyDashboardGlobe()
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
