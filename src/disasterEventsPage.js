import {
  DISASTER_TYPES,
  SEVERITY_LEVELS,
  STATUS_OPTIONS,
  createDisasterEvent,
  deleteDisasterEvent,
  emptyEventForm,
  eventToForm,
  formatEventDate,
  formatNumber,
  labelDisasterType,
  labelCountry,
  labelSeverity,
  labelStatus,
  listDisasterEvents,
  localizeEventTitle,
  parseEventPayload,
  updateDisasterEvent,
} from './disasterEvents.js'
import { showTerminalNotice } from './terminalNotice.js'
import { getCurrentUser } from './auth.js'
import { renderBackToMainMenu } from './terminalNav.js'

let state = {
  events: [],
  filters: { disaster_type: '', country: '', severity: '', keyword: '' },
  editingId: null,
  pendingDeleteId: null,
  loading: false,
  submitting: false,
  deleting: false,
  user: null,
  mode: 'console',
  activeRoute: 'dashboard',
  onNavigate: null,
}

function optionsHtml(items, selected = '') {
  return items
    .map((item) => `<option value="${item.value}" ${item.value === selected ? 'selected' : ''}>${item.label}</option>`)
    .join('')
}

function filterOptionsHtml(items, includeAll = true) {
  const all = includeAll ? '<option value="">全部</option>' : ''
  return all + items.map((item) => `<option value="${item.value}">${item.label}</option>`).join('')
}

function severityClass(value) {
  return `disaster-badge disaster-badge--${value}`
}

function truncate(text, max = 48) {
  const value = String(text || '')
  return value.length > max ? `${value.slice(0, max)}…` : value
}

function renderTableRows(events, { readOnly = false } = {}) {
  if (!events.length) {
    const colspan = readOnly ? 7 : 8
    const emptyMsg = readOnly
      ? '暂无灾害事件记录。'
      : '暂无灾害事件记录。点击 [ NEW EVENT ] 新增。'
    return `<tr><td colspan="${colspan}" class="disaster-empty">${emptyMsg}</td></tr>`
  }

  return events
    .map(
      (event) => `
    <tr data-event-id="${event.id}">
      <td class="disaster-table__title">${escapeHtml(localizeEventTitle(event))}</td>
      <td>${escapeHtml(labelDisasterType(event.disaster_type))}</td>
      <td>${escapeHtml(labelCountry(event.country))}${event.region ? `<br><span style="opacity:.6">${escapeHtml(event.region)}</span>` : ''}</td>
      <td>${formatEventDate(event.event_date)}</td>
      <td><span class="${severityClass(event.severity)}">${escapeHtml(labelSeverity(event.severity))}</span></td>
      <td>${formatNumber(event.casualties)}</td>
      <td>${escapeHtml(labelStatus(event.status))}</td>
      ${
        readOnly
          ? ''
          : `<td>
        <div class="disaster-row-actions">
          <button type="button" data-action="edit" data-id="${event.id}">[ EDIT ]</button>
          <button type="button" data-action="delete" data-id="${event.id}">[ DELETE ]</button>
        </div>
      </td>`
      }
    </tr>
  `,
    )
    .join('')
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderForm(form, title, error = '') {
  return `
    <form class="disaster-form" id="disaster-event-form" novalidate>
      <h2>${title}</h2>
      ${error ? `<p class="disaster-form-error" role="alert">${escapeHtml(error)}</p>` : ''}
      <div class="disaster-form-grid">
        <label class="disaster-form-span-2">
          <span>标题 TITLE *</span>
          <input name="title" type="text" required value="${escapeHtml(form.title)}" />
        </label>
        <label>
          <span>灾害类型 TYPE *</span>
          <select name="disaster_type">${optionsHtml(DISASTER_TYPES, form.disaster_type)}</select>
        </label>
        <label>
          <span>严重程度 SEVERITY *</span>
          <select name="severity">${optionsHtml(SEVERITY_LEVELS, form.severity)}</select>
        </label>
        <label>
          <span>国家 COUNTRY *</span>
          <input name="country" type="text" required value="${escapeHtml(form.country)}" />
        </label>
        <label>
          <span>区域 REGION</span>
          <input name="region" type="text" value="${escapeHtml(form.region)}" />
        </label>
        <label>
          <span>事件日期 DATE *</span>
          <input name="event_date" type="date" required value="${escapeHtml(form.event_date)}" />
        </label>
        <label>
          <span>状态 STATUS *</span>
          <select name="status">${optionsHtml(STATUS_OPTIONS, form.status)}</select>
        </label>
        <label>
          <span>伤亡 CASUALTIES</span>
          <input name="casualties" type="number" min="0" value="${escapeHtml(form.casualties)}" />
        </label>
        <label>
          <span>受影响人口 AFFECTED</span>
          <input name="affected_population" type="number" min="0" value="${escapeHtml(form.affected_population)}" />
        </label>
        <label>
          <span>经济损失 ECONOMIC LOSS</span>
          <input name="economic_loss" type="number" min="0" step="0.01" value="${escapeHtml(form.economic_loss)}" placeholder="单位：万元" />
        </label>
        <label>
          <span>来源名称 SOURCE</span>
          <input name="source_name" type="text" value="${escapeHtml(form.source_name)}" />
        </label>
        <label class="disaster-form-span-2">
          <span>来源链接 SOURCE URL</span>
          <input name="source_url" type="url" value="${escapeHtml(form.source_url)}" placeholder="https://" />
        </label>
        <label class="disaster-form-span-2">
          <span>描述 DESCRIPTION</span>
          <textarea name="description" rows="4">${escapeHtml(form.description)}</textarea>
        </label>
      </div>
      <div class="disaster-form-actions">
        <button type="submit" ${state.submitting ? 'disabled' : ''}>${state.submitting ? '[ SAVING... ]' : '[ SAVE ]'}</button>
        <button type="button" id="disaster-form-cancel">[ CANCEL ]</button>
      </div>
    </form>
  `
}

export function renderDisasterDashboard({ user, mode = 'query' }) {
  state.user = user
  state.mode = mode

  const readOnly = mode === 'query'
  const kicker = '[ DISASTER_QUERY / SEARCH TERMINAL ]'
  const title = '灾害事件查询'
  const subtitle = 'Disaster Event Query · 档案检索与筛选'
  const form = state.editingId && state.editingId !== 'new'
    ? eventToForm(state.events.find((e) => e.id === state.editingId))
    : emptyEventForm()
  const formTitle = state.editingId && state.editingId !== 'new' ? '[ EDIT DISASTER EVENT ]' : '[ NEW DISASTER EVENT ]'
  const deleteTarget = state.events.find((e) => e.id === state.pendingDeleteId)

  return `
    <section class="vault-console vault-console--subpage" aria-label="灾害事件查询">
      ${renderBackToMainMenu()}
      <div class="disaster-dashboard">
      <header class="disaster-dashboard__header">
        <div>
          <p class="vault-kicker">${kicker}</p>
          <h1>${title}</h1>
          <p>${subtitle}</p>
        </div>
      </header>

      <form class="disaster-filters" id="disaster-filters">
        <label>
          <span>灾害类型</span>
          <select name="disaster_type">${filterOptionsHtml(DISASTER_TYPES)}</select>
        </label>
        <label>
          <span>国家</span>
          <input name="country" type="text" placeholder="如：中国" value="${escapeHtml(state.filters.country)}" />
        </label>
        <label>
          <span>严重程度</span>
          <select name="severity">${filterOptionsHtml(SEVERITY_LEVELS)}</select>
        </label>
        <label>
          <span>关键词</span>
          <input name="keyword" type="text" placeholder="标题/描述/区域" value="${escapeHtml(state.filters.keyword)}" />
        </label>
        <button type="submit">[ SEARCH ]</button>
        <button type="button" id="disaster-filter-reset">[ RESET ]</button>
      </form>

      <div class="disaster-toolbar">
        <p class="disaster-toolbar__meta">RECORD COUNT: <strong id="disaster-count">${state.events.length}</strong></p>
        ${
          readOnly
            ? ''
            : `<div class="disaster-toolbar__buttons">
          <button type="button" id="disaster-new-btn">[ NEW EVENT ]</button>
        </div>`
        }
      </div>

      <div class="disaster-table-wrap" id="disaster-table-wrap">
        ${
          state.loading
            ? '<p class="disaster-loading">&gt; FETCHING DISASTER_RECORDS...</p>'
            : `
        <table class="disaster-table">
          <thead>
            <tr>
              <th>TITLE</th>
              <th>TYPE</th>
              <th>LOCATION</th>
              <th>DATE</th>
              <th>SEVERITY</th>
              <th>CASUALTIES</th>
              <th>STATUS</th>
              ${readOnly ? '' : '<th>ACTIONS</th>'}
            </tr>
          </thead>
          <tbody id="disaster-table-body">
            ${renderTableRows(state.events, { readOnly })}
          </tbody>
        </table>`
        }
      </div>

      ${
        readOnly
          ? ''
          : `
      <div class="disaster-form-panel" id="disaster-form-panel" ${state.editingId !== null ? '' : 'hidden'}>
        ${renderForm(form, formTitle)}
      </div>

      <div class="disaster-confirm" id="disaster-delete-confirm" ${state.pendingDeleteId ? '' : 'hidden'}>
        <div class="disaster-confirm__box">
          <p>&gt; [CONFIRM DELETE] 确定删除事件「${escapeHtml(truncate(deleteTarget?.title, 36))}」？此操作不可撤销。</p>
          <div class="disaster-confirm__actions">
            <button type="button" id="disaster-delete-confirm-yes">[ CONFIRM ]</button>
            <button type="button" id="disaster-delete-confirm-no">[ CANCEL ]</button>
          </div>
        </div>
      </div>`
      }
      </div>
    </section>
  `
}

function readFiltersFromDom() {
  const form = document.getElementById('disaster-filters')
  if (!form) return state.filters
  const data = new FormData(form)
  return {
    disaster_type: String(data.get('disaster_type') || ''),
    country: String(data.get('country') || ''),
    severity: String(data.get('severity') || ''),
    keyword: String(data.get('keyword') || ''),
  }
}

function readFormFromDom() {
  const form = document.getElementById('disaster-event-form')
  if (!form) return emptyEventForm()
  const data = new FormData(form)
  return Object.fromEntries(data.entries())
}

function syncFilterSelects() {
  const form = document.getElementById('disaster-filters')
  if (!form) return
  form.disaster_type.value = state.filters.disaster_type || ''
  form.country.value = state.filters.country || ''
  form.severity.value = state.filters.severity || ''
  form.keyword.value = state.filters.keyword || ''
}

function updateTableBody() {
  const body = document.getElementById('disaster-table-body')
  const count = document.getElementById('disaster-count')
  const wrap = document.getElementById('disaster-table-wrap')

  if (count) count.textContent = String(state.events.length)

  if (state.loading) {
    if (wrap) wrap.innerHTML = '<p class="disaster-loading">&gt; FETCHING DISASTER_RECORDS...</p>'
    return
  }

  if (!body && wrap) {
    wrap.innerHTML = `
      <table class="disaster-table">
        <thead>
          <tr>
            <th>TITLE</th>
            <th>TYPE</th>
            <th>LOCATION</th>
            <th>DATE</th>
            <th>SEVERITY</th>
            <th>CASUALTIES</th>
            <th>STATUS</th>
            <th>ACTIONS</th>
          </tr>
        </thead>
        <tbody id="disaster-table-body">${renderTableRows(state.events, { readOnly: state.mode === 'query' })}</tbody>
      </table>`
    return
  }

  if (body) body.innerHTML = renderTableRows(state.events, { readOnly: state.mode === 'query' })
}

async function loadEvents({ silent = false } = {}) {
  if (!silent) {
    state.loading = true
    updateTableBody()
  }

  const { data, error } = await listDisasterEvents(state.filters)
  state.loading = false

  if (error) {
    showTerminalNotice(error.message || '加载灾害事件失败', 'error')
    state.events = []
    updateTableBody()
    return
  }

  state.events = data
  updateTableBody()
}

function openCreateForm() {
  state.editingId = 'new'
  state.pendingDeleteId = null
  rerenderFormPanel(emptyEventForm(), '[ NEW DISASTER EVENT ]')
  document.getElementById('disaster-form-panel')?.removeAttribute('hidden')
}

function openEditForm(id) {
  const event = state.events.find((e) => e.id === id)
  if (!event) return
  state.editingId = id
  state.pendingDeleteId = null
  rerenderFormPanel(eventToForm(event), '[ EDIT DISASTER EVENT ]')
  document.getElementById('disaster-form-panel')?.removeAttribute('hidden')
}

function closeFormPanel() {
  state.editingId = null
  document.getElementById('disaster-form-panel')?.setAttribute('hidden', '')
}

function rerenderFormPanel(form, title, error = '') {
  const panel = document.getElementById('disaster-form-panel')
  if (!panel) return
  panel.innerHTML = renderForm(form, title, error)
  bindFormHandlers()
}

function bindFormHandlers() {
  document.getElementById('disaster-form-cancel')?.addEventListener('click', closeFormPanel)
  document.getElementById('disaster-event-form')?.addEventListener('submit', handleFormSubmit)
}

async function handleFormSubmit(e) {
  e.preventDefault()
  if (state.submitting) return
  const formValues = readFormFromDom()
  const parsed = parseEventPayload(formValues)
  if (parsed.error) {
    rerenderFormPanel(
      formValues,
      state.editingId && state.editingId !== 'new' ? '[ EDIT DISASTER EVENT ]' : '[ NEW DISASTER EVENT ]',
      parsed.error.message,
    )
    return
  }

  const isEdit = Boolean(state.editingId && state.editingId !== 'new')
  const currentUser = getCurrentUser() || state.user
  state.submitting = true
  rerenderFormPanel(
    formValues,
    isEdit ? '[ EDIT DISASTER EVENT ]' : '[ NEW DISASTER EVENT ]',
  )

  const result = isEdit
    ? await updateDisasterEvent(state.editingId, parsed.payload)
    : await createDisasterEvent(parsed.payload, currentUser)
  state.submitting = false

  if (result.error) {
    const msg = result.error.message || (isEdit ? '更新失败' : '创建失败')
    if (result.stale) {
      state.user = null
    }
    rerenderFormPanel(formValues, isEdit ? '[ EDIT DISASTER EVENT ]' : '[ NEW DISASTER EVENT ]', msg)
    showTerminalNotice(msg, 'error')
    return
  }

  closeFormPanel()
  showTerminalNotice(isEdit ? '灾害事件已更新' : '灾害事件已创建')
  await loadEvents({ silent: true })
}

function openDeleteConfirm(id) {
  state.pendingDeleteId = id
  const panel = document.getElementById('disaster-delete-confirm')
  const event = state.events.find((e) => e.id === id)
  if (panel) {
    panel.querySelector('p').textContent = `> [CONFIRM DELETE] 确定删除事件「${truncate(event?.title, 36)}」？此操作不可撤销。`
    panel.removeAttribute('hidden')
  }
}

function closeDeleteConfirm() {
  state.pendingDeleteId = null
  document.getElementById('disaster-delete-confirm')?.setAttribute('hidden', '')
}

async function confirmDelete() {
  if (!state.pendingDeleteId || state.deleting) return
  state.deleting = true
  const confirmButton = document.getElementById('disaster-delete-confirm-yes')
  if (confirmButton) {
    confirmButton.disabled = true
    confirmButton.textContent = '[ DELETING... ]'
  }
  const { error } = await deleteDisasterEvent(state.pendingDeleteId)
  state.deleting = false
  closeDeleteConfirm()

  if (error) {
    showTerminalNotice(error.message || '删除失败', 'error')
    return
  }

  showTerminalNotice('灾害事件已删除')
  await loadEvents({ silent: true })
}

export function bindDisasterDashboard({ user, onNavigate, mode = 'console' }) {
  state.user = user || getCurrentUser()
  state.mode = mode
  state.onNavigate = onNavigate

  syncFilterSelects()

  document.getElementById('disaster-filters')?.addEventListener('submit', async (e) => {
    e.preventDefault()
    state.filters = readFiltersFromDom()
    await loadEvents()
    showTerminalNotice(`检索完成，共 ${state.events.length} 条记录`)
  })

  document.getElementById('disaster-filter-reset')?.addEventListener('click', async () => {
    state.filters = { disaster_type: '', country: '', severity: '', keyword: '' }
    const form = document.getElementById('disaster-filters')
    if (form) form.reset()
    await loadEvents()
    showTerminalNotice('筛选条件已重置')
  })

  document.getElementById('disaster-new-btn')?.addEventListener('click', openCreateForm)

  if (mode !== 'query') {
    document.getElementById('disaster-table-wrap')?.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-action]')
      if (!btn) return
      const id = btn.dataset.id
      if (btn.dataset.action === 'edit') openEditForm(id)
      if (btn.dataset.action === 'delete') openDeleteConfirm(id)
    })

    document.getElementById('disaster-delete-confirm-yes')?.addEventListener('click', confirmDelete)
    document.getElementById('disaster-delete-confirm-no')?.addEventListener('click', closeDeleteConfirm)
    bindFormHandlers()
  }

  loadEvents()
}

export function resetDisasterDashboardState() {
  state = {
    events: [],
    filters: { disaster_type: '', country: '', severity: '', keyword: '' },
    editingId: null,
    pendingDeleteId: null,
    loading: false,
    submitting: false,
    deleting: false,
    user: state.user,
    mode: state.mode,
    activeRoute: state.activeRoute,
    onNavigate: state.onNavigate,
  }
}
