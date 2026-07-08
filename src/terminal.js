import { playTypewriterClick } from './audio.js'
import { notifyTypewriterEnd, notifyTypewriterStart } from './aiFace.js'

export { setupAudioUnlock, destroyAudio } from './audio.js'

export const CHAR_DELAY = 50
export const SILENT_CHARS = new Set([' ', '。', '，', '？', '！', '：'])

const LINE_EXIT_FAST_DURATION = 300
const STATIC_FADE_DURATION = 600
const MAX_CORNER_LOG_LINES = 5
const CORNER_LOG_INTERVAL = 1500
const CORNER_LOG_EXIT_DURATION = 400

const STATIC_CORNER_LOG_LINES = [
  'FETCHING CRISIS_DATA_FEED...',
  'BOOT_SECTOR: VERIFIED',
  'MEMORY_ALLOCATED: 2047MB',
  'SCANNING SIGNAL_INPUT...',
  'CONNECTION: ESTABLISHED',
  'ANALYZING_EVENT_PATTERN...',
  'THREAT_INDEX: MONITORING',
  'DATA_PIPELINE: ACTIVE',
  'SURVIVAL_METRICS: STANDBY',
  'ALERT_BUFFER: READY',
  'GEO_SYNC: IN_PROGRESS',
  'ARCHIVE_STATUS: RECORDING',
  'VAULT_CORE: OBSERVING',
  'TERMINAL_LINK: SECURE',
  'CRISIS_DB: STANDBY',
]

let cornerLogTimer = null
let cornerLogOptions = {}
let lineSlots = { current: null, prev: null, prev2: null }

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function formatTimestamp() {
  const d = new Date()
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${h}:${m}:${s}`
}

function clearLineSlots() {
  lineSlots = { current: null, prev: null, prev2: null }
}

function setSlotClass(el, slot) {
  if (!el) return
  el.classList.remove('is-current', 'is-prev', 'is-prev2', 'is-exiting')
  if (slot) el.classList.add(`is-${slot}`)
}

export function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function getTerminalStage() {
  return document.getElementById('terminal-stage')
}

export function getScrollLines() {
  return document.getElementById('scroll-lines')
}

export function getPinArea() {
  return document.getElementById('scroll-pin-area')
}

export function getLineStack() {
  return document.getElementById('terminal-line-stack')
}

export function getTerminalContent() {
  return getTerminalStage()
}

export function getTerminalViewport() {
  return getTerminalStage()
}

export function getErrorBar() {
  return document.getElementById('error-bar')
}

const SHELL_HTML = `
  <main id="terminal">
    <div id="terminal-stage" class="terminal-stage">
      <div id="terminal-line-stack" class="terminal-line-stack">
        <div id="scroll-viewport" class="scroll-viewport">
          <div id="scroll-lines" class="scroll-lines"></div>
        </div>
        <div id="scroll-pin-area" class="scroll-pin-area"></div>
      </div>
    </div>
    <div id="error-bar"></div>
    <aside id="corner-log">
      <div id="corner-log-scroll" class="corner-log-scroll"></div>
    </aside>
  </main>
`

export function buildTerminalShell() {
  document.getElementById('app').innerHTML = SHELL_HTML
  resetTerminalScroll()
  resetCornerLogScroll()
}

export function ensureCornerLogPanel() {
  if (document.getElementById('corner-log')) return

  const host = document.getElementById('screen-content')
  if (!host) return

  const aside = document.createElement('aside')
  aside.id = 'corner-log'
  aside.innerHTML = '<div id="corner-log-scroll" class="corner-log-scroll"></div>'
  host.appendChild(aside)
  resetCornerLogScroll()
}

export function resetTerminalScroll() {
  const stage = getTerminalStage()
  if (!stage) return
  stage.innerHTML = `
    <div id="terminal-line-stack" class="terminal-line-stack">
      <div id="scroll-viewport" class="scroll-viewport">
        <div id="scroll-lines" class="scroll-lines"></div>
      </div>
      <div id="scroll-pin-area" class="scroll-pin-area"></div>
    </div>
  `
  stage.classList.remove('boot-centered')
  clearLineSlots()
}

export async function advanceTerminalLine() {
  if (lineSlots.prev2) {
    lineSlots.prev2.classList.add('is-exiting')
    await delay(LINE_EXIT_FAST_DURATION)
    lineSlots.prev2.remove()
    lineSlots.prev2 = null
  }

  if (lineSlots.prev) {
    setSlotClass(lineSlots.prev, 'prev2')
    lineSlots.prev2 = lineSlots.prev
  } else {
    lineSlots.prev2 = null
  }

  if (lineSlots.current) {
    setSlotClass(lineSlots.current, 'prev')
    lineSlots.prev = lineSlots.current
  } else {
    lineSlots.prev = null
  }

  lineSlots.current = null
}

export async function fadeOutStaticGroup(group) {
  if (!group) return
  group.classList.add('is-fading')
  await delay(STATIC_FADE_DURATION)
  group.remove()
}

export function registerCurrentLayer(el) {
  lineSlots.current = el
  setSlotClass(el, 'current')
}

let errorTimer = null

export function showError(message, autoDismiss = true) {
  const bar = getErrorBar()
  if (!bar) return
  bar.textContent = `> [ERROR] ${message}`
  if (errorTimer) clearTimeout(errorTimer)
  if (autoDismiss) {
    errorTimer = setTimeout(() => {
      bar.textContent = ''
      errorTimer = null
    }, 1500)
  }
}

export async function typeText(element, text, options = {}) {
  const charDelay = options.charDelay ?? CHAR_DELAY
  const playSound = options.playSound ?? true
  notifyTypewriterStart()
  element.textContent = ''
  try {
    for (const char of text) {
      element.textContent += char
      if (playSound) {
        playTypewriterClick(char)
      }
      await delay(charDelay)
    }
  } finally {
    notifyTypewriterEnd()
  }
}

window.typeText = typeText

export function createLine(withPrompt = false, parent = null) {
  const wrapper = document.createElement('div')
  wrapper.className = 'terminal-line-layer'
  const line = document.createElement('div')
  line.className = withPrompt ? 'terminal-line has-prompt' : 'terminal-line'
  wrapper.appendChild(line)
  const container = parent || getLineStack()
  container.appendChild(wrapper)
  registerCurrentLayer(wrapper)
  return line
}

export function createStaticGroup(className = 'static-group') {
  const group = document.createElement('div')
  group.className = className
  getTerminalStage().appendChild(group)
  return group
}

export function createScrollRow(className = 'static-group') {
  return createStaticGroup(className)
}

export async function printLine(text, options = {}) {
  await advanceTerminalLine()
  const line = createLine(true)
  await typeText(line, text, options)
  return line
}

function resetCornerLogScroll() {
  const scroll = document.getElementById('corner-log-scroll')
  if (!scroll) return
  scroll.innerHTML = ''
}

async function pruneCornerLogLines() {
  const scroll = document.getElementById('corner-log-scroll')
  if (!scroll) return

  while (scroll.children.length > MAX_CORNER_LOG_LINES) {
    const oldest = scroll.firstElementChild
    oldest.classList.add('corner-log-exiting')
    await delay(CORNER_LOG_EXIT_DURATION)
    oldest.remove()
  }
}

function generateCornerLogLine() {
  const { mode = 'intro', getRoundProgress, getLastReactionTime } = cornerLogOptions
  const generators = [
    () => STATIC_CORNER_LOG_LINES[randomInt(0, STATIC_CORNER_LOG_LINES.length - 1)],
    () => `COGNITIVE_LOAD: ${randomInt(60, 95)}%`,
    () => `NEURAL_SYNC: ${randomInt(70, 99)}%`,
    () => `TIMESTAMP: ${formatTimestamp()}`,
    () => {
      const id = localStorage.getItem('player_id') || 'UNKNOWN'
      return `PLAYER_ID: ${id.slice(0, 8)}`
    },
  ]

  if (mode === 'game') {
    if (getRoundProgress) {
      generators.push(() => `ROUND_PROGRESS: ${getRoundProgress()}`)
    }
    if (getLastReactionTime) {
      const rt = getLastReactionTime()
      if (rt != null) {
        generators.push(() => `REACTION_DELTA: ${rt}ms`)
      }
    }
  }

  return generators[randomInt(0, generators.length - 1)]()
}

export async function appendCornerLog(text) {
  const scroll = document.getElementById('corner-log-scroll')
  if (!scroll) return

  const line = document.createElement('div')
  line.className = 'corner-log-line'
  line.textContent = text
  scroll.appendChild(line)
  await pruneCornerLogLines()
}

async function appendRandomCornerLog() {
  await appendCornerLog(generateCornerLogLine())
}

export function startCornerLog(options = {}) {
  stopCornerLog()
  cornerLogOptions = options

  appendRandomCornerLog()
  cornerLogTimer = setInterval(() => {
    appendRandomCornerLog()
  }, CORNER_LOG_INTERVAL)
}

export function stopCornerLog() {
  if (cornerLogTimer) {
    clearInterval(cornerLogTimer)
    cornerLogTimer = null
  }
}
