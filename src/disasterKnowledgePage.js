import { supabase } from './supabase.js'
import { formatStatNumber } from './statFormat.js'
import { bindTerminalNavigation } from './terminalNav.js'

export const KNOWLEDGE_ENTRIES = [
  {
    id: 'earthquake',
    labelZh: '地震',
    labelEn: 'Earthquake',
    dbKeys: ['earthquake'],
    definition: '地壳快速释放能量引起的地面震动，常伴随余震与次生灾害。',
    causes: '板块构造运动、断层活动、火山活动或人类诱发（水库蓄水、采矿爆破等）。',
    impacts: '建筑倒塌、人员伤亡、交通与通信中断、引发滑坡或海啸等连锁反应。',
    advice: '就地躲避于坚固桌下或承重墙角；远离玻璃与悬挂物；震后撤离至开阔地带，警惕余震。',
  },
  {
    id: 'flood',
    labelZh: '洪水',
    labelEn: 'Flood',
    dbKeys: ['flood'],
    definition: '河流水位暴涨或强降雨导致的地表积水与淹没现象。',
    causes: '持续强降雨、融雪、风暴潮、堤坝溃决或城市排水系统超负荷。',
    impacts: '农田与居民区被淹、饮水污染、疫病风险上升、基础设施损毁。',
    advice: '向高处转移，勿涉水通行；切断电源与燃气；储备清洁饮水，避免接触污染水体。',
  },
  {
    id: 'storm',
    labelZh: '台风 / 风暴',
    labelEn: 'Storm',
    dbKeys: ['typhoon', 'storm'],
    definition: '强烈大气涡旋或强对流天气系统，常伴大风、暴雨与风暴潮。',
    causes: '热带海洋暖湿气流抬升、气压梯度加大及季节性温差变化。',
    impacts: '狂风摧毁设施、暴雨引发洪涝、沿海风暴潮侵蚀、航班与航运中断。',
    advice: '加固门窗与户外物品；远离海边与临时搭建物；关注预警等级，必要时提前撤离。',
  },
  {
    id: 'wildfire',
    labelZh: '山火',
    labelEn: 'Wildfire',
    dbKeys: ['wildfire'],
    definition: '林区或草原在干燥条件下失控蔓延的明火灾害。',
    causes: '高温干旱、雷击、人为用火疏忽或纵火，强风助长火势扩散。',
    impacts: '森林资源损失、空气质量恶化、威胁居民区、破坏生态与生物多样性。',
    advice: '发现火情立即报警；逆风侧撤离，勿深入烟雾区；佩戴口罩减少烟尘吸入。',
  },
  {
    id: 'drought',
    labelZh: '干旱',
    labelEn: 'Drought',
    dbKeys: ['drought'],
    definition: '长期降水显著偏少导致的持续性缺水状态。',
    causes: '高压系统长期控制、厄尔尼诺等气候异常、水资源过度开采与植被退化。',
    impacts: '农作物减产、人畜饮水困难、河湖水位下降、野火与沙尘风险升高。',
    advice: '节约用水、储备应急水源；农业区调整灌溉；关注官方旱情通报与配水安排。',
  },
  {
    id: 'landslide',
    labelZh: '滑坡',
    labelEn: 'Landslide',
    dbKeys: ['landslide'],
    definition: '斜坡岩土体在重力与水体浸润作用下沿滑动面整体或分散运动。',
    causes: '持续降雨、地震、不合理开挖削坡、植被破坏及水库蓄水诱发。',
    impacts: '掩埋道路与建筑、阻断河道、造成人员伤亡与交通瘫痪。',
    advice: '雨季避免在陡坡与沟谷停留；发现裂缝、鼓胀等前兆立即上报并撤离。',
  },
  {
    id: 'extreme_temperature',
    labelZh: '极端温度',
    labelEn: 'Extreme Temperature',
    dbKeys: ['extreme_temperature'],
    definition: '显著超出历史同期均值的持续高温或热浪天气过程。',
    causes: '副热带高压稳定、城市热岛效应、全球变暖背景下极端事件频率上升。',
    impacts: '中暑与热射病、电力负荷激增、农业干旱、森林火险等级升高。',
    advice: '避开午后高温时段外出；补充水分与电解质；关注老人、儿童等脆弱群体。',
  },
  {
    id: 'epidemic',
    labelZh: '流行病',
    labelEn: 'Epidemic',
    dbKeys: ['epidemic'],
    definition: '病原体在人群中超出预期水平传播的疾病暴发或流行事件。',
    causes: '病毒或细菌变异、人口流动、卫生条件不足、疫苗覆盖率低及聚集性活动。',
    impacts: '医疗资源挤兑、社会经济活动受限、高风险群体健康威胁加剧。',
    advice: '遵循官方防控指引；保持手卫生与通风；出现症状及时就医并减少聚集。',
  },
]

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

function renderTypeList(selectedId) {
  return KNOWLEDGE_ENTRIES.map((entry) => {
    const active = entry.id === selectedId ? ' is-active' : ''
    return `
      <button
        type="button"
        class="dkb-type-btn${active}"
        data-knowledge-id="${entry.id}"
        aria-pressed="${entry.id === selectedId}"
      >
        <span class="dkb-type-btn__zh">${escapeHtml(entry.labelZh)}</span>
        <span class="dkb-type-btn__en">${escapeHtml(entry.labelEn)}</span>
      </button>
    `
  }).join('')
}

function renderDetailPanel(entry, count, statsError) {
  if (!entry) {
    return `
      <div class="dkb-detail dkb-detail--empty">
        <p class="dkb-detail__prompt">&gt; 请选择左侧灾害类型以调取参考资料…</p>
      </div>
    `
  }

  const countHtml = statsError
    ? `<p class="dkb-detail__stat-error">&gt; [同步失败] ${escapeHtml(statsError)}</p>`
    : `
      <div class="dkb-detail__stat">
        <span class="dkb-detail__stat-label">数据库记录数量</span>
        <strong class="dkb-detail__stat-value">${escapeHtml(formatStatNumber(count))}</strong>
        <em class="dkb-detail__stat-hint">disaster_events · ${escapeHtml(entry.dbKeys.join(' + '))}</em>
      </div>
    `

  return `
    <article class="dkb-detail" aria-label="${escapeHtml(entry.labelZh)} 参考资料">
      <header class="dkb-detail__header">
        <p class="dkb-detail__kicker">[ REF_ENTRY / ${escapeHtml(entry.id.toUpperCase())} ]</p>
        <h2 class="dkb-detail__title">
          <span>${escapeHtml(entry.labelZh)}</span>
          <em>${escapeHtml(entry.labelEn)}</em>
        </h2>
      </header>
      <div class="dkb-detail__body">
        <section class="dkb-field">
          <h3>灾害定义 <span>DEFINITION</span></h3>
          <p>${escapeHtml(entry.definition)}</p>
        </section>
        <section class="dkb-field">
          <h3>主要成因 <span>CAUSES</span></h3>
          <p>${escapeHtml(entry.causes)}</p>
        </section>
        <section class="dkb-field">
          <h3>常见影响 <span>IMPACTS</span></h3>
          <p>${escapeHtml(entry.impacts)}</p>
        </section>
        <section class="dkb-field dkb-field--highlight">
          <h3>应急避险建议 <span>EMERGENCY ADVICE</span></h3>
          <p>${escapeHtml(entry.advice)}</p>
        </section>
        <section class="dkb-field dkb-field--stat">
          <h3>数据库记录数量 <span>DB RECORD COUNT</span></h3>
          ${countHtml}
        </section>
      </div>
    </article>
  `
}

export function renderKnowledgePage({ selectedId = 'earthquake', counts = {}, statsError = null, loading = true } = {}) {
  const entry = KNOWLEDGE_ENTRIES.find((e) => e.id === selectedId) || KNOWLEDGE_ENTRIES[0]
  const count = entry ? sumCounts(counts, entry.dbKeys) : 0

  return `
    <section class="vault-console vault-console--subpage" aria-label="灾害知识库">
      ${renderBackBar()}
      <section class="dkb-terminal">
        <header class="dkb-terminal__header">
          <p class="dkb-terminal__kicker">[ CRISIS_DATA / REFERENCE_ARCHIVE ]</p>
          <h1 class="dkb-terminal__title">
            <span class="dkb-terminal__title-en">DISASTER KNOWLEDGE BASE</span>
            <span class="dkb-terminal__title-zh">灾害知识库</span>
          </h1>
          <p class="dkb-terminal__subtitle">&gt; 终端参考资料库 · 常见灾害类型基础知识与应急提示</p>
        </header>
        <div class="dkb-terminal__layout">
          <aside class="dkb-terminal__list" aria-label="灾害类型列表">
            <p class="dkb-list__label">[ TYPE_INDEX ]</p>
            <div class="dkb-terminal__list-scroll">
              ${renderTypeList(entry?.id)}
            </div>
          </aside>
          <main class="dkb-terminal__main" aria-live="polite">
            ${loading
    ? '<div class="dkb-detail dkb-detail--loading"><p class="dkb-detail__prompt">&gt; 正在同步数据库统计…</p></div>'
    : renderDetailPanel(entry, count, statsError)}
          </main>
        </div>
        <footer class="dkb-terminal__footer">
          <span>SOURCE: STATIC_REFERENCE + disaster_type_stats</span>
          <span>ACCESS: AUTHENTICATED</span>
        </footer>
      </section>
    </section>
  `
}

function sumCounts(counts, keys) {
  return keys.reduce((sum, key) => sum + (Number(counts[key]) || 0), 0)
}

async function fetchTypeCounts() {
  const { data, error } = await supabase.from('disaster_type_stats').select('disaster_type, count')
  if (error) return { counts: {}, error: error.message }

  const counts = Object.fromEntries(
    (data || []).map((row) => [row.disaster_type, Number(row.count) || 0]),
  )
  return { counts, error: null }
}

function bindTypeSelection(root, state, onNavigate) {
  root.querySelectorAll('[data-knowledge-id]').forEach((button) => {
    button.addEventListener('click', () => {
      const id = button.dataset.knowledgeId
      if (!id || id === state.selectedId) return
      state.selectedId = id
      refreshDetail(root, state)
    })
  })
  bindTerminalNavigation({ onNavigate, root })
}

function refreshDetail(root, state) {
  const entry = KNOWLEDGE_ENTRIES.find((e) => e.id === state.selectedId) || KNOWLEDGE_ENTRIES[0]
  const main = root.querySelector('.dkb-terminal__main')
  const list = root.querySelector('.dkb-terminal__list')
  if (!main || !list) return

  const count = sumCounts(state.counts, entry.dbKeys)
  main.innerHTML = renderDetailPanel(entry, count, state.statsError)

  list.querySelectorAll('[data-knowledge-id]').forEach((btn) => {
    const active = btn.dataset.knowledgeId === entry.id
    btn.classList.toggle('is-active', active)
    btn.setAttribute('aria-pressed', String(active))
  })
}

export async function initKnowledgePage({ onNavigate, selectedId = 'earthquake' } = {}) {
  const app = document.getElementById('app')
  if (!app) return

  const state = {
    selectedId,
    counts: {},
    statsError: null,
    loading: true,
  }

  app.innerHTML = renderKnowledgePage(state)
  bindTypeSelection(app, state, onNavigate)

  const { counts, error } = await fetchTypeCounts()
  state.counts = counts
  state.statsError = error
  state.loading = false

  const main = app.querySelector('.dkb-terminal__main')
  if (main) {
    const entry = KNOWLEDGE_ENTRIES.find((e) => e.id === state.selectedId) || KNOWLEDGE_ENTRIES[0]
    const count = sumCounts(state.counts, entry.dbKeys)
    main.innerHTML = renderDetailPanel(entry, count, state.statsError)
  }
}
