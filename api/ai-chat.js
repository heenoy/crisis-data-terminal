import { createClient } from '@supabase/supabase-js'

const RESTRICTED_REPLY = '该终端仅支持灾害数据与应急知识相关问询。'
const DEFAULT_MODEL = 'deepseek-v4-flash'

const SCOPE_PATTERN =
  /灾害|应急|地震|洪水|台风|飓风|风暴|干旱|山火|野火|滑坡|泥石流|疫情|流行病|极端温度|高温|低温|死亡|伤亡|受影响|经济损失|统计|数据库|趋势|国家|地区|disaster|crisis|emergency|earthquake|flood|storm|typhoon|hurricane|drought|wildfire|landslide|epidemic|casualt|death|affected|economic|database|supabase|trend|country/i

const STATS_PATTERN =
  /统计|数据库|数量|多少|总数|趋势|排名|最多|最高|死亡|伤亡|受影响|经济损失|国家|地区|类型|severity|count|total|trend|rank|top|death|casualt|affected|economic|database|type|country/i

function json(res, status, body) {
  res.status(status).json(body)
}

function isInScope(question) {
  return SCOPE_PATTERN.test(question)
}

function needsStats(question) {
  return STATS_PATTERN.test(question)
}

function getSupabaseClient() {
  const url = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.VITE_SUPABASE_ANON_KEY

  if (!url || !key) return null
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  })
}

async function queryMaybe(promise) {
  const { data, error } = await promise
  if (error) return { error: error.message, data: null }
  return { error: null, data }
}

async function fetchStatsContext(question) {
  if (!needsStats(question)) return null

  const supabase = getSupabaseClient()
  if (!supabase) {
    return { warning: 'Supabase server environment variables are not configured.' }
  }

  const [dashboard, types, severities, yearly, latest] = await Promise.all([
    queryMaybe(supabase.from('dashboard_stats').select('*').single()),
    queryMaybe(supabase.from('disaster_type_stats').select('disaster_type,count').order('count', { ascending: false }).limit(10)),
    queryMaybe(supabase.from('severity_stats').select('severity,count').order('count', { ascending: false }).limit(6)),
    queryMaybe(supabase.from('yearly_disaster_stats').select('year,event_count,total_deaths,total_affected').order('year', { ascending: false }).limit(8)),
    queryMaybe(supabase.from('latest_events').select('title,country,disaster_type,severity,event_date,casualties,affected_population').limit(5)),
  ])

  return {
    dashboard: dashboard.data,
    topDisasterTypes: types.data || [],
    severityDistribution: severities.data || [],
    recentYears: yearly.data || [],
    latestEvents: latest.data || [],
    warnings: [dashboard, types, severities, yearly, latest]
      .filter((item) => item.error)
      .map((item) => item.error),
  }
}

function buildSystemPrompt(statsContext) {
  return [
    '你是 Crisis Data Terminal 的 AI 灾害问询终端。',
    '只回答灾害事件、灾害类型、灾害统计、应急知识、系统数据库相关问题。',
    `如果用户问无关内容，必须只回复：“${RESTRICTED_REPLY}”`,
    '回答使用中文，保持简洁、准确、终端分析员风格。',
    '涉及应急建议时提醒用户以当地官方预警和应急管理部门信息为准。',
    '不要编造数据库中不存在的精确数字；如果上下文没有提供数据，就说明需要查看数据库统计。',
    statsContext
      ? `以下是服务端从 Supabase 精简查询得到的数据库上下文，不是全量事件表：\n${JSON.stringify(statsContext)}`
      : '本次问题没有附加数据库统计上下文。',
  ].join('\n')
}

function normalizeHistory(history) {
  if (!Array.isArray(history)) return []
  return history
    .filter((item) => item && ['user', 'assistant'].includes(item.role) && item.content)
    .slice(-8)
    .map((item) => ({
      role: item.role,
      content: String(item.content).slice(0, 1000),
    }))
}

async function callDeepSeek({ question, history, statsContext }) {
  const apiKey = process.env.DEEPSEEK_API_KEY
  if (!apiKey) {
    throw new Error('DEEPSEEK_API_KEY is not configured')
  }

  const baseUrl = (process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com').replace(/\/$/, '')
  const model = process.env.DEEPSEEK_MODEL || DEFAULT_MODEL
  const messages = [
    { role: 'system', content: buildSystemPrompt(statsContext) },
    ...normalizeHistory(history),
    { role: 'user', content: question },
  ]

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.3,
      max_tokens: 900,
      stream: false,
    }),
  })

  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) throw new Error('DeepSeek API returned a non-JSON response')
  const payload = await response.json()
  if (!response.ok) {
    throw new Error(payload?.error?.message || `DeepSeek API error ${response.status}`)
  }

  const answer = payload?.choices?.[0]?.message?.content?.trim()
  if (!answer) throw new Error('DeepSeek API returned an empty answer')
  return answer
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Allow', 'POST, OPTIONS')
    return json(res, 204, {})
  }

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST, OPTIONS')
    return json(res, 405, { error: 'Method not allowed' })
  }

  const question = String(req.body?.question || '').trim().slice(0, 800)
  const history = req.body?.history

  if (!question) {
    return json(res, 400, { error: 'Question is required' })
  }

  if (!isInScope(question)) {
    return json(res, 200, { answer: RESTRICTED_REPLY, restricted: true })
  }

  try {
    const statsContext = await fetchStatsContext(question)
    const answer = await callDeepSeek({ question, history, statsContext })
    return json(res, 200, {
      answer,
      usedStats: Boolean(statsContext),
      model: process.env.DEEPSEEK_MODEL || DEFAULT_MODEL,
    })
  } catch (err) {
    console.error('[Crisis Data Terminal] ai-chat failed:', err)
    return json(res, 502, { error: 'AI service is temporarily unavailable' })
  }
}
