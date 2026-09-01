import { ensureFloatingAiMascot, notifyTypewriterEnd, notifyTypewriterStart, subscribeMascotPosition } from './aiFace.js'
import { bindTerminalNavigation } from './terminalNav.js'

const ANALYZING_TEXT = '正在分析灾害数据库……'
const SERVICE_ERROR_TEXT = 'AI 分析：\n服务暂时不可用，请稍后重试。'

const state = {
  messages: [
    {
      role: 'assistant',
      content: 'VAULT-0：\n请直接向我提问。',
    },
  ],
  busy: false,
}

let unsubscribeMascotPosition = null
let bubbleSyncRaf = null

function cleanupInquiryCompanion() {
  unsubscribeMascotPosition?.()
  unsubscribeMascotPosition = null
  window.removeEventListener('resize', syncBubbleToMascot)
  if (bubbleSyncRaf) cancelAnimationFrame(bubbleSyncRaf)
  bubbleSyncRaf = null
}

export function destroyKnowledgePage() {
  cleanupInquiryCompanion()
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderBackBar() {
  return `
    <div class="terminal-back-bar terminal-back-bar--split">
      <button type="button" class="terminal-back-bar__btn" data-route="dashboard" aria-label="返回灾害事件总览">
        ← 返回灾害事件总览
      </button>
      <button type="button" class="terminal-back-bar__btn" data-route="start" aria-label="返回主菜单">
        ← 返回主菜单
      </button>
    </div>
  `
}

function latestAssistantMessage() {
  return [...state.messages].reverse().find((message) => message.role === 'assistant')
}

function recentHistory() {
  return state.messages
    .filter((message) => message.role === 'user')
    .slice(-3)
    .map((message) => message.content)
}

function renderBubbleContent() {
  const latest = latestAssistantMessage()
  const answer = state.busy ? ANALYZING_TEXT : latest?.content || 'AI 分析：\n等待输入。'
  const history = recentHistory()

  return `
    <p class="aiq-bubble__meta">[ AI_CRISIS_CORE / ${state.busy ? 'ANALYZING' : latest?.error ? 'ERROR' : 'READY'} ]</p>
    <div class="aiq-bubble__body">${escapeHtml(answer).replace(/\n/g, '<br>')}</div>
    ${history.length
      ? `
        <div class="aiq-bubble__history" aria-label="最近指令">
          ${history.map((item) => `<span>&gt; ${escapeHtml(item)}</span>`).join('')}
        </div>
      `
      : ''}
  `
}

function renderInputForm() {
  return `
    <form class="aiq-command" id="aiq-chat-form">
      <p class="aiq-command__examples">
        示例：查询“中国洪水灾害趋势” / “解释重大灾害标准” / “地震如何避险”
      </p>
      <div class="aiq-command__row">
        <label class="aiq-command__input-wrap">
          <span>${state.busy ? ANALYZING_TEXT : 'CRISIS_QUERY_INPUT'}</span>
          <textarea
            id="aiq-input"
            name="question"
            rows="2"
            maxlength="800"
            placeholder="输入灾害数据库查询指令..."
            ${state.busy ? 'disabled' : ''}
          ></textarea>
        </label>
        <button type="submit" class="aiq-submit" ${state.busy ? 'disabled' : ''}>
          ${state.busy ? '[ ANALYZING... ]' : '[ SEND ]'}
        </button>
      </div>
    </form>
  `
}

export function renderKnowledgePage() {
  return `
    <section class="vault-console vault-console--subpage" aria-label="AI 灾害问询终端">
      ${renderBackBar()}
      <section class="aiq-terminal">
        <header class="aiq-terminal__header">
          <p class="aiq-terminal__kicker">[ CRISIS_DATA / AI_INQUIRY_NODE ]</p>
          <h1 class="aiq-terminal__title">
            <span class="aiq-terminal__title-en">AI CRISIS INQUIRY TERMINAL</span>
            <span class="aiq-terminal__title-zh">AI 灾害问询终端</span>
          </h1>
        </header>
        <main class="aiq-stage" aria-live="polite">
          <div class="aiq-face-anchor" aria-hidden="true"></div>
          <section class="aiq-face-bubble" id="aiq-face-bubble">
            ${renderBubbleContent()}
          </section>
        </main>
        ${renderInputForm()}
      </section>
    </section>
  `
}

function renderDynamicParts(root) {
  const bubble = root.querySelector('#aiq-face-bubble')
  if (bubble) bubble.innerHTML = renderBubbleContent()

  const oldForm = root.querySelector('#aiq-chat-form')
  if (oldForm) {
    oldForm.outerHTML = renderInputForm()
    bindChatForm(root)
  }
}

function limitHistory() {
  const firstAssistant = state.messages[0]
  const recent = state.messages.slice(1).slice(-5)
  state.messages = firstAssistant ? [firstAssistant, ...recent] : recent
}

async function sendQuestion(root, question) {
  const content = question.trim()
  if (!content || state.busy) return

  state.messages.push({ role: 'user', content })
  state.busy = true
  notifyTypewriterStart()
  renderDynamicParts(root)

  try {
    const res = await fetch('/api/ai-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: content,
        history: state.messages.slice(-6).map(({ role, content }) => ({ role, content })),
      }),
    })
    const contentType = res.headers.get('content-type') || ''
    if (!contentType.includes('application/json')) throw new Error('AI response is not JSON')
    const payload = await res.json()
    if (!res.ok) throw new Error(payload.error || 'AI request failed')
    if (typeof payload.answer !== 'string' || !payload.answer.trim()) throw new Error('AI response is missing an answer')
    state.messages.push({
      role: 'assistant',
      content: `AI 分析：\n${payload.answer}`,
    })
  } catch (err) {
    console.warn('[Crisis Data Terminal] AI inquiry failed:', err)
    state.messages.push({ role: 'assistant', content: SERVICE_ERROR_TEXT, error: true })
  } finally {
    state.busy = false
    limitHistory()
    notifyTypewriterEnd()
    renderDynamicParts(root)
    root.querySelector('#aiq-input')?.focus()
    syncBubbleToMascot()
  }
}

function bindChatForm(root) {
  const form = root.querySelector('#aiq-chat-form')
  const input = root.querySelector('#aiq-input')
  form?.addEventListener('submit', (event) => {
    event.preventDefault()
    sendQuestion(root, input?.value || '')
  })
  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      sendQuestion(root, input.value)
    }
  })
}

function positionMascotForInquiry() {
  const face = document.getElementById('ai-face')
  const screenContent = document.getElementById('screen-content')
  if (!face || !screenContent) return
  if (face.style.left && face.style.top) return
  try {
    if (sessionStorage.getItem('crisis_ai_mascot_position')) return
  } catch {
    // Keep the current page position if sessionStorage is unavailable.
    return
  }

  const x = Math.max(12, screenContent.clientWidth * 0.58 - face.offsetWidth / 2)
  const y = Math.max(12, screenContent.clientHeight * 0.42 - face.offsetHeight / 2)
  face.style.left = `${x}px`
  face.style.top = `${y}px`
  face.style.right = 'auto'
  face.style.bottom = 'auto'
}

function syncBubbleToMascot() {
  if (bubbleSyncRaf) cancelAnimationFrame(bubbleSyncRaf)
  bubbleSyncRaf = requestAnimationFrame(() => {
    const bubble = document.getElementById('aiq-face-bubble')
    const face = document.getElementById('ai-face')
    if (!bubble || !face || face.hidden) return

    const faceRect = face.getBoundingClientRect()
    const bubbleWidth = bubble.offsetWidth || 360
    const gap = 18
    let left = faceRect.left - bubbleWidth - gap
    if (left < 14) left = faceRect.right + gap
    const maxLeft = Math.max(14, window.innerWidth - bubbleWidth - 14)
    left = Math.min(Math.max(14, left), maxLeft)

    const top = Math.min(
      Math.max(14, faceRect.top + faceRect.height * 0.08),
      Math.max(14, window.innerHeight - bubble.offsetHeight - 18),
    )

    bubble.style.left = `${left}px`
    bubble.style.top = `${top}px`
  })
}

function setupMascotCompanion() {
  cleanupInquiryCompanion()
  ensureFloatingAiMascot({ state: 'detected' })
  positionMascotForInquiry()
  unsubscribeMascotPosition = subscribeMascotPosition(syncBubbleToMascot)
  window.addEventListener('resize', syncBubbleToMascot)
  syncBubbleToMascot()
}

export async function initKnowledgePage({ onNavigate } = {}) {
  const app = document.getElementById('app')
  if (!app) return

  app.innerHTML = renderKnowledgePage()
  bindTerminalNavigation({ onNavigate, root: app })
  bindChatForm(app)
  requestAnimationFrame(setupMascotCompanion)
}
