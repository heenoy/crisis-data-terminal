export const HEALTH_STATE = Object.freeze({
  UNCHECKED: 'unchecked',
  LOADING: 'loading',
  READY: 'ready',
  DEGRADED: 'degraded',
  UNAVAILABLE: 'unavailable',
})

const EXPECTED_MODEL = 'Random Forest T2'
const EXPECTED_CLASSES = Object.freeze(['Low', 'Moderate', 'Severe'])

function nowIso() {
  return new Date().toISOString()
}

function elapsed(started) {
  return Math.max(0, Math.round(performance.now() - started))
}

function failure(code, label, started, state = HEALTH_STATE.UNAVAILABLE) {
  return { state, code, label, checkedAt: nowIso(), durationMs: elapsed(started), details: {} }
}

function classifyError(error, started, timedOut = false) {
  if (timedOut) return failure('TIMEOUT', '请求超时', started)
  if (error?.name === 'AbortError') return failure('CANCELLED', '检查已取消', started)
  if (error instanceof TypeError) return failure('NETWORK_ERROR', '网络连接失败', started)
  return failure('SERVICE_ERROR', '服务请求失败', started)
}

async function runTimed(task, timeoutMs, parentSignal) {
  const controller = new AbortController()
  let timedOut = false
  const abortFromParent = () => controller.abort()
  if (parentSignal?.aborted) controller.abort()
  else parentSignal?.addEventListener('abort', abortFromParent, { once: true })
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  try {
    return await task(controller.signal)
  } catch (error) {
    if (timedOut && error?.name === 'AbortError') throw Object.assign(new Error('timeout'), { name: 'AbortError', healthCheckTimedOut: true })
    throw error
  } finally {
    clearTimeout(timer)
    parentSignal?.removeEventListener('abort', abortFromParent)
  }
}

export async function checkDatabaseHealth({ getSession, countDisasters, signal, timeoutMs = 8000 }) {
  const started = performance.now()
  try {
    return await runTimed(async (requestSignal) => {
      const session = await getSession()
      if (!session) return failure('UNAUTHENTICATED', '管理员会话不可用', started)

      const result = await countDisasters(requestSignal)
      if (result?.error) {
        const status = Number(result.status || result.error.status || 0)
        const code = String(result.error.code || '')
        if (status === 401) return failure('UNAUTHENTICATED', '管理员会话已失效', started)
        if (status === 403 || code === '42501') return failure('FORBIDDEN', '当前会话没有读取权限', started)
        return failure('DATA_API_ERROR', 'Data API 返回错误', started)
      }
      if (!Number.isInteger(result?.count) || result.count < 0) {
        return failure('INVALID_RESPONSE', 'Data API 响应格式异常', started)
      }
      return {
        state: HEALTH_STATE.READY,
        code: 'READY',
        label: 'Data API 可用',
        checkedAt: nowIso(),
        durationMs: elapsed(started),
        details: { recordCount: result.count },
      }
    }, timeoutMs, signal)
  } catch (error) {
    return classifyError(error, started, error?.healthCheckTimedOut === true)
  }
}

async function readJsonResponse(response) {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.toLowerCase().includes('application/json')) throw new SyntaxError('non-json')
  return response.json()
}

export async function checkPredictionHealth({ fetchImpl = fetch, signal, timeoutMs = 12000 }) {
  const started = performance.now()
  try {
    return await runTimed(async (requestSignal) => {
      const response = await fetchImpl('/api/health', {
        method: 'GET',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        signal: requestSignal,
      })
      let body
      try {
        body = await readJsonResponse(response)
      } catch {
        return failure('INVALID_RESPONSE', '预测服务响应格式异常', started)
      }
      if (!response.ok || body?.success !== true || body?.status !== 'ready') {
        return failure('SERVICE_ERROR', '预测服务返回异常', started)
      }
      const classes = Array.isArray(body.classes) ? body.classes : []
      const contractValid = body.model === EXPECTED_MODEL &&
        classes.length === EXPECTED_CLASSES.length &&
        classes.every((label, index) => label === EXPECTED_CLASSES[index])
      if (!contractValid) return failure('CONTRACT_MISMATCH', '冻结模型合同异常', started, HEALTH_STATE.DEGRADED)
      return {
        state: HEALTH_STATE.READY,
        code: 'READY',
        label: '预测服务可用',
        checkedAt: nowIso(),
        durationMs: elapsed(started),
        details: { model: body.model, classes },
      }
    }, timeoutMs, signal)
  } catch (error) {
    return classifyError(error, started, error?.healthCheckTimedOut === true)
  }
}

export async function checkAiGeneration({ fetchImpl = fetch, signal, timeoutMs = 20000 }) {
  const started = performance.now()
  try {
    return await runTimed(async (requestSignal) => {
      const response = await fetchImpl('/api/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ question: '请用一句话说明洪水档案分析需要关注什么。', history: [] }),
        signal: requestSignal,
      })
      let body
      try {
        body = await readJsonResponse(response)
      } catch {
        return failure('INVALID_RESPONSE', 'AI服务响应格式异常', started)
      }
      if (!response.ok) return failure('SERVICE_ERROR', 'AI服务暂时不可用', started)
      if (typeof body?.answer !== 'string' || !body.answer.trim()) {
        return failure('INVALID_RESPONSE', 'AI服务响应格式异常', started)
      }
      return {
        state: HEALTH_STATE.READY,
        code: 'READY',
        label: '真实生成验证通过',
        checkedAt: nowIso(),
        durationMs: elapsed(started),
        details: { model: typeof body.model === 'string' ? body.model : '未返回' },
      }
    }, timeoutMs, signal)
  } catch (error) {
    return classifyError(error, started, error?.healthCheckTimedOut === true)
  }
}

export function aggregateHealth(results) {
  const values = Object.values(results)
  if (values.some((item) => item.state === HEALTH_STATE.LOADING)) {
    return { state: HEALTH_STATE.LOADING, label: '检查中' }
  }
  if (values.every((item) => item.state === HEALTH_STATE.UNCHECKED)) {
    return { state: HEALTH_STATE.UNCHECKED, label: '尚未检查' }
  }
  if (values.every((item) => item.state === HEALTH_STATE.READY)) {
    return { state: HEALTH_STATE.READY, label: '全部已检查服务正常' }
  }
  return { state: HEALTH_STATE.DEGRADED, label: '部分服务异常或未验证' }
}
