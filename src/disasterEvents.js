import { supabase } from './supabase.js'

export const DISASTER_TYPE_LABELS = {
  earthquake: '地震',
  flood: '洪水',
  typhoon: '台风',
  storm: '风暴',
  epidemic: '流行病',
  drought: '干旱',
  extreme_temperature: '极端温度',
  landslide: '滑坡',
  wildfire: '山火',
  volcanic_activity: '火山活动',
  transport_accident: '交通事故',
  industrial_accident: '工业事故',
  hazardous_material: '危险品事故',
  other: '其他',
}

export const DISASTER_TYPES = Object.entries(DISASTER_TYPE_LABELS).map(([value, label]) => ({
  value,
  label,
}))

export const SEVERITY_LEVELS = [
  { value: 'critical', label: '特别重大' },
  { value: 'high', label: '重大' },
  { value: 'medium', label: '较大' },
  { value: 'low', label: '一般' },
]

export const STATUS_OPTIONS = [
  { value: 'active', label: '进行中' },
  { value: 'monitoring', label: '监测中' },
  { value: 'resolved', label: '已处置' },
  { value: 'archived', label: '已归档' },
]

const TYPE_LABELS = DISASTER_TYPE_LABELS
const SEVERITY_LABELS = Object.fromEntries(SEVERITY_LEVELS.map((o) => [o.value, o.label]))
const STATUS_LABELS = Object.fromEntries(STATUS_OPTIONS.map((o) => [o.value, o.label]))

const COUNTRY_LABELS = {
  Afghanistan: '阿富汗',
  Argentina: '阿根廷',
  Australia: '澳大利亚',
  Bangladesh: '孟加拉国',
  Brazil: '巴西',
  Canada: '加拿大',
  Chile: '智利',
  China: '中国',
  Colombia: '哥伦比亚',
  Egypt: '埃及',
  Ethiopia: '埃塞俄比亚',
  France: '法国',
  Germany: '德国',
  India: '印度',
  Indonesia: '印度尼西亚',
  Iran: '伊朗',
  Iraq: '伊拉克',
  Italy: '意大利',
  Japan: '日本',
  Kenya: '肯尼亚',
  Madagascar: '马达加斯加',
  Mauritania: '毛里塔尼亚',
  Mexico: '墨西哥',
  Myanmar: '缅甸',
  Nepal: '尼泊尔',
  Nigeria: '尼日利亚',
  Pakistan: '巴基斯坦',
  Peru: '秘鲁',
  Philippines: '菲律宾',
  Russia: '俄罗斯',
  Somalia: '索马里',
  'South Africa': '南非',
  Spain: '西班牙',
  'Sri Lanka': '斯里兰卡',
  Thailand: '泰国',
  Turkey: '土耳其',
  'United Kingdom': '英国',
  'United States': '美国',
  USA: '美国',
  Vietnam: '越南',
  Yemen: '也门',
  中国: '中国',
  印度: '印度',
  日本: '日本',
}

export function labelDisasterType(value) {
  const key = String(value || '').trim().toLowerCase()
  return TYPE_LABELS[key] || TYPE_LABELS[value] || value || '--'
}

export function buildDisasterCategoryDistribution(typeRows) {
  return (typeRows || [])
    .map((row) => ({
      key: String(row.disaster_type || '').trim(),
      label: labelDisasterType(row.disaster_type),
      value: Number(row.count) || 0,
    }))
    .filter((d) => d.key && d.value > 0)
    .sort((a, b) => b.value - a.value)
}

export function labelCountry(value) {
  const raw = String(value || '').trim()
  if (!raw) return '--'
  if (/[\u4e00-\u9fff]/.test(raw)) return raw
  return COUNTRY_LABELS[raw] || COUNTRY_LABELS[raw.replace(/\s+/g, ' ')] || raw
}

function extractYear(event, title = '') {
  const fromTitle = String(title).match(/\b(19|20)\d{2}\b/)
  if (fromTitle) return fromTitle[0]
  const fromField = String(event?.start_year || '').trim()
  if (/^(19|20)\d{2}$/.test(fromField)) return fromField
  const fromDate = String(event?.event_date || '').slice(0, 4)
  if (/^(19|20)\d{2}$/.test(fromDate)) return fromDate
  return ''
}

export function localizeEventTitle(event) {
  const title = String(event?.title || '').trim()
  if (!title) return '--'
  if (/[\u4e00-\u9fff]/.test(title)) return title

  const country = labelCountry(event?.country)
  const type = labelDisasterType(event?.disaster_type)
  const year = extractYear(event, title)
  const yearPrefix = year ? `${year}年` : ''

  if (/cyclone/i.test(title) && /fani/i.test(title)) {
    return `${yearPrefix}${country}气旋“法尼”`
  }
  if (/extreme temperature/i.test(title)) {
    return `${yearPrefix}${country}${type === '--' ? '极端温度' : type}事件`
  }
  if (/earthquake/i.test(title)) {
    return `${yearPrefix}${country}地震`
  }
  if (/drought/i.test(title)) {
    return `${yearPrefix}${country}干旱`
  }
  if (/wildfire|forest fire/i.test(title)) {
    return `${yearPrefix}${country}山火`
  }
  if (/landslide/i.test(title)) {
    return `${yearPrefix}${country}滑坡灾害`
  }
  if (/flood/i.test(title)) {
    return `${yearPrefix}${country}${type === '--' ? '洪水' : type}灾害`
  }
  if (/typhoon|cyclone|hurricane/i.test(title)) {
    return `${yearPrefix}${country}${type === '--' ? '台风' : type}`
  }
  if (/storm/i.test(title)) {
    return `${yearPrefix}${country}风暴灾害`
  }

  if (country && type && country !== event?.country) {
    return `${yearPrefix}${country}${type}`
  }

  return title
}

export function labelSeverity(value) {
  return SEVERITY_LABELS[value] || value || '--'
}

export function labelStatus(value) {
  return STATUS_LABELS[value] || value || '--'
}

function escapeIlike(value) {
  return String(value || '').replace(/[%_\\]/g, '\\$&')
}

export async function listDisasterEvents(filters = {}) {
  let query = supabase
    .from('disaster_events')
    .select('*')
    .order('event_date', { ascending: false })
    .order('created_at', { ascending: false })

  if (filters.disaster_type) {
    query = query.eq('disaster_type', filters.disaster_type)
  }
  if (filters.country?.trim()) {
    query = query.ilike('country', `%${escapeIlike(filters.country.trim())}%`)
  }
  if (filters.severity) {
    query = query.eq('severity', filters.severity)
  }
  if (filters.keyword?.trim()) {
    const kw = escapeIlike(filters.keyword.trim())
    query = query.or(
      `title.ilike.%${kw}%,description.ilike.%${kw}%,region.ilike.%${kw}%,country.ilike.%${kw}%`,
    )
  }

  const { data, error } = await query
  return { data: data || [], error }
}

function crudError(action) {
  return { message: `${action}失败，请确认当前账号权限后重试。` }
}

export async function createDisasterEvent(payload, userRef) {
  if (!userRef?.id) return { data: null, error: crudError('创建') }

  const safePayload = { ...(payload || {}) }
  delete safePayload.created_by
  delete safePayload.created_by_auth

  const insertRow = {
    ...safePayload,
    updated_at: new Date().toISOString(),
    created_by_auth: userRef.id,
  }

  const { data, error } = await supabase
    .from('disaster_events')
    .insert(insertRow)
    .select('*')
    .single()

  return { data, error: error ? crudError('创建') : null }
}

export async function updateDisasterEvent(id, payload) {
  const { data, error } = await supabase
    .from('disaster_events')
    .update({
      ...payload,
      updated_at: new Date().toISOString(),
    })
    .eq('id', id)
    .select('*')
    .single()

  return { data, error: error ? crudError('更新') : data ? null : crudError('更新') }
}

export async function deleteDisasterEvent(id) {
  const { data, error } = await supabase.from('disaster_events').delete().eq('id', id).select('id').maybeSingle()
  return {
    data,
    error: error ? crudError('删除') : data ? null : { message: '未找到可删除的灾害事件。' },
  }
}

export async function countDisasterEvents() {
  const { count, error } = await supabase
    .from('disaster_events')
    .select('id', { count: 'exact', head: true })

  return { count: count ?? 0, error }
}

export function emptyEventForm() {
  return {
    title: '',
    disaster_type: 'earthquake',
    country: '',
    region: '',
    event_date: '',
    severity: 'medium',
    casualties: '0',
    affected_population: '0',
    economic_loss: '',
    description: '',
    source_name: '',
    source_url: '',
    status: 'active',
  }
}

export function eventToForm(event) {
  if (!event) return emptyEventForm()
  return {
    title: event.title || '',
    disaster_type: event.disaster_type || 'earthquake',
    country: event.country || '',
    region: event.region || '',
    event_date: event.event_date || '',
    severity: event.severity || 'medium',
    casualties: String(event.casualties ?? 0),
    affected_population: String(event.affected_population ?? 0),
    economic_loss: event.economic_loss != null ? String(event.economic_loss) : '',
    description: event.description || '',
    source_name: event.source_name || '',
    source_url: event.source_url || '',
    status: event.status || 'active',
  }
}

export function parseEventPayload(form) {
  const title = form.title?.trim()
  const country = form.country?.trim()
  const eventDate = form.event_date?.trim()

  if (!title) return { error: { message: '标题不能为空' } }
  if (!country) return { error: { message: '国家/地区不能为空' } }
  if (!eventDate) return { error: { message: '事件日期不能为空' } }

  const casualties = parseInt(form.casualties, 10)
  const affectedPopulation = parseInt(form.affected_population, 10)
  const economicLossRaw = String(form.economic_loss ?? '').trim()
  let economic_loss = null
  if (economicLossRaw) {
    economic_loss = Number(economicLossRaw)
    if (Number.isNaN(economic_loss) || economic_loss < 0) {
      return { error: { message: '经济损失必须为非负数字' } }
    }
  }

  return {
    payload: {
      title,
      disaster_type: form.disaster_type,
      country,
      region: form.region?.trim() || null,
      event_date: eventDate,
      severity: form.severity,
      casualties: Number.isNaN(casualties) ? 0 : Math.max(0, casualties),
      affected_population: Number.isNaN(affectedPopulation) ? 0 : Math.max(0, affectedPopulation),
      economic_loss,
      description: form.description?.trim() || null,
      source_name: form.source_name?.trim() || null,
      source_url: form.source_url?.trim() || null,
      status: form.status,
    },
  }
}

export function formatEventDate(value) {
  if (!value) return '--'
  return String(value).slice(0, 10)
}

export function formatNumber(value) {
  if (value == null || value === '') return '--'
  return Number(value).toLocaleString('zh-CN')
}
