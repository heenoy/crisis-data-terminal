const HINT_CONTINUE = 'CLICK TO CONTINUE ▶'
const HINT_CHOICE = 'MAKE YOUR CHOICE ▼'

let waitingForClick = false
let clickResolve = null
let hintEl = null
let blinkRaf = null
let initialized = false

function isInteractiveTarget(target) {
  if (
    document.querySelector(
      '.scroll-line--input .terminal-input:not([data-resolved])'
    )
  ) {
    return true
  }
  return Boolean(
    target.closest(
      'button, input, textarea, select, a, .scroll-line--choice, .scroll-line--option, .scroll-line--input, .wake-init-btn, .choice-btn, .wake-overlay'
    )
  )
}

function updateBlinkOpacity() {
  if (!hintEl || hintEl.style.display === 'none') return
  const t = (performance.now() % 1500) / 1500
  const opacity = 0.2 + 0.8 * (0.5 - 0.5 * Math.cos(t * Math.PI * 2))
  hintEl.style.opacity = String(opacity)
  blinkRaf = requestAnimationFrame(updateBlinkOpacity)
}

function startBlink() {
  if (blinkRaf) cancelAnimationFrame(blinkRaf)
  blinkRaf = requestAnimationFrame(updateBlinkOpacity)
}

function stopBlink() {
  if (blinkRaf) {
    cancelAnimationFrame(blinkRaf)
    blinkRaf = null
  }
}

function ensureHint() {
  if (hintEl) return hintEl
  const content = document.getElementById('screen-content')
  hintEl = document.createElement('div')
  hintEl.id = 'click-advance-hint'
  hintEl.setAttribute('aria-hidden', 'true')
  hintEl.style.cssText =
    "position:absolute;bottom:16px;left:50%;transform:translateX(-50%);font-family:'Press Start 2P',monospace;font-size:9px;color:rgba(0,255,65,0.5);pointer-events:none;z-index:10;white-space:nowrap;"
  content?.appendChild(hintEl)
  return hintEl
}

export function showClickHint(text = HINT_CONTINUE) {
  const el = ensureHint()
  el.textContent = text
  el.style.display = 'block'
  startBlink()
}

export function hideClickHint() {
  stopBlink()
  if (hintEl) {
    hintEl.style.display = 'none'
    hintEl.style.opacity = '1'
  }
}

export function suppressClickAdvance() {
  waitingForClick = false
  clickResolve = null
  hideClickHint()
}

export function pauseClickAdvance() {
  waitingForClick = false
  clickResolve = null
}

export function initClickAdvance() {
  if (initialized) return
  initialized = true

  const screen = document.getElementById('screen')
  screen?.addEventListener('click', (e) => {
    if (!waitingForClick) return
    if (isInteractiveTarget(e.target)) return

    waitingForClick = false
    hideClickHint()
    const resolve = clickResolve
    clickResolve = null
    resolve?.()
  })
}

export function waitForClick(text = HINT_CONTINUE) {
  return new Promise((resolve) => {
    waitingForClick = true
    clickResolve = resolve
    showClickHint(text)
  })
}

export { HINT_CHOICE, HINT_CONTINUE }
