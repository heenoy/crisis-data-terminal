import assert from 'node:assert/strict'
import {
  HEALTH_STATE,
  aggregateHealth,
  checkAiGeneration,
  checkDatabaseHealth,
  checkPredictionHealth,
} from '../src/services/systemHealth.js'

function response(body, { status = 200, contentType = 'application/json' } = {}) {
  return new Response(contentType.includes('json') ? JSON.stringify(body) : String(body), {
    status,
    headers: { 'Content-Type': contentType },
  })
}

const databaseReady = await checkDatabaseHealth({
  getSession: async () => ({ user: { id: 'admin' } }),
  countDisasters: async () => ({ count: 16856, error: null, status: 200 }),
})
assert.equal(databaseReady.state, HEALTH_STATE.READY)
assert.equal(databaseReady.details.recordCount, 16856)

const unauthenticated = await checkDatabaseHealth({
  getSession: async () => null,
  countDisasters: async () => assert.fail('count request must not run without a session'),
})
assert.equal(unauthenticated.code, 'UNAUTHENTICATED')

const forbidden = await checkDatabaseHealth({
  getSession: async () => ({ user: { id: 'admin' } }),
  countDisasters: async () => ({ count: null, error: { code: '42501' }, status: 403 }),
})
assert.equal(forbidden.code, 'FORBIDDEN')
assert.equal(forbidden.details.recordCount, undefined)

const invalidDatabase = await checkDatabaseHealth({
  getSession: async () => ({ user: { id: 'admin' } }),
  countDisasters: async () => ({ count: '16856', error: null, status: 200 }),
})
assert.equal(invalidDatabase.code, 'INVALID_RESPONSE')

const predictionReady = await checkPredictionHealth({
  fetchImpl: async () => response({ success: true, status: 'ready', model: 'Random Forest T2', classes: ['Low', 'Moderate', 'Severe'] }),
})
assert.equal(predictionReady.state, HEALTH_STATE.READY)
assert.deepEqual(predictionReady.details.classes, ['Low', 'Moderate', 'Severe'])

const contractMismatch = await checkPredictionHealth({
  fetchImpl: async () => response({ success: true, status: 'ready', model: 'Other', classes: ['Low', 'Moderate', 'Severe'] }),
})
assert.equal(contractMismatch.code, 'CONTRACT_MISMATCH')
assert.equal(contractMismatch.state, HEALTH_STATE.DEGRADED)

const invalidPrediction = await checkPredictionHealth({
  fetchImpl: async () => response('<html></html>', { contentType: 'text/html' }),
})
assert.equal(invalidPrediction.code, 'INVALID_RESPONSE')

const networkFailure = await checkPredictionHealth({ fetchImpl: async () => { throw new TypeError('offline') } })
assert.equal(networkFailure.code, 'NETWORK_ERROR')

const timedOut = await checkPredictionHealth({
  timeoutMs: 5,
  fetchImpl: (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
  }),
})
assert.equal(timedOut.code, 'TIMEOUT')

const aiReady = await checkAiGeneration({
  fetchImpl: async () => response({ answer: '有效短回答', model: 'test-model' }),
})
assert.equal(aiReady.state, HEALTH_STATE.READY)
assert.equal(aiReady.details.model, 'test-model')

const aiInvalid = await checkAiGeneration({ fetchImpl: async () => response({ answer: '' }) })
assert.equal(aiInvalid.code, 'INVALID_RESPONSE')

assert.deepEqual(
  aggregateHealth({ database: databaseReady, prediction: predictionReady, ai: aiReady }),
  { state: HEALTH_STATE.READY, label: '全部已检查服务正常' },
)
assert.equal(
  aggregateHealth({ database: databaseReady, prediction: predictionReady, ai: { state: HEALTH_STATE.UNCHECKED } }).state,
  HEALTH_STATE.DEGRADED,
)

console.log(JSON.stringify({
  database: databaseReady.code,
  prediction: predictionReady.code,
  contractMismatch: contractMismatch.code,
  networkFailure: networkFailure.code,
  timeout: timedOut.code,
  ai: aiReady.code,
}, null, 2))
