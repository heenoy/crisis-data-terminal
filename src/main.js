import './style.css'
import './vaultTheme.css'
import './vaultTheme.js'
import './systemConsole.css'
import './survivorAuth.css'
import './disasterEvents.css'
import './disasterAnalytics.css'
import './dashboardPage.css'
import './disasterKnowledgePage.css'
import './aiFace.css'
import { runLaunchSequence } from './launchScreen.js'
import { ensureAudioContext, playGeigerClick } from './audio.js'
import {
  ensureFloatingAiMascot,
  initAiFaceEarly,
  notifyTypewriterEnd,
  notifyTypewriterStart,
} from './aiFace.js'
import { ensureAiSummaryBubble, hideAiSummaryBubble } from './aiSummaryBubble.js'
import { getCurrentUser, initAuth, isLoggedIn, refreshSessionUser, signOut, subscribeAuth } from './auth.js'
import { renderSystemPage } from './systemConsole.js'
import { showTerminalNotice } from './terminalNotice.js'
import {
  buildTerminalShell,
  delay,
  getTerminalContent,
  getTerminalViewport,
  stopCornerLog,
} from './terminal.js'

const PROGRESS_BAR_WIDTH = 30

const SCREEN_BAR_LABELS = {
  start: {
    tl: '[CRISIS DATA / STANDBY]',
    tr: '[ACCESS_GATE]',
    bl: '[SYSTEM: ONLINE]',
    br: '[AUTH: REQUIRED]',
  },
  auth: {
    tl: '[CRISIS DATA / ACCESS]',
    tr: '[LOGIN_TERMINAL]',
    bl: '[MODULE: ACTIVE]',
    br: '[ARCHIVE: READY]',
  },
  dashboard: {
    tl: '[CRISIS DATA / OVERVIEW]',
    tr: '[DISASTER EVENT DB]',
    bl: '[MONITOR: ACTIVE]',
    br: '[DB: CONNECTED]',
  },
  analytics: {
    tl: '[CRISIS DATA / ANALYTICS]',
    tr: '[DATA_VISUALIZATION]',
    bl: '[MODULE: ACTIVE]',
    br: '[FEED: SYNCED]',
  },
  situation: {
    tl: '[CRISIS DATA / ANALYTICS]',
    tr: '[DATA_VISUALIZATION]',
    bl: '[MODULE: ACTIVE]',
    br: '[FEED: SYNCED]',
  },
  query: {
    tl: '[CRISIS DATA / QUERY]',
    tr: '[RECORD_SEARCH]',
    bl: '[MODULE: STANDBY]',
    br: '[PHASE_01]',
  },
  archive: {
    tl: '[CRISIS DATA / ARCHIVE]',
    tr: '[DISASTER_RECORDS]',
    bl: '[MODULE: STANDBY]',
    br: '[PHASE_01]',
  },
  knowledge: {
    tl: '[CRISIS DATA / REFERENCE]',
    tr: '[DISASTER KNOWLEDGE BASE]',
    bl: '[MODULE: ACTIVE]',
    br: '[DB: CONNECTED]',
  },
  intro: {
    tl: '[CRISIS DATA]',
    tr: '[DISASTER_ARCHIVE]',
    bl: '[SYSTEM: ONLINE]',
    br: '[TERMINAL: READY]',
  },
}

const ROUTE_ALIASES = {
  '': 'start',
  start: 'start',
  auth: 'auth',
  login: 'auth',
  register: 'auth',
  dashboard: 'dashboard',
  home: 'dashboard',
  situation: 'analytics',
  status: 'analytics',
  analytics: 'analytics',
  analysis: 'analytics',
  query: 'query',
  archive: 'archive',
  docs: 'knowledge',
  documentation: 'knowledge',
  knowledge: 'knowledge',
}

const PUBLIC_ROUTES = new Set(['start', 'auth'])
const PROTECTED_ROUTES = new Set(['dashboard', 'query', 'analytics', 'archive', 'situation', 'knowledge'])
const MENU_ACTION_ROUTES = {
  login: 'auth',
  dashboard: 'dashboard',
  query: 'query',
  analytics: 'analytics',
  knowledge: 'knowledge',
  exit: null,
  logout: null,
}

let consoleAiFaceSpeakTimer = null
let hasCompletedBoot = false
let lastKnownUserId = null

function goFromStart() {
  handleMenuAction(isLoggedIn() ? 'dashboard' : 'login')
}

function handleAccessDenied() {
  showTerminalNotice('访问受限，请先登录系统', 'error', 1400)
  setTimeout(() => {
    setRouteHash('auth')
    renderRoute('auth', { bypassGuard: true })
  }, 900)
}

function handleExitTerminal() {
  window.close()

  setTimeout(() => {
    if (typeof window.closed === 'boolean' && window.closed) return
    try {
      window.open('', '_self')
      window.close()
    } catch {
      // ignore
    }
    setTimeout(() => {
      if (typeof window.closed === 'boolean' && window.closed) return
      showTerminalNotice('请手动关闭此标签页', 'success', 2400)
    }, 120)
  }, 80)
}

function handleMenuAction(action) {
  if (action === 'exit') {
    handleExitTerminal()
    return
  }

  if (action === 'logout') {
    handleLogout()
    return
  }

  const route = MENU_ACTION_ROUTES[action]
  if (!route) return

  if (!isLoggedIn() && PROTECTED_ROUTES.has(route)) {
    handleAccessDenied()
    return
  }

  navigateTo(route)
}

function navigateTo(route, options = {}) {
  const normalized = normalizeRoute(route)

  if (!options.bypassGuard && !isLoggedIn() && PROTECTED_ROUTES.has(normalized)) {
    handleAccessDenied()
    return
  }

  setRouteHash(normalized)
  renderRoute(normalized, options)
}

function normalizeRoute(route) {
  let key = String(route || '').trim().toLowerCase()
  key = key.replace(/^#\/?/, '').replace(/^\//, '')
  return ROUTE_ALIASES[key] || 'start'
}

function resolveRoute(route, { bypassGuard = false } = {}) {
  const normalized = normalizeRoute(route)

  if (bypassGuard) return normalized

  if (!isLoggedIn() && PROTECTED_ROUTES.has(normalized)) {
    return 'auth'
  }

  if (normalized === 'auth' && isLoggedIn()) {
    return 'dashboard'
  }

  if (PUBLIC_ROUTES.has(normalized) || PROTECTED_ROUTES.has(normalized)) {
    return normalized
  }

  return 'start'
}

function updateScreenBars(view) {
  const labels = SCREEN_BAR_LABELS[view] || SCREEN_BAR_LABELS.start
  const tl = document.getElementById('screen-bar-tl')
  const tr = document.getElementById('screen-bar-tr')
  const bl = document.getElementById('screen-bar-bl')
  const br = document.getElementById('screen-bar-br')
  if (tl) tl.textContent = labels.tl
  if (tr) tr.textContent = labels.tr
  if (bl) bl.textContent = labels.bl
  if (br) br.textContent = labels.br
}

function setRouteHash(route, replace = false) {
  const normalized = normalizeRoute(route)
  const hash = `#${normalized}`
  if (window.location.hash === hash) return
  if (replace) window.history.replaceState(null, '', hash)
  else window.location.hash = hash
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function renderProgressBar(percent) {
  const filled = Math.round((percent / 100) * PROGRESS_BAR_WIDTH)
  const empty = PROGRESS_BAR_WIDTH - filled
  const bar = '█'.repeat(filled) + '░'.repeat(empty)
  return `[SYSTEM_BOOT_SEQUENCE: ${percent}%]\n${bar}`
}

function finishPreboot() {
  document.body.classList.remove('is-preboot')
}

async function runWakeSequence() {
  const overlay = document.getElementById('wake-overlay')
  const btn = document.getElementById('wake-init-btn')
  if (!overlay || !btn) return

  if (overlay.hidden) overlay.hidden = false
  btn.hidden = false
  btn.classList.add('wake-init-btn--visible')

  await new Promise((resolve) => {
    const onInit = async () => {
      btn.removeEventListener('click', onInit)
      btn.classList.add('wake-init-btn--exiting')

      await ensureAudioContext()
      playGeigerClick()

      await delay(220)
      btn.remove()

      overlay.classList.add('wake-overlay--exiting')
      await delay(500)
      overlay.remove()
      finishPreboot()
      resolve()
    }

    btn.addEventListener('click', onInit)
  })
}

async function runBootSequence() {
  const stage = getTerminalViewport()
  const content = getTerminalContent()
  content.innerHTML = ''
  stage?.classList.add('boot-centered')

  const container = document.createElement('div')
  container.className = 'boot-container'

  const labelEl = document.createElement('p')
  labelEl.className = 'boot-label terminal-line'
  container.appendChild(labelEl)

  const barEl = document.createElement('p')
  barEl.className = 'boot-bar terminal-line'
  container.appendChild(barEl)

  content.appendChild(container)

  let percent = 0
  const targetDuration = randomInt(4500, 6000)
  const startTime = Date.now()

  while (percent < 100) {
    const text = renderProgressBar(percent)
    const lines = text.split('\n')
    labelEl.textContent = lines[0]
    barEl.textContent = lines[1]

    await delay(randomInt(80, 500))

    const elapsed = Date.now() - startTime
    const remaining = targetDuration - elapsed
    const remainingPercent = 100 - percent

    let jump
    if (remaining <= 0 || remainingPercent <= 0) {
      jump = remainingPercent
    } else {
      jump = randomInt(4, 18)
      if (percent + jump > 100) jump = 100 - percent
    }

    percent = Math.min(100, percent + jump)
  }

  const finalText = renderProgressBar(100)
  const finalLines = finalText.split('\n')
  labelEl.textContent = finalLines[0]
  barEl.textContent = finalLines[1]
  await delay(120)

  stage?.classList.remove('boot-centered')
  content.innerHTML = ''
}

const AI_FACE_ROUTES = new Set(['start', 'dashboard', 'query', 'analytics', 'knowledge'])

function mountConsoleAiFace() {
  const slot = document.querySelector('[data-ai-face-slot]')
  const face = document.getElementById('ai-face')
  const screenContent = document.getElementById('screen-content')
  if (!face || !screenContent) return

  const saved = sessionStorage.getItem('crisis_ai_mascot_position')
  ensureFloatingAiMascot({ state: 'detected' })

  if (!saved && slot) {
    const slotRect = slot.getBoundingClientRect()
    const contentRect = screenContent.getBoundingClientRect()
    const x = slotRect.left - contentRect.left + (slotRect.width - face.offsetWidth) / 2
    const y = slotRect.top - contentRect.top + (slotRect.height - face.offsetHeight) / 2
    face.style.left = `${Math.max(8, x)}px`
    face.style.top = `${Math.max(8, y)}px`
    face.style.right = 'auto'
    face.style.bottom = 'auto'
  }

  face.hidden = false
  face.setAttribute('aria-hidden', 'false')

  if (consoleAiFaceSpeakTimer) clearTimeout(consoleAiFaceSpeakTimer)
  notifyTypewriterStart()
  consoleAiFaceSpeakTimer = setTimeout(() => {
    notifyTypewriterEnd()
    consoleAiFaceSpeakTimer = null
  }, 2200)

  ensureAiSummaryBubble({ refresh: false })
}

function ensureGlobalAiFace(route) {
  if (!AI_FACE_ROUTES.has(route)) {
    hideAiFace()
    hideAiSummaryBubble()
    return
  }

  if (route === 'start') {
    requestAnimationFrame(() => mountConsoleAiFace())
    return
  }

  requestAnimationFrame(() => {
    ensureFloatingAiMascot({ state: 'detected' })
    ensureAiSummaryBubble({ refresh: true })
  })
}

function hideAiFace() {
  const face = document.getElementById('ai-face')
  if (face) {
    face.hidden = true
    face.setAttribute('aria-hidden', 'true')
  }
}

function bindStartKeyboard() {
  document.addEventListener('keydown', (e) => {
    if (!hasCompletedBoot) return
    if (resolveRoute(window.location.hash) !== 'start') return
    if (e.key !== 'Enter') return
    goFromStart()
  })
}

function handleLogout() {
  signOut()
  showTerminalNotice('已退出登录', 'success')
  setRouteHash('start')
  renderRoute('start', { bypassGuard: true })
}

function renderRoute(route, options = {}) {
  const requested = normalizeRoute(route)
  const normalized = resolveRoute(route, options)

  if (!options.bypassGuard && !isLoggedIn() && PROTECTED_ROUTES.has(requested)) {
    showTerminalNotice('访问受限，请先登录系统', 'error', 1400)
  }

  const barView = normalized
  updateScreenBars(barView)

  renderSystemPage({
    route: normalized,
    user: getCurrentUser(),
    isLoggedIn: isLoggedIn(),
    onNavigate: navigateTo,
    onMenuAction: handleMenuAction,
    onAccessDenied: handleAccessDenied,
    onLogout: handleLogout,
  })

  stopCornerLog()

  ensureGlobalAiFace(normalized)
}

function onHashChange() {
  if (!hasCompletedBoot) return
  renderRoute(window.location.hash)
}

function onAuthStateChanged(user) {
  if (!hasCompletedBoot) return

  const nextUserId = user?.id ?? null
  if (nextUserId === lastKnownUserId) return
  lastKnownUserId = nextUserId

  const expected = resolveRoute(window.location.hash)
  if (normalizeRoute(window.location.hash) !== expected) {
    setRouteHash(expected, true)
  }
  renderRoute(expected)
}

async function initTerminal() {
  try {
    await runLaunchSequence()
    await runWakeSequence()
    updateScreenBars('intro')
    buildTerminalShell()
    await runBootSequence()
    initAiFaceEarly()
    stopCornerLog()

    initAuth()
    await refreshSessionUser()

    hasCompletedBoot = true

    const initialRoute = resolveRoute(window.location.hash)
    renderRoute(initialRoute)
    setRouteHash(initialRoute, true)
    lastKnownUserId = getCurrentUser()?.id ?? null
    bindStartKeyboard()
    subscribeAuth(onAuthStateChanged)
    window.addEventListener('hashchange', onHashChange)
  } catch (err) {
    console.error('[Crisis Data Terminal] init failed:', err)
  }
}

initTerminal()
