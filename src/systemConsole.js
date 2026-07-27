import { bindAuthPage, renderAuthPage } from './authPage.js'
import { bindTerminalNavigation } from './terminalNav.js'
import { ROUTES } from './router/routes.js'
import { destroyUserOverview, initUserOverview, renderUserOverview } from './pages/user/overview.js'
import { initUserSearch, renderUserSearch } from './pages/user/search.js'
import { initUserAnalysis, renderUserAnalysis } from './pages/user/analysis.js'
import { destroyUserAiInquiry, initUserAiInquiry } from './pages/user/aiInquiry.js'
import { initAdminDashboard, renderAdminDashboard, resetAdminDashboard } from './pages/admin/dashboard.js'
import { initAdminDisasterManage, renderAdminDisasterManage } from './pages/admin/disasterManage.js'
import { initAdminUserManage, renderAdminUserManage } from './pages/admin/userManage.js'
import { initAdminSystemMonitor, renderAdminSystemMonitor } from './pages/admin/systemMonitor.js'
import { initAdminModelManage, renderAdminModelManage } from './pages/admin/modelManage.js'

const BRAND_SUBTITLE = 'CRISIS DATA TERMINAL / 应急灾害监测终端 · Disaster Event Monitor'

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderHomeMenuItem({ action, label, subtitle, primary = false, locked = false }) {
  return `
    <button
      type="button"
      class="vault-home-item ${primary ? 'vault-home-item--primary' : ''} ${locked ? 'is-locked' : ''}"
      data-menu-action="${action}"
      ${locked ? 'data-locked="true" aria-disabled="true"' : ''}
    >
      <span class="vault-menu-cursor" aria-hidden="true">&gt;</span>
      <strong>${escapeHtml(label)}</strong>
      <em>${escapeHtml(subtitle)}</em>
      ${locked ? '<span class="vault-menu-lock">LOCKED</span>' : ''}
    </button>
  `
}

function renderAuthenticatedHomeScreen(user) {
  const body = `
    <div class="vault-home-screen">
      <div class="vault-home-topline" aria-label="terminal header">
        <span>[CRISIS DATA TERMINAL]</span>
        <span>STATUS: ONLINE</span>
        <span>SIGNAL: SECURE</span>
      </div>

      <div class="vault-home-titlebar">
        <div class="vault-brand-block">
          <div class="vault-brand-row">
            <h1 class="vault-logo" aria-label="VAULT-0">
              <span class="vault-logo-main">VAULT</span><span class="vault-logo-model">-0</span>
            </h1>
            <div class="vault-title-face-slot" data-ai-face-slot></div>
          </div>
          <p>${BRAND_SUBTITLE}</p>
        </div>
      </div>

      <main class="vault-home-menu" aria-label="Crisis Data Terminal menu">
        ${
          user?.role === 'admin'
            ? renderHomeMenuItem({
                action: 'admin-dashboard',
                label: '管理控制台',
                subtitle: 'ADMIN PORTAL',
                primary: true,
              })
            : ''
        }
        ${renderHomeMenuItem({
          action: 'dashboard',
          label: '灾害事件总览',
          subtitle: 'DISASTER EVENT OVERVIEW',
          primary: true,
        })}
        ${renderHomeMenuItem({
          action: 'query',
          label: '灾害事件查询',
          subtitle: 'DISASTER QUERY',
        })}
        ${renderHomeMenuItem({
          action: 'analytics',
          label: '数据分析中心',
          subtitle: 'DATA ANALYTICS',
        })}
        ${renderHomeMenuItem({
          action: 'knowledge',
          label: 'AI 灾害问询',
          subtitle: 'AI CRISIS INQUIRY',
        })}
        ${renderHomeMenuItem({
          action: 'logout',
          label: '退出登录',
          subtitle: 'SIGN OUT',
        })}
      </main>

      <aside class="vault-home-status" aria-label="terminal status">
        <span>SESSION ACTIVE / MONITOR ONLINE</span>
        <span>SYSTEM ONLINE / SIGNAL: SECURE</span>
      </aside>
    </div>
  `

  return `
    <section class="vault-console" aria-label="Crisis Data Terminal">
      ${body}
    </section>
  `
}

function renderHomeScreen({ isLoggedIn, user }) {
  return isLoggedIn ? renderAuthenticatedHomeScreen(user) : renderGuestHomeScreen()
}

function renderGuestHomeScreen() {
  const body = `
    <div class="vault-home-screen">
      <div class="vault-home-topline" aria-label="terminal header">
        <span>[CRISIS DATA TERMINAL]</span>
        <span>STATUS: STANDBY</span>
        <span>SIGNAL: STABLE</span>
      </div>

      <div class="vault-home-titlebar">
        <div class="vault-brand-block">
          <div class="vault-brand-row">
            <h1 class="vault-logo" aria-label="VAULT-0">
              <span class="vault-logo-main">VAULT</span><span class="vault-logo-model">-0</span>
            </h1>
            <div class="vault-title-face-slot" data-ai-face-slot></div>
          </div>
          <p>${BRAND_SUBTITLE}</p>
        </div>
      </div>

      <main class="vault-home-menu" aria-label="Crisis Data Terminal menu">
        ${renderHomeMenuItem({
          action: 'login',
          label: '登录系统',
          subtitle: 'AUTH / LOGIN',
          primary: true,
        })}
        ${renderHomeMenuItem({
          action: 'query',
          label: '灾害事件查询',
          subtitle: 'DISASTER QUERY',
          locked: true,
        })}
        ${renderHomeMenuItem({
          action: 'analytics',
          label: '数据分析中心',
          subtitle: 'DATA ANALYTICS',
          locked: true,
        })}
        ${renderHomeMenuItem({
          action: 'knowledge',
          label: 'AI 灾害问询',
          subtitle: 'AI CRISIS INQUIRY',
          locked: true,
        })}
        ${renderHomeMenuItem({
          action: 'exit',
          label: '退出终端',
          subtitle: 'EXIT TERMINAL',
        })}
      </main>

      <aside class="vault-home-status" aria-label="terminal status">
        <span>AUTH REQUIRED / 请先登录系统</span>
        <span>SYSTEM ONLINE / SIGNAL: STABLE</span>
      </aside>
    </div>
  `

  return `
    <section class="vault-console" aria-label="Crisis Data Terminal">
      ${body}
    </section>
  `
}

export function bindHomeScreen({ onMenuAction, onAccessDenied }) {
  document.querySelectorAll('[data-menu-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.dataset.menuAction
      if (button.dataset.locked === 'true') {
        onAccessDenied?.()
        return
      }
      onMenuAction?.(action)
    })
  })
}

export function renderSystemPage({
  route,
  user,
  isLoggedIn,
  onNavigate,
  onMenuAction,
  onAccessDenied,
  onLogout,
}) {
  const app = document.getElementById('app')
  if (!app) return
  destroyUserOverview()
  destroyUserAiInquiry()
  resetAdminDashboard()

  const pages = {
    start: () => renderHomeScreen({ isLoggedIn, user }),
    auth: renderAuthPage,
    [ROUTES.USER_OVERVIEW]: () => renderUserOverview(),
    [ROUTES.USER_SEARCH]: () => renderUserSearch(user),
    [ROUTES.USER_ANALYSIS]: () => renderUserAnalysis(),
    [ROUTES.USER_AI_INQUIRY]: () => `
      <section class="vault-console vault-console--subpage" aria-label="AI 灾害问询终端">
        <p class="situation-loading">&gt; 正在加载 AI 灾害问询终端...</p>
      </section>
    `,
    [ROUTES.ADMIN_DASHBOARD]: () => renderAdminDashboard(),
    [ROUTES.ADMIN_DISASTERS]: () => renderAdminDisasterManage(user),
    [ROUTES.ADMIN_USERS]: () => renderAdminUserManage(),
    [ROUTES.ADMIN_SYSTEM]: () => renderAdminSystemMonitor(),
    [ROUTES.ADMIN_MODELS]: () => renderAdminModelManage(),
    dashboard: () => `
      <section class="vault-console vault-console--subpage" aria-label="灾害事件总览">
        <div class="situation-dashboard">
          <p class="situation-loading">&gt; 正在同步灾害数据库…</p>
        </div>
      </section>
    `,
    knowledge: () => `
      <section class="vault-console vault-console--subpage" aria-label="AI 灾害问询终端">
        <p class="situation-loading">&gt; 正在加载 AI 灾害问询终端...</p>
      </section>
    `,
  }

  app.style.display = 'block'
  app.innerHTML = (pages[route] || pages.start)()

  if (route === 'start') {
    bindHomeScreen({ onMenuAction, onAccessDenied })
    return
  }

  if (route === 'auth') {
    bindAuthPage({
      onSuccess: () => onNavigate(ROUTES.AUTH),
      onBack: () => onNavigate('start'),
    })
    return
  }

  if (route === ROUTES.USER_OVERVIEW) {
    initUserOverview({ onNavigate, onLogout })
    return
  }

  if (route === ROUTES.USER_SEARCH) {
    initUserSearch({ user, onNavigate })
    bindTerminalNavigation({ onNavigate, root: app })
    return
  }

  if (route === ROUTES.USER_ANALYSIS) {
    initUserAnalysis({ onNavigate })
    bindTerminalNavigation({ onNavigate, root: app })
    return
  }

  if (route === ROUTES.USER_AI_INQUIRY) {
    initUserAiInquiry({ onNavigate })
    return
  }

  if (route === ROUTES.ADMIN_DASHBOARD) {
    initAdminDashboard({ onNavigate, onLogout })
    return
  }

  if (route === ROUTES.ADMIN_DISASTERS) {
    initAdminDisasterManage({ user, onNavigate })
    bindTerminalNavigation({ onNavigate, root: app })
    return
  }

  if (route === ROUTES.ADMIN_USERS) {
    initAdminUserManage(onNavigate)
    return
  }

  if (route === ROUTES.ADMIN_SYSTEM) {
    initAdminSystemMonitor(onNavigate)
    return
  }

  if (route === ROUTES.ADMIN_MODELS) {
    initAdminModelManage(onNavigate)
    return
  }

}
