import registry from '../../data/model-registry.json'
import { supabase } from '../../supabase.js'
import {
  HEALTH_STATE,
  aggregateHealth,
  checkAiGeneration,
  checkDatabaseHealth,
  checkPredictionHealth,
} from '../../services/systemHealth.js'

const frozenHash = registry.frozenModel.sha256
const unchecked = (label = '尚未检查') => ({
  state: HEALTH_STATE.UNCHECKED,
  code: 'UNCHECKED',
  label,
  checkedAt: null,
  durationMs: null,
  details: {},
})
const loading = (label = '检查中') => ({
  state: HEALTH_STATE.LOADING,
  code: 'LOADING',
  label,
  checkedAt: null,
  durationMs: null,
  details: {},
})

let state = createInitialState()
let cycleId = 0
let cycleController = null
let aiController = null
let aiChecking = false

function createInitialState() {
  return {
    database: unchecked(),
    prediction: unchecked(),
    ai: unchecked('未执行生成验证'),
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatDuration(value) {
  return Number.isFinite(value) ? `${value} ms` : '—'
}

function statusCard(id, title, subtitle, body, action = '') {
  return `<article class="system-health-card" data-health-card="${id}" data-state="unchecked">
    <div class="system-health-card__heading">
      <div><p class="vault-kicker">[ ${subtitle} ]</p><h2>${title}</h2></div>
      <span class="system-health-badge" data-health-badge>尚未检查</span>
    </div>
    <div class="system-health-card__body">${body}</div>
    <dl class="system-health-meta">
      <div><dt>最近检查</dt><dd data-health-time>—</dd></div>
      <div><dt>浏览器往返耗时</dt><dd data-health-duration>—</dd></div>
    </dl>
    ${action}
  </article>`
}

export function renderAdminSystemMonitor() {
  return `<section class="vault-console vault-console--subpage" aria-label="系统状态">
    <div class="admin-portal admin-system-status">
      <header class="admin-portal__header">
        <div><p class="vault-kicker">[ ADMIN_PORTAL / SYSTEM STATUS ]</p><h1>系统状态</h1><p>按需核对有限服务的最后一次检查结果。</p></div>
        <button type="button" class="system-health-refresh" data-health-refresh>[ 重新检查 ]</button>
      </header>

      <section class="system-health-summary" data-health-summary data-state="unchecked" aria-live="polite">
        <span class="system-health-summary__mark" aria-hidden="true">◇</span>
        <div><p class="vault-kicker">[ CHECK SUMMARY ]</p><strong data-health-summary-label>尚未检查</strong></div>
      </section>

      <div class="system-health-grid">
        ${statusCard('database', '数据库与 Data API', 'DATABASE / DATA API', `
          <p data-health-message>尚未检查管理员会话和只读数据访问。</p>
          <p>灾害记录：<strong data-health-value="recordCount">—</strong></p>
        `)}
        ${statusCard('prediction', '预测 API 与冻结模型', 'PREDICTION API', `
          <p data-health-message>尚未检查预测健康合同。</p>
          <p>实时模型：<strong data-health-value="model">—</strong></p>
          <p>类别顺序：<strong data-health-value="classes">—</strong></p>
          <p>登记 SHA-256：<code title="${escapeHtml(frozenHash)}">${escapeHtml(frozenHash.slice(0, 12))}…${escapeHtml(frozenHash.slice(-8))}</code></p>
        `)}
        ${statusCard('ai', 'AI 灾害问询服务', 'AI INQUIRY', `
          <p data-health-message>未执行生成验证。该检查不会随页面加载自动调用。</p>
          <p>验证方式：<strong>管理员手动触发一次真实、短文本生成请求</strong></p>
          <p>服务模型：<strong data-health-value="model">—</strong></p>
        `, '<button type="button" class="system-health-card__action" data-health-ai-check>[ 执行真实 AI 检查 ]</button>')}
      </div>

      <aside class="system-health-note">
        <strong>[ ON-DEMAND CHECK ]</strong>
        <span>当前结果是按需健康检查，不是持续实时监控；延迟为浏览器侧单次请求往返耗时，状态只代表最后一次检查结果。</span>
      </aside>
    </div>
  </section>`
}

function setValue(card, key, value) {
  const element = card?.querySelector(`[data-health-value="${key}"]`)
  if (element) element.textContent = value ?? '—'
}

function renderCard(id) {
  const result = state[id]
  const card = document.querySelector(`[data-health-card="${id}"]`)
  if (!card) return
  card.dataset.state = result.state
  card.querySelector('[data-health-badge]').textContent = result.label
  card.querySelector('[data-health-message]').textContent = result.label
  card.querySelector('[data-health-time]').textContent = formatTime(result.checkedAt)
  card.querySelector('[data-health-duration]').textContent = formatDuration(result.durationMs)

  if (id === 'database') setValue(card, 'recordCount', Number.isInteger(result.details.recordCount) ? `${result.details.recordCount.toLocaleString('zh-CN')} 条` : '—')
  if (id === 'prediction') {
    setValue(card, 'model', result.details.model)
    setValue(card, 'classes', Array.isArray(result.details.classes) ? result.details.classes.join(' / ') : '—')
  }
  if (id === 'ai') setValue(card, 'model', result.details.model)
}

function renderSummary() {
  const summary = aggregateHealth(state)
  const element = document.querySelector('[data-health-summary]')
  if (!element) return
  element.dataset.state = summary.state
  element.querySelector('[data-health-summary-label]').textContent = summary.label
}

function renderAll() {
  Object.keys(state).forEach(renderCard)
  renderSummary()
  const running = Object.values(state).some((item) => item.state === HEALTH_STATE.LOADING)
  const refresh = document.querySelector('[data-health-refresh]')
  const aiButton = document.querySelector('[data-health-ai-check]')
  if (refresh) refresh.disabled = running
  if (aiButton) aiButton.disabled = aiChecking || state.ai.state === HEALTH_STATE.LOADING
}

async function databaseAdapter(signal) {
  let query = supabase.from('disaster_events').select('id', { count: 'exact', head: true })
  if (typeof query.abortSignal === 'function') query = query.abortSignal(signal)
  const { count, error, status } = await query
  return { count, error, status }
}

async function runSafeChecks() {
  cycleController?.abort()
  const controller = new AbortController()
  cycleController = controller
  const currentCycle = ++cycleId
  state = {
    database: loading('正在检查 Data API'),
    prediction: loading('正在检查预测合同'),
    ai: state.ai.state === HEALTH_STATE.LOADING ? unchecked('未执行生成验证') : state.ai,
  }
  renderAll()

  const [database, prediction] = await Promise.all([
    checkDatabaseHealth({
      getSession: async () => (await supabase.auth.getSession()).data.session,
      countDisasters: databaseAdapter,
      signal: controller.signal,
    }),
    checkPredictionHealth({ signal: controller.signal }),
  ])
  if (controller.signal.aborted || currentCycle !== cycleId) return
  state.database = database
  state.prediction = prediction
  renderAll()
}

async function runAiCheck() {
  if (aiChecking) return
  aiChecking = true
  aiController?.abort()
  const controller = new AbortController()
  aiController = controller
  state.ai = loading('正在执行真实生成验证')
  renderAll()
  const result = await checkAiGeneration({ signal: controller.signal })
  if (controller.signal.aborted || aiController !== controller) return
  state.ai = result
  aiChecking = false
  renderAll()
}

export function initAdminSystemMonitor() {
  document.querySelector('[data-health-refresh]')?.addEventListener('click', runSafeChecks)
  document.querySelector('[data-health-ai-check]')?.addEventListener('click', runAiCheck)
  runSafeChecks()
}

export function destroyAdminSystemMonitor() {
  cycleId += 1
  cycleController?.abort()
  aiController?.abort()
  cycleController = null
  aiController = null
  aiChecking = false
  state = createInitialState()
}
