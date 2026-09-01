import { bindAuthPage, renderAuthPage } from './authPage.js'
import { bindTerminalNavigation } from './terminalNav.js'
import { mountBreadcrumbs } from './components/breadcrumbs.js'
import { ROUTES } from './router/routes.js'
import { destroyUserOverview, initUserOverview, renderUserOverview } from './pages/user/overview.js'
import { initUserSearch, renderUserSearch } from './pages/user/search.js'
import { initUserAnalysis, renderUserAnalysis } from './pages/user/analysis.js'
import { initImpactAnalysis, renderImpactAnalysis } from './pages/user/impactAnalysis.js'
import { destroyUserAiInquiry, initUserAiInquiry } from './pages/user/aiInquiry.js'
import { initAdminDashboard, renderAdminDashboard, resetAdminDashboard } from './pages/admin/dashboard.js'
import { initAdminDisasterManage, renderAdminDisasterManage } from './pages/admin/disasterManage.js'
import { initAdminUserManage, renderAdminUserManage } from './pages/admin/userManage.js'
import { initAdminSystemMonitor, renderAdminSystemMonitor } from './pages/admin/systemMonitor.js'
import { initAdminModelManage, renderAdminModelManage } from './pages/admin/modelManage.js'

const BRAND_SUBTITLE = 'CRISIS DATA TERMINAL / 灾害事件智能分析终端 · Disaster Intelligence Terminal'

const AUTHENTICATED_MENU_GROUPS = [
  {
    label: 'DATA SERVICES',
    items: [
      { action: 'dashboard', label: '世界灾害总览', subtitle: 'GLOBAL DISASTER OVERVIEW', primary: true },
      { action: 'query', label: '灾害事件查询', subtitle: 'DISASTER QUERY' },
      { action: 'analytics', label: '数据分析中心', subtitle: 'DATA ANALYTICS' },
      { action: 'impact-analysis', label: '灾害影响等级预测', subtitle: 'IMPACT LEVEL PREDICTION' },
      { action: 'knowledge', label: 'AI 灾害问询', subtitle: 'AI CRISIS INQUIRY' },
    ],
  },
  {
    label: 'ADMINISTRATION',
    roles: ['admin'],
    items: [
      { action: 'admin-dashboard', label: '管理控制台', subtitle: 'ADMIN CONSOLE' },
    ],
  },
  {
    label: 'SESSION',
    items: [
      { action: 'logout', label: '退出登录', subtitle: 'SIGN OUT' },
    ],
  },
]

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

function renderHomeMenuGroup(group, user) {
  if (group.roles && !group.roles.includes(user?.role)) return ''
  return `
    <section class="vault-home-menu-group" aria-labelledby="menu-group-${group.label.toLowerCase()}">
      <h2 id="menu-group-${group.label.toLowerCase()}" class="vault-home-menu-group__label">[ ${group.label} ]</h2>
      <div class="vault-home-menu-group__items">
        ${group.items.map(renderHomeMenuItem).join('')}
      </div>
    </section>
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
        ${AUTHENTICATED_MENU_GROUPS.map((group) => renderHomeMenuGroup(group, user)).join('')}
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
  const buttons = [...document.querySelectorAll('[data-menu-action]:not([data-locked="true"])')]
  let activeIndex = Math.max(0, buttons.findIndex((button) => button.classList.contains('vault-home-item--primary')))

  const setActive = (index, { focus = false } = {}) => {
    activeIndex = (index + buttons.length) % buttons.length
    buttons.forEach((button, buttonIndex) => {
      const isActive = buttonIndex === activeIndex
      button.classList.toggle('vault-home-item--active', isActive)
      button.classList.toggle('vault-home-item--primary', isActive)
    })
    if (focus) buttons[activeIndex]?.focus()
  }

  buttons.forEach((button, index) => {
    button.addEventListener('focus', () => setActive(index))
    button.addEventListener('click', () => {
      const action = button.dataset.menuAction
      onMenuAction?.(action)
    })
  })

  document.querySelector('.vault-home-menu')?.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    setActive(activeIndex + (event.key === 'ArrowDown' ? 1 : -1), { focus: true })
  })

  setActive(activeIndex)
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
    [ROUTES.USER_IMPACT_ANALYSIS]: () => renderImpactAnalysis(),
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
  mountBreadcrumbs({ root: app, route, onNavigate })

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

  if (route === ROUTES.USER_IMPACT_ANALYSIS) {
    initImpactAnalysis({ onNavigate })
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
