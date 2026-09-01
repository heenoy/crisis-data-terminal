const LABELS = [
  ['Low', '低影响'],
  ['Moderate', '中等影响'],
  ['Severe', '严重影响'],
]

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char])
}

export function validateImpactOptions(body) {
  if (!body || body.success !== true) throw Object.assign(new Error('选项服务返回失败'), { code: body?.error?.code || 'OPTIONS_REJECTED' })
  if (!Array.isArray(body.countries) || body.countries.length === 0) throw Object.assign(new Error('国家或地区列表为空'), { code: 'EMPTY_COUNTRIES' })
  if (!Array.isArray(body.disaster_types) || body.disaster_types.length === 0) throw Object.assign(new Error('灾害类型列表为空'), { code: 'EMPTY_DISASTER_TYPES' })
  if (!Array.isArray(body.magnitude_scales)) throw Object.assign(new Error('强度量表结构错误'), { code: 'INVALID_MAGNITUDE_SCALES' })
  if (!Array.isArray(body.magnitude_groups)) throw Object.assign(new Error('灾害强度历史参考结构错误'), { code: 'INVALID_MAGNITUDE_GROUPS' })
  if (body.countries.some((item) => typeof item?.code !== 'string' || typeof item?.name !== 'string')) throw Object.assign(new Error('国家或地区选项结构错误'), { code: 'INVALID_COUNTRY_STRUCTURE' })
  if (body.disaster_types.some((item) => typeof item?.type !== 'string' || !Array.isArray(item?.subtypes))) throw Object.assign(new Error('灾害类型选项结构错误'), { code: 'INVALID_DISASTER_TYPE_STRUCTURE' })
  if (body.magnitude_groups.some((item) => typeof item?.group_key !== 'string' || typeof item?.disaster_type !== 'string' || typeof item?.magnitude_scale !== 'string' || !Array.isArray(item?.references))) throw Object.assign(new Error('灾害强度历史参考结构错误'), { code: 'INVALID_MAGNITUDE_GROUP_STRUCTURE' })
  return body
}

export async function fetchImpactOptions({ fetchImpl = fetch, signal } = {}) {
  const response = await fetchImpl('/api/impact-options', { method: 'GET', headers: { Accept: 'application/json' }, signal })
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.toLowerCase().includes('application/json')) {
    throw Object.assign(new Error('选项接口没有返回JSON'), { code: 'OPTIONS_NOT_JSON', status: response.status, contentType })
  }
  const body = await response.json()
  if (!response.ok) throw Object.assign(new Error(body?.error?.message || '选项请求失败'), { code: body?.error?.code || 'OPTIONS_HTTP_ERROR', status: response.status })
  return validateImpactOptions(body)
}

export function renderImpactAnalysis() {
  return `
    <section class="impact-analysis vault-console vault-console--subpage" aria-labelledby="impact-analysis-title">
      <div class="terminal-page-scroll impact-analysis__scroll">
        <header class="impact-analysis__header">
          <div class="impact-analysis__meta">
            <p class="impact-analysis__eyebrow">[ VAULT-0 / IMPACT LEVEL PREDICTION ]</p>
            <span class="impact-analysis__model-tag" title="冻结模型版本：三级 Random Forest T2" aria-label="冻结模型版本：三级 Random Forest T2">MODEL: RF-T2</span>
          </div>
          <h1 id="impact-analysis-title">灾害影响等级预测</h1>
          <p>根据灾害发生时可获取的信息，预测其可能的影响等级。</p>
        </header>
        <div class="impact-analysis__layout">
        <main class="impact-analysis__main">
        <form class="impact-form" data-impact-form>
          <label>国家或地区<select name="country_code" required><option value="">正在加载...</option></select></label>
          <label>灾害类型<select name="disaster_type" required><option value="">请选择</option></select></label>
          <label>灾害子类型<select name="disaster_subtype" required disabled><option value="">请先选择灾害类型</option></select></label>
          <div class="impact-form__date-row">
            <label>日期精度<select name="date_granularity" required>
              <option value="day">精确到日</option><option value="month">精确到月</option><option value="year">仅年份</option>
            </select></label>
            <label>发生日期<input name="event_date" required placeholder="YYYY-MM-DD" autocomplete="off"></label>
          </div>
          <div class="impact-form__date-row">
            <label>灾害强度（Magnitude，可选）
              <span class="impact-form__magnitude-input"><input name="magnitude" type="number" step="any" inputmode="decimal" placeholder="请先选择灾害类型和量表" list="impact-magnitude-references"><span data-impact-magnitude-unit></span></span>
              <datalist id="impact-magnitude-references" data-impact-magnitude-datalist></datalist>
            </label>
            <label>强度量表（可选）<select name="magnitude_scale" disabled><option value="">请先选择灾害类型</option></select></label>
          </div>
          <p class="impact-form__hint" data-impact-magnitude-hint>灾害强度仅在相同灾害类型与量表语义组内进行相对比较，不同量表不可直接比较。</p>
          <div class="impact-magnitude-references" data-impact-magnitude-references hidden aria-live="polite"></div>
          <div class="impact-form__error" data-impact-error role="alert" hidden>
            <span data-impact-error-message></span>
            <button type="button" class="impact-form__retry" data-impact-options-retry hidden>[ 重新加载输入选项 ]</button>
          </div>
          <button class="impact-form__submit" type="submit">[ 开始预测 / RUN ]</button>
        </form>
        <section class="impact-result" data-impact-result aria-live="polite">
          <div class="impact-result__empty">完成输入后，这里会同时显示低影响、中等影响、严重影响三类等级概率。</div>
        </section>
        </main>
        </div>
      </div>
    </section>`
}

export function formatReferenceFactors(referenceFactors = []) {
  return referenceFactors.flatMap((factor) => {
    const text = String(factor || '')
    if (/日期仅有年份|月份作为缺失处理/.test(text)) return []
    if (/^(冻结历史档案频次|冻结历史档案条数)：/.test(text)) return [text.replace(/^(冻结历史档案频次|冻结历史档案条数)：/, '同类历史档案：').replace(/(\d+)$/, '$1条')]
    if (/^事件年度HDI背景值：/.test(text)) return [text.replace('事件年度HDI背景值：', '事发年份人类发展指数（HDI）：')]
    if (/^HDI背景信息缺失/.test(text)) return ['事发年份人类发展指数（HDI）：暂无对应数据']
    const magnitude = text.match(/^Magnitude同语义组内相对位置：(-?\d+(?:\.\d+)?)/)
    if (magnitude) {
      const value = Number(magnitude[1])
      const position = value < -0.5 ? '偏低' : value > 0.5 ? '偏高' : '接近一般水平'
      return [`灾害强度：在同类历史记录中${position}`]
    }
    if (/^Magnitude未提供/.test(text)) return ['灾害强度：未提供']
    if (/Magnitude组内标准化依据/.test(text)) return ['灾害强度：当前类型与量表暂无可用的同类比较依据']
    return [text]
  })
}

function renderResult(body) {
  const probabilities = LABELS.map(([key, zh]) => {
    const value = Number(body.prediction.probabilities[key] || 0)
    return `<div class="impact-probability"><div><span>${zh}</span><strong>${(value * 100).toFixed(1)}%</strong></div><div class="impact-probability__track"><i style="width:${Math.max(0, Math.min(100, value * 100))}%"></i></div></div>`
  }).join('')
  const levelZh = Object.fromEntries(LABELS)[body.prediction.level] || body.prediction.label_zh
  const factors = formatReferenceFactors(body.reference_factors)
  const warnings = body.input_quality.warnings.length
    ? `<div class="impact-result__warnings"><h3>数据完整性</h3><ul>${body.input_quality.warnings.map((x) => `<li>${escapeHtml(x)}</li>`).join('')}</ul></div>` : ''
  return `<div class="impact-result__level"><strong>预测等级：${escapeHtml(levelZh)}（${escapeHtml(body.prediction.level)}）</strong></div>
    <section class="impact-result__probabilities"><h2>等级概率分布</h2>${probabilities}<p class="impact-result__note">模型输出概率用于比较三个等级的相对倾向。</p></section>
    <div class="impact-result__factors"><h2>本次判断依据</h2><ul>${factors.map((x) => `<li>${escapeHtml(x)}</li>`).join('')}</ul></div>
    ${warnings}`
}

export function buildPredictionSummary(body, closeThreshold = 0.05) {
  const probabilities = body?.prediction?.probabilities || {}
  const ordered = ['Low', 'Moderate', 'Severe']
    .map((label) => ({ label, value: Number(probabilities[label]) }))
    .filter((item) => Number.isFinite(item.value))
    .sort((a, b) => b.value - a.value)
  const top = ordered[0]
  if (!top) return '分析已完成，请结合完整的等级概率分布理解本次结果。'
  const labelZh = Object.fromEntries(LABELS)
  const second = ordered[1]
  if (second && top.value - second.value <= closeThreshold) {
    return `“${labelZh[top.label]}”与“${labelZh[second.label]}”的输出概率较为接近，建议结合完整的概率分布理解本次结果。`
  }
  return `根据历史档案的相似特征，本次输入更接近“${labelZh[top.label]}”等级。`
}

function formatReferenceValue(value, scale) {
  if (scale === 'Moment Magnitude' || scale === '°C') return Number(value.toFixed(1)).toString()
  if (scale === 'Kph') return Math.round(value).toString()
  if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString('zh-CN')
  return Number(value.toFixed(1)).toString()
}

export function initImpactAnalysis() {
  const form = document.querySelector('[data-impact-form]')
  if (!form) return
  const country = form.elements.country_code
  const type = form.elements.disaster_type
  const subtype = form.elements.disaster_subtype
  const granularity = form.elements.date_granularity
  const dateInput = form.elements.event_date
  const scale = form.elements.magnitude_scale
  const result = document.querySelector('[data-impact-result]')
  const magnitudeHint = document.querySelector('[data-impact-magnitude-hint]')
  const magnitudeInput = form.elements.magnitude
  const magnitudeUnit = document.querySelector('[data-impact-magnitude-unit]')
  const magnitudeDatalist = document.querySelector('[data-impact-magnitude-datalist]')
  const magnitudeReferences = document.querySelector('[data-impact-magnitude-references]')
  const error = document.querySelector('[data-impact-error]')
  const errorMessage = error.querySelector('[data-impact-error-message]')
  const retry = error.querySelector('[data-impact-options-retry]')
  let options
  let loadPromise = null
  let loadController = null
  let predictionController = null
  let bubbleTimer = null
  const isActive = () => form.isConnected && document.querySelector('[data-impact-form]') === form
  const setAiStatus = (state, detail = '') => {
    if (!isActive()) return
    const messages = {
      loading: '正在读取可用的灾害档案索引，请稍候。',
      retrying: '正在重新读取灾害档案索引，请稍候。',
      ready: '档案索引已载入，可以开始输入。',
      incomplete: '输入信息还不完整。请检查必填字段后再提交分析。',
      blocking_error: '输入选项没有成功载入。你可以重新尝试；在数据恢复前，我不会提交不完整的分析。',
      analyzing: '信息已接收，正在与历史灾害档案进行比对。',
      success: detail || '预测已完成，请结合等级概率分布理解本次结果。',
      failure: '本次预测未能完成，请检查输入或稍后重试。',
    }
    if (bubbleTimer) window.clearTimeout(bubbleTimer)
    ensureAiMascotBubble(messages[state])
    if (state === 'ready') {
      bubbleTimer = window.setTimeout(() => {
        if (isActive()) hideAiMascotBubble({ clear: true })
      }, 1800)
    }
  }
  const setOptionState = (state, message = '') => {
    if (!isActive()) return
    form.dataset.optionsState = state
    const busy = state === 'loading' || state === 'retrying'
    country.disabled = busy || state === 'blocking_error'
    type.disabled = busy || state === 'blocking_error'
    retry.hidden = state !== 'blocking_error'
    error.hidden = !message
    errorMessage.textContent = message
    if (busy) {
      country.innerHTML = `<option value="">${state === 'retrying' ? '正在重新加载...' : '正在加载...'}</option>`
      type.innerHTML = '<option value="">正在加载...</option>'
    }
    if (state === 'blocking_error') {
      country.innerHTML = '<option value="">国家或地区选项载入失败</option>'
      type.innerHTML = '<option value="">灾害类型选项载入失败</option>'
    }
    setAiStatus(state)
  }
  const loadOptions = (retrying = false) => {
    if (loadPromise) return loadPromise
    setOptionState(retrying ? 'retrying' : 'loading')
    loadController = new AbortController()
    loadPromise = fetchImpactOptions({ signal: loadController.signal })
      .then((loaded) => {
        if (!isActive()) return
        options = loaded
        country.innerHTML = '<option value="">请选择国家或地区</option>' + options.countries.map((x) => `<option value="${escapeHtml(x.code)}">${escapeHtml(x.name)} (${escapeHtml(x.code)})</option>`).join('')
        type.innerHTML = '<option value="">请选择灾害类型</option>' + options.disaster_types.map((x) => `<option value="${escapeHtml(x.type)}">${escapeHtml(x.type)}</option>`).join('')
        setOptionState('ready')
      })
      .catch((reason) => {
        if (!isActive() || reason?.name === 'AbortError') return
        console.warn('[impact-options]', { code: reason?.code || 'OPTIONS_LOAD_FAILED', status: reason?.status || null, contentType: reason?.contentType || null })
        const message = reason?.code === 'OPTIONS_NOT_JSON'
          ? '输入选项服务返回了网页而不是JSON。请确认使用 npm run dev 启动完整环境后重试。'
          : '国家、灾害类型等输入选项没有成功载入。请重新加载后再进行分析。'
        setOptionState('blocking_error', message)
      })
      .finally(() => { loadPromise = null })
    return loadPromise
  }
  retry.addEventListener('click', () => loadOptions(true))
  loadOptions(false)
  const clearMagnitude = (message = '') => {
    const hadValue = magnitudeInput.value.trim() !== ''
    magnitudeInput.value = ''
    magnitudeDatalist.innerHTML = ''
    magnitudeReferences.innerHTML = ''
    magnitudeReferences.hidden = true
    magnitudeUnit.textContent = ''
    if (hadValue && message) magnitudeHint.textContent = message
  }
  const groupsForSelection = () => (options?.magnitude_groups || []).filter((item) => {
    if (item.disaster_type !== type.value) return false
    return item.grouping_strategy.startsWith('disaster_type') || item.group_name === subtype.value
  })
  const updateMagnitudeScales = () => {
    const groups = groupsForSelection()
    const scales = [...new Set(groups.map((item) => item.magnitude_scale))]
    scale.disabled = !type.value || scales.length === 0
    scale.innerHTML = !type.value
      ? '<option value="">请先选择灾害类型</option>'
      : scales.length
        ? '<option value="">请选择量表</option>' + scales.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('')
        : '<option value="">当前类型无适用量表</option>'
    magnitudeInput.placeholder = scales.length ? '选择量表后查看历史参考' : '当前组合无统一灾害强度参考'
  }
  const updateMagnitudeReferences = () => {
    const selectedGroup = groupsForSelection().find((item) => item.magnitude_scale === scale.value)
    magnitudeDatalist.innerHTML = ''
    magnitudeReferences.innerHTML = ''
    magnitudeReferences.hidden = true
    magnitudeUnit.textContent = selectedGroup?.unit_label || ''
    if (!selectedGroup) {
      magnitudeInput.placeholder = type.value ? '请选择适用量表' : '请先选择灾害类型和量表'
      magnitudeHint.textContent = '灾害强度仅在相同灾害类型与量表语义组内进行相对比较，不同量表不可直接比较。'
      return
    }
    if (!selectedGroup.eligible || !selectedGroup.references?.length) {
      magnitudeInput.placeholder = '当前组合无统一灾害强度参考'
      magnitudeHint.textContent = '当前灾害类型与量表暂无可靠参考值，可留空。'
      return
    }
    const buttons = selectedGroup.references.map((reference) => {
      const display = formatReferenceValue(Number(reference.value), selectedGroup.magnitude_scale)
      return `<button type="button" class="impact-magnitude-reference" data-impact-magnitude-value="${escapeHtml(reference.value)}"><span>${escapeHtml(reference.label)}</span><strong>${escapeHtml(display)} ${escapeHtml(selectedGroup.unit_label)}</strong></button>`
    }).join('')
    magnitudeDatalist.innerHTML = selectedGroup.references.map((reference) => `<option value="${escapeHtml(reference.value)}">${escapeHtml(reference.label)}</option>`).join('')
    magnitudeReferences.innerHTML = `<span class="impact-magnitude-references__label">历史参考：</span>${buttons}`
    magnitudeReferences.hidden = false
    magnitudeInput.placeholder = selectedGroup.magnitude_scale === 'Moment Magnitude' ? '例如 6.5' : selectedGroup.magnitude_scale === 'Kph' ? '例如 120 km/h' : `请输入 ${selectedGroup.unit_label}`
    magnitudeHint.textContent = `参考值来自当前语义组的历史分位数（${selectedGroup.sample_count}条有效记录），仅表示组内相对位置，不是规定档位。`
  }
  type.addEventListener('change', () => {
    if (!options) return
    clearMagnitude('灾害类型已更改，原灾害强度值已清除，请重新选择量表。')
    const selected = options.disaster_types.find((x) => x.type === type.value)
    subtype.disabled = !selected
    subtype.innerHTML = selected ? '<option value="">请选择灾害子类型</option>' + selected.subtypes.map((x) => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join('') : '<option value="">请先选择灾害类型</option>'
    updateMagnitudeScales()
    updateMagnitudeReferences()
  })
  subtype.addEventListener('change', () => {
    clearMagnitude('灾害子类型已更改，原灾害强度值已清除，请重新选择量表。')
    updateMagnitudeScales()
    updateMagnitudeReferences()
  })
  scale.addEventListener('change', () => {
    clearMagnitude('强度量表已更改，原数值已清除。')
    updateMagnitudeReferences()
  })
  magnitudeReferences.addEventListener('click', (event) => {
    const button = event.target.closest('[data-impact-magnitude-value]')
    if (!button) return
    magnitudeInput.value = button.dataset.impactMagnitudeValue
    magnitudeInput.focus()
  })
  granularity.addEventListener('change', () => {
    dateInput.placeholder = granularity.value === 'day' ? 'YYYY-MM-DD' : granularity.value === 'month' ? 'YYYY-MM' : 'YYYY'
  })
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); error.hidden = true
    if (!options || form.dataset.optionsState !== 'ready') {
      setOptionState('blocking_error', '输入选项尚未就绪，请先重新加载。')
      return
    }
    if (!form.reportValidity()) {
      setAiStatus('incomplete')
      return
    }
    const submit = form.querySelector('button[type="submit"]'); submit.disabled = true; submit.textContent = '[ 预测中... ]'
    setAiStatus('analyzing')
    const magnitudeText = form.elements.magnitude.value.trim()
    const payload = { country_code: country.value, disaster_type: type.value, disaster_subtype: subtype.value,
      event_date: dateInput.value.trim(), date_granularity: granularity.value,
      magnitude: magnitudeText === '' ? null : Number(magnitudeText), magnitude_scale: scale.value || null }
    try {
      predictionController = new AbortController()
      const response = await fetch('/api/predict-impact', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: predictionController.signal })
      const body = await response.json()
      if (!response.ok || !body.success) throw new Error(body?.error?.message || '影响等级预测失败')
      result.innerHTML = renderResult(body)
      setAiStatus('success', buildPredictionSummary(body))
    } catch (reason) {
      if (reason?.name === 'AbortError') return
      error.hidden = false; error.textContent = reason.message || '影响等级预测暂时不可用，请稍后重试。'
      setAiStatus('failure')
    } finally {
      submit.disabled = false; submit.textContent = '[ 开始预测 / RUN ]'
    }
  })
  window.addEventListener('hashchange', () => {
    loadController?.abort()
    predictionController?.abort()
    if (bubbleTimer) window.clearTimeout(bubbleTimer)
  }, { once: true })
}
import { ensureAiMascotBubble, hideAiMascotBubble } from '../../aiFace.js'
