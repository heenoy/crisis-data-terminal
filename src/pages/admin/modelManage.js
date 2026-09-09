import * as echarts from 'echarts'
import registry from '../../data/model-registry.json'

const charts = []
let lastTrigger = null
let resizeObserver = null
const metric = (value) => value == null ? '—' : Number(value).toFixed(4)
const percent = (value) => value == null ? '未记录' : `${(value * 100).toFixed(1)}%`
const statusText = { Production: '正式使用', Candidate: '候选', Historical: '历史方案', Baseline: '基线' }
const scopeText = { historicalValidation: '历史 Validation', developmentOof: 'Development 时间CV OOF', lockedTest: '独立 Test 2022—2023' }

function modelCard(model) {
  return `<article class="model-archive-card" data-status="${model.status}">
    <div class="model-archive-card__top"><span class="model-status model-status--${model.status.toLowerCase()}">${statusText[model.status]}</span><span>${scopeText[model.evaluationScope]}</span></div>
    <h3>${model.displayName}</h3><p>${model.algorithm} · ${model.featureSet} · ${model.labelSet}</p>
    <dl class="model-metric-row"><div><dt>Macro F1</dt><dd>${metric(model.metrics.macro_f1)}</dd></div><div><dt>Balanced Accuracy</dt><dd>${metric(model.metrics.balanced_accuracy)}</dd></div><div><dt>Severe Recall</dt><dd>${metric(model.metrics.severe_recall)}</dd></div></dl>
    <p class="model-archive-card__conclusion">${model.conclusion}</p>
    <button type="button" data-model-detail="${model.id}" aria-label="查看${model.displayName}详情">[ 查看详情 ]</button>
  </article>`
}

function ciRows() {
  const labels = { accuracy: 'Accuracy', balanced_accuracy: 'Balanced Accuracy', macro_f1: 'Macro F1', weighted_f1: 'Weighted F1', severe_precision: 'Severe Precision', severe_recall: 'Severe Recall', severe_f1: 'Severe F1' }
  return Object.entries(labels).map(([key, label]) => {
    const ci = registry.experiments.bootstrapIntervals[key]
    return `<tr><th scope="row">${label}</th><td>${metric(ci.point_estimate)}</td><td>${metric(ci.ci_lower)}—${metric(ci.ci_upper)}</td></tr>`
  }).join('')
}

export function renderAdminModelManage() {
  const model = registry.frozenModel
  return `<section class="vault-console vault-console--subpage" aria-label="模型档案与实验结果"><div class="admin-portal admin-models">
    <header class="admin-portal__header"><div><p class="vault-kicker">[ ADMIN_PORTAL / MODEL ARCHIVE ]</p><h1>模型档案与实验结果</h1><p>只读展示当前正式模型、研究基线与验证证据。</p></div><span class="model-readonly-badge">READ ONLY</span></header>
    <section class="model-production" aria-labelledby="production-title"><div><p class="vault-kicker">[ CURRENT PRODUCTION ]</p><h2 id="production-title">${model.name}</h2></div><span class="model-frozen-badge">FROZEN / ${model.integrity}</span>
      <dl class="model-production-grid"><div><dt>任务类别</dt><dd>${model.classes.join(' / ')}</dd></div><div><dt>训练数据</dt><dd>Development ${model.development}</dd></div><div><dt>独立测试</dt><dd>Test ${model.test} · ${model.testRows}条</dd></div><div><dt>特征</dt><dd>${model.featureCount}项锁定特征</dd></div><div><dt>SHA-256</dt><dd title="${model.sha256}">${model.sha256.slice(0, 12)}…${model.sha256.slice(-8)}</dd></div><div><dt>状态</dt><dd>唯一 Production 模型</dd></div></dl>
    </section>
    <section class="model-section" aria-labelledby="archive-title"><div class="model-section__heading"><div><p class="vault-kicker">[ MODEL REGISTRY ]</p><h2 id="archive-title">模型档案</h2></div><p>不同评价口径分开标注，不构成跨口径性能排名。</p></div><div class="model-archive-grid">${registry.models.map(modelCard).join('')}</div></section>
    <section class="model-section" aria-labelledby="stability-title"><div class="model-section__heading"><div><p class="vault-kicker">[ EXPERIMENTS / STABILITY ]</p><h2 id="stability-title">实验与稳定性</h2></div><p>图表仅比较同一划分、标签和指标口径。</p></div>
      <div class="model-chart-grid"><figure><figcaption>Development OOF 综合指标</figcaption><div class="model-chart" data-chart="oof" role="img" aria-label="RF和LightGBM的Development OOF指标对比"></div></figure><figure><figcaption>各时间折 Severe Recall</figcaption><div class="model-chart" data-chart="recall" role="img" aria-label="各时间折Severe Recall折线图"></div></figure><figure><figcaption>各时间折 Severe F1</figcaption><div class="model-chart" data-chart="f1" role="img" aria-label="各时间折Severe F1折线图"></div></figure><figure><figcaption>RF-T2 独立Test混淆矩阵</figcaption><div class="model-chart" data-chart="confusion" role="img" aria-label="RF-T2独立Test混淆矩阵"></div></figure><figure class="model-chart-wide"><figcaption>Severe权重实验：Precision / Recall / F1</figcaption><div class="model-chart" data-chart="weights" role="img" aria-label="Severe权重实验指标变化"></div></figure></div>
      <div class="model-evidence-grid"><article><h3>Bootstrap 95%置信区间</h3><p>固定2022—2023 Test样本的分层事件级Bootstrap，不代表所有未来年份。</p><div class="model-table-wrap"><table><thead><tr><th>指标</th><th>点估计</th><th>95%区间</th></tr></thead><tbody>${ciRows()}</tbody></table></div></article><article><h3>实验结论</h3><ul>${registry.experiments.conclusions.map((item) => `<li>${item}</li>`).join('')}</ul><p>Severe→Low 是辅助分析中风险最高的低估方向；冻结Test中共有 ${registry.experiments.testConfusionMatrix.values[2][0]} 条。</p></article></div>
    </section>
    <dialog class="model-detail-dialog" aria-labelledby="model-detail-title"><div data-model-detail-content></div><button type="button" data-model-detail-close>[ 关闭详情 ]</button></dialog>
  </div></section>`
}

const axis = { axisLine: { lineStyle: { color: '#326b45' } }, axisLabel: { color: '#8bc99a' }, splitLine: { lineStyle: { color: 'rgba(88,255,128,.1)' } } }
function addChart(name, option) {
  const element = document.querySelector(`[data-chart="${name}"]`)
  if (!element) return
  const chart = echarts.init(element)
  chart.setOption({ color: ['#57f287', '#ffb454', '#58b6ff'], textStyle: { color: '#9eeaad', fontFamily: 'monospace' }, animation: !matchMedia('(prefers-reduced-motion: reduce)').matches, ...option })
  element.dataset.seriesCount = String(option.series?.length ?? 0)
  element.dataset.pointCount = String(option.series?.reduce((count, series) => count + (series.data?.length ?? 0), 0) ?? 0)
  charts.push(chart)
}
function initCharts() {
  const pooled = registry.experiments.pooledOof
  const base = { tooltip: { trigger: 'axis' }, legend: { textStyle: { color: '#9eeaad' } }, grid: { left: 52, right: 20, bottom: 38 } }
  addChart('oof', { ...base, xAxis: { type: 'category', data: ['Macro F1', 'Balanced Accuracy', 'Severe F1'], ...axis }, yAxis: { type: 'value', min: 0, max: 0.8, ...axis }, series: pooled.map((r) => ({ name: r.model, type: 'bar', data: [r.macro_f1, r.balanced_accuracy, r.severe_f1] })) })
  for (const [name, key] of [['recall', 'severeRecall'], ['f1', 'severeF1']]) addChart(name, { ...base, xAxis: { type: 'category', data: [1, 2, 3, 4].map((v) => `Fold ${v}`), ...axis }, yAxis: { type: 'value', min: 0, max: 0.7, ...axis }, series: ['RF_T2', 'LGBM_T2'].map((model) => ({ name: model, type: 'line', symbolSize: 8, data: registry.experiments.temporalFolds.filter((r) => r.model === model).map((r) => r[key]) })) })
  const cm = registry.experiments.testConfusionMatrix
  addChart('confusion', { tooltip: {}, grid: { left: 82, right: 28, bottom: 48, top: 24 }, xAxis: { type: 'category', name: '预测类别', data: cm.labels, ...axis }, yAxis: { type: 'category', name: '真实类别', data: cm.labels, ...axis }, visualMap: { min: 0, max: Math.max(...cm.values.flat()), show: false, inRange: { color: ['#06120a', '#1a6e36', '#72ff9a'] } }, series: [{ type: 'heatmap', data: cm.values.flatMap((row, y) => row.map((value, x) => [x, y, value])), label: { show: true, color: '#d8ffe0' } }] })
  const weights = registry.experiments.weightSearch
  addChart('weights', { ...base, tooltip: { trigger: 'axis', valueFormatter: (value) => Number(value).toFixed(4) }, xAxis: { type: 'category', name: 'Severe权重倍率', data: weights.map((r) => `×${r.weightMultiplier}`), ...axis }, yAxis: { type: 'value', min: 0, max: 0.9, ...axis }, series: [['Precision', 'severePrecision'], ['Recall', 'severeRecall'], ['F1', 'severeF1']].map(([label, key]) => ({ name: label, type: 'line', symbol: 'circle', symbolSize: 8, showSymbol: true, data: weights.map((r) => r[key]) })) })
}

function openDetails(model, trigger) {
  const dialog = document.querySelector('.model-detail-dialog')
  const content = dialog?.querySelector('[data-model-detail-content]')
  if (!dialog || !content || !model) return
  lastTrigger = trigger
  content.innerHTML = `<p class="vault-kicker">[ ${model.status.toUpperCase()} / ${scopeText[model.evaluationScope]} ]</p><h2 id="model-detail-title">${model.displayName}</h2><p>${model.conclusion}</p>${model.caveat ? `<p class="model-detail-warning">${model.caveat}</p>` : ''}<dl class="model-detail-grid"><div><dt>算法</dt><dd>${model.algorithm}</dd></div><div><dt>特征方案</dt><dd>${model.featureSet}</dd></div><div><dt>标签口径</dt><dd>${model.labelSet}</dd></div><div><dt>Macro F1</dt><dd>${metric(model.metrics.macro_f1)}</dd></div><div><dt>Balanced Accuracy</dt><dd>${metric(model.metrics.balanced_accuracy)}</dd></div><div><dt>Severe P / R / F1</dt><dd>${percent(model.metrics.severe_precision)} / ${percent(model.metrics.severe_recall)} / ${percent(model.metrics.severe_f1)}</dd></div></dl><p class="model-source">实验来源：${model.experimentSource}</p>`
  dialog.showModal()
}

export function initAdminModelManage() {
  document.querySelectorAll('[data-model-detail]').forEach((button) => button.addEventListener('click', () => openDetails(registry.models.find((model) => model.id === button.dataset.modelDetail), button)))
  const dialog = document.querySelector('.model-detail-dialog')
  dialog?.querySelector('[data-model-detail-close]')?.addEventListener('click', () => dialog.close())
  dialog?.addEventListener('close', () => lastTrigger?.focus())
  initCharts()
  resizeObserver = new ResizeObserver(() => charts.forEach((chart) => chart.resize()))
  document.querySelectorAll('.model-chart').forEach((element) => resizeObserver.observe(element))
}

export function destroyAdminModelManage() {
  resizeObserver?.disconnect()
  resizeObserver = null
  charts.splice(0).forEach((chart) => chart.dispose())
  lastTrigger = null
}
