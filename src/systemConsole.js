import { bindAuthPage, renderAuthPage } from './authPage.js'
import { bindDisasterDashboard, renderDisasterDashboard } from './disasterEventsPage.js'
import { initAnalyticsPage, renderAnalyticsPage } from './disasterAnalyticsPage.js'
import { initSituationDashboard } from './dashboardPage.js'
import { initKnowledgePage } from './disasterKnowledgePage.js'
import { bindTerminalNavigation } from './terminalNav.js'

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

function renderAuthenticatedHomeScreen() {
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
          label: '灾害知识库',
          subtitle: 'DISASTER KNOWLEDGE BASE',
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

function renderHomeScreen({ isLoggedIn }) {
  return isLoggedIn ? renderAuthenticatedHomeScreen() : renderGuestHomeScreen()
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
          label: '灾害知识库',
          subtitle: 'DISASTER KNOWLEDGE BASE',
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

  const pages = {
    start: () => renderHomeScreen({ isLoggedIn }),
    auth: renderAuthPage,
    dashboard: () => `
      <section class="vault-console vault-console--subpage" aria-label="灾害事件总览">
        <div class="situation-dashboard">
          <p class="situation-loading">&gt; 正在同步灾害数据库…</p>
        </div>
      </section>
    `,
    query: () => renderDisasterDashboard({ user, mode: 'console' }),
    analytics: () => renderAnalyticsPage(),
    situation: () => renderAnalyticsPage(),
    knowledge: () => `
      <section class="vault-console vault-console--subpage" aria-label="灾害知识库">
        <p class="situation-loading">&gt; 正在加载参考资料库…</p>
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
      onSuccess: () => onNavigate('dashboard'),
      onBack: () => onNavigate('start'),
    })
    return
  }

  if (route === 'dashboard') {
    initSituationDashboard({ onNavigate, onLogout })
    return
  }

  if (route === 'query') {
    bindDisasterDashboard({ user, onNavigate, mode: 'console' })
    bindTerminalNavigation({ onNavigate, root: app })
    return
  }

  if (route === 'analytics' || route === 'situation') {
    initAnalyticsPage({ onNavigate })
    bindTerminalNavigation({ onNavigate, root: app })
    return
  }

  if (route === 'knowledge') {
    initKnowledgePage({ onNavigate })
  }
}
