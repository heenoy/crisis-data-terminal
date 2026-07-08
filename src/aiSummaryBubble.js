import {
  buildAiSummaryText,
  fetchGlobalDisasterStats,
  formatDashboardNumber,
} from './dashboardData.js'
import { subscribeMascotPosition } from './aiFace.js'

const BUBBLE_COLLAPSED_KEY = 'crisis_ai_bubble_collapsed'
const BUBBLE_HIDDEN_KEY = 'crisis_ai_bubble_hidden'

let bubbleEl = null
let statsCache = null
let unsubscribePosition = null
let refreshTimer = null

function readFlag(key) {
  try {
    return sessionStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function writeFlag(key, value) {
  try {
    sessionStorage.setItem(key, value ? '1' : '0')
  } catch {
    // ignore
  }
}

function ensureBubbleElement() {
  const screenContent = document.getElementById('screen-content')
  if (!screenContent) return null

  if (!bubbleEl) {
    bubbleEl = document.createElement('aside')
    bubbleEl.id = 'ai-summary-bubble'
    bubbleEl.className = 'ai-summary-bubble'
    bubbleEl.setAttribute('aria-label', '系统分析摘要')
    bubbleEl.innerHTML = `
      <div class="ai-summary-bubble__header">
        <span class="ai-summary-bubble__title">系统分析</span>
        <div class="ai-summary-bubble__actions">
          <button type="button" class="ai-summary-bubble__btn" data-action="collapse" aria-label="收起">−</button>
          <button type="button" class="ai-summary-bubble__btn" data-action="close" aria-label="关闭">×</button>
        </div>
      </div>
      <div class="ai-summary-bubble__body">
        <p class="ai-summary-bubble__text" id="ai-summary-bubble-text">正在同步数据库统计…</p>
      </div>
    `
    screenContent.appendChild(bubbleEl)

    bubbleEl.querySelector('[data-action="collapse"]')?.addEventListener('click', () => {
      const collapsed = bubbleEl.classList.toggle('is-collapsed')
      writeFlag(BUBBLE_COLLAPSED_KEY, collapsed)
      syncBubblePosition()
    })

    bubbleEl.querySelector('[data-action="close"]')?.addEventListener('click', () => {
      bubbleEl.classList.add('is-hidden')
      writeFlag(BUBBLE_HIDDEN_KEY, true)
    })
  }

  if (readFlag(BUBBLE_COLLAPSED_KEY)) bubbleEl.classList.add('is-collapsed')
  if (readFlag(BUBBLE_HIDDEN_KEY)) bubbleEl.classList.add('is-hidden')

  return bubbleEl
}

export function syncBubblePosition() {
  const face = document.getElementById('ai-face')
  const bubble = bubbleEl || document.getElementById('ai-summary-bubble')
  const screenContent = document.getElementById('screen-content')
  if (!face || !bubble || !screenContent || face.hidden) {
    if (bubble) bubble.hidden = true
    return
  }

  if (bubble.classList.contains('is-hidden')) {
    bubble.hidden = true
    return
  }

  bubble.hidden = false
  const faceRect = face.getBoundingClientRect()
  const contentRect = screenContent.getBoundingClientRect()
  const bubbleWidth = bubble.offsetWidth || 248
  const bubbleHeight = bubble.offsetHeight || 120

  let left = faceRect.left - contentRect.left - bubbleWidth - 10
  let top = faceRect.top - contentRect.top

  if (left < 8) {
    left = faceRect.right - contentRect.left + 10
  }

  const maxLeft = Math.max(8, contentRect.width - bubbleWidth - 8)
  const maxTop = Math.max(8, contentRect.height - bubbleHeight - 8)
  left = Math.min(Math.max(8, left), maxLeft)
  top = Math.min(Math.max(8, top), maxTop)

  bubble.style.left = `${left}px`
  bubble.style.top = `${top}px`
}

function renderBubbleText() {
  const textEl = document.getElementById('ai-summary-bubble-text')
  if (!textEl) return
  textEl.textContent = buildAiSummaryText(statsCache)
}

async function loadBubbleStats({ force = false } = {}) {
  const { stats, error } = await fetchGlobalDisasterStats({ force })
  if (error) {
    const textEl = document.getElementById('ai-summary-bubble-text')
    if (textEl) textEl.textContent = `系统分析：数据读取失败（${error.message || error}）`
    return
  }
  statsCache = stats
  renderBubbleText()
}

export function ensureAiSummaryBubble({ refresh = false } = {}) {
  const bubble = ensureBubbleElement()
  if (!bubble) return

  if (!unsubscribePosition) {
    unsubscribePosition = subscribeMascotPosition(() => {
      syncBubblePosition()
    })
  }

  syncBubblePosition()
  loadBubbleStats({ force: refresh })

  if (!refreshTimer) {
    refreshTimer = window.setInterval(() => {
      loadBubbleStats({ force: true })
    }, 180000)
  }
}

export function hideAiSummaryBubble() {
  if (bubbleEl) bubbleEl.hidden = true
}

export function destroyAiSummaryBubble() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  unsubscribePosition?.()
  unsubscribePosition = null
}

export function refreshAiSummaryBubble() {
  loadBubbleStats({ force: true })
}
