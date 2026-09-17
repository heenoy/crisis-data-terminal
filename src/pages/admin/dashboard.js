import { fetchAdminDashboardStats } from '../../services/adminStats.js'

const EMPTY_STATS = {
  disasterCount: '---',
  userCount: '---',
  databaseStatus: 'CHECKING',
}

let state = { ...EMPTY_STATS }
let onNavigate = null
let onLogout = null

function logLine(label, value, id, modifier = '') {
  return `
    <p class="admin-boot-log__line ${modifier}">
      <span class="admin-boot-log__prompt">&gt;</span>
      <span class="admin-boot-log__label">${label}</span>
      <strong id="${id}">${value}</strong>
    </p>
  `
}

function moduleEntry(route, code, label, secondary = false, status = 'READY') {
  return `
    <button
      type="button"
      class="admin-module-entry ${secondary ? 'admin-module-entry--secondary' : ''}"
      data-route="${route}"
    >
      <span class="admin-module-entry__cursor" aria-hidden="true">&gt;</span>
      <span class="admin-module-entry__content">
        <strong>[ ${code} ]</strong>
        <em>${label}</em>
      </span>
      <span class="admin-module-entry__status" aria-hidden="true">${status}</span>
    </button>
  `
}

export function renderAdminDashboard() {
  return `
    <section class="vault-console vault-console--subpage" aria-label="Admin Portal Dashboard">
      <div class="admin-portal">
        <header class="admin-portal__header">
          <div>
            <p class="vault-kicker">[ ADMIN_PORTAL / SYSTEM CONTROL ]</p>
            <h1>VAULT-0 ADMIN CONTROL<span class="admin-terminal-cursor" aria-hidden="true">_</span></h1>
            <p>SYSTEM ADMINISTRATION TERMINAL</p>
          </div>
          <button type="button" class="admin-portal__logout" data-admin-action="logout">[ SIGN OUT ]</button>
        </header>

        <section class="admin-boot-log" aria-label="系统启动日志">
          <h2>[ SYSTEM BOOT LOG ]</h2>
          <div class="admin-boot-log__output">
            ${logLine('DATABASE', state.databaseStatus, 'admin-database-status', 'admin-boot-log__line--status')}
            ${logLine('DISASTER RECORDS :', state.disasterCount, 'admin-disaster-count')}
            ${logLine('REGISTERED USERS :', state.userCount, 'admin-user-count')}
            ${logLine('STORAGE STATUS :', state.databaseStatus === 'CONNECTED' ? 'ONLINE' : 'CHECKING', 'admin-storage-status')}
            ${logLine('LAST SYNC :', '---- -- --  --:--:--', 'admin-last-sync')}
          </div>
        </section>

        <nav class="admin-module-grid" aria-label="管理模块">
          <h2>[ ADMIN MODULE ]</h2>
          ${moduleEntry('admin/disasters', 'DISASTER DATA', '灾害数据管理')}
          ${moduleEntry('admin/users', 'USER CONTROL', '用户管理')}
          ${moduleEntry('admin/system', 'SYSTEM STATUS', '系统状态', false, 'ON DEMAND')}
          ${moduleEntry('admin/models', 'MODEL CONTROL', '模型管理')}
          ${moduleEntry('user/overview', 'DISASTER OVERVIEW', '世界灾害总览', true)}
        </nav>
      </div>
    </section>
  `
}

function animateTerminalValue(element, value) {
  if (!element) return

  const text = String(value)
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    element.textContent = text
    return
  }

  element.textContent = ''
  let index = 0
  const timer = window.setInterval(() => {
    index += 1
    element.textContent = text.slice(0, index)
    if (index >= text.length) window.clearInterval(timer)
  }, 42)
}

function updateStats(stats) {
  state = stats
  const disasterCount = document.getElementById('admin-disaster-count')
  const userCount = document.getElementById('admin-user-count')
  const databaseStatus = document.getElementById('admin-database-status')
  const storageStatus = document.getElementById('admin-storage-status')
  const lastSync = document.getElementById('admin-last-sync')

  animateTerminalValue(disasterCount, stats.disasterCount)
  animateTerminalValue(userCount, stats.userCount)
  animateTerminalValue(databaseStatus, stats.databaseStatus)
  animateTerminalValue(storageStatus, stats.databaseStatus === 'CONNECTED' ? 'ONLINE' : 'UNAVAILABLE')
  animateTerminalValue(lastSync, new Date().toLocaleString('zh-CN', { hour12: false }))

  if (databaseStatus) {
    databaseStatus.classList.toggle('is-unavailable', stats.databaseStatus !== 'CONNECTED')
  }
  storageStatus?.classList.toggle('is-unavailable', stats.databaseStatus !== 'CONNECTED')
}

export async function initAdminDashboard({ onNavigate: navigate, onLogout: logout }) {
  onNavigate = navigate
  onLogout = logout

  document.querySelectorAll('.admin-module-grid [data-route]').forEach((button) => {
    button.addEventListener('click', () => onNavigate?.(button.dataset.route))
  })
  document.querySelector('[data-admin-action="logout"]')?.addEventListener('click', () => onLogout?.())

  updateStats(await fetchAdminDashboardStats())
}

export function resetAdminDashboard() {
  state = { ...EMPTY_STATS }
  onNavigate = null
  onLogout = null
}
