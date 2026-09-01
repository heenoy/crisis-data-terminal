import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import path from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const { createClient } = require('@supabase/supabase-js')

function loadLocalEnv() {
  for (const name of ['.env', '.env.local']) {
    try {
      for (const line of readFileSync(name, 'utf8').split(/\r?\n/)) {
        const match = line.match(/^([^#=]+)=(.*)$/)
        if (!match || process.env[match[1].trim()] !== undefined) continue
        process.env[match[1].trim()] = match[2].trim().replace(/^['"]|['"]$/g, '')
      }
    } catch {}
  }
}

loadLocalEnv()
const previewUrl = process.env.PREVIEW_URL
const shareUrl = process.env.PREVIEW_SHARE_URL
const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL
const anonKey = process.env.SUPABASE_ANON_KEY || process.env.VITE_SUPABASE_ANON_KEY
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SECRET_KEY
const pythonExe = process.env.PREVIEW_VERIFY_PYTHON
const pythonDeps = path.resolve('.python-deps')
if (![previewUrl, shareUrl, supabaseUrl, anonKey, serviceKey, pythonExe].every(Boolean)) throw new Error('Preview verification environment is incomplete')

const ADMIN_ID = '241663c4-6b4f-487e-bff1-7de850695152'
const USER_ID = '17cdbe10-bf86-4d09-b554-efb94c95aeac'
const adminClient = createClient(supabaseUrl, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } })

async function sessionFor(userId) {
  const { data: userData, error: userError } = await adminClient.auth.admin.getUserById(userId)
  if (userError || !userData.user?.email) throw userError || new Error('Auth test user unavailable')
  const { data: linkData, error: linkError } = await adminClient.auth.admin.generateLink({ type: 'magiclink', email: userData.user.email })
  if (linkError || !linkData.properties?.hashed_token) throw linkError || new Error('Auth test link unavailable')
  const publicClient = createClient(supabaseUrl, anonKey, { auth: { persistSession: false, autoRefreshToken: false } })
  const { data, error } = await publicClient.auth.verifyOtp({ token_hash: linkData.properties.hashed_token, type: 'magiclink' })
  if (error || !data.session) throw error || new Error('Auth test session unavailable')
  return { client: publicClient, session: data.session }
}

const payloads = [
  { country_code: 'CHN', disaster_type: 'Flood', disaster_subtype: 'Flood (General)', event_date: '2023-07-15', date_granularity: 'day', magnitude: 1000, magnitude_scale: 'Km2' },
  { country_code: 'JPN', disaster_type: 'Earthquake', disaster_subtype: 'Ground movement', event_date: '2022-03', date_granularity: 'month', magnitude: 6.5, magnitude_scale: 'Moment Magnitude' },
  { country_code: 'USA', disaster_type: 'Storm', disaster_subtype: 'Tropical cyclone', event_date: '2021', date_granularity: 'year', magnitude: 150, magnitude_scale: 'Kph' },
]
const pythonCode = "import json,sys; from ml_inference.service import prediction_response; status,body=prediction_response(json.loads(sys.argv[1])); print(json.dumps({'status':status,'body':body},ensure_ascii=False))"
const localPredictions = payloads.map((payload) => {
  const run = spawnSync(pythonExe, ['-c', pythonCode, JSON.stringify(payload)], {
    cwd: process.cwd(), encoding: 'utf8', env: { ...process.env, PYTHONPATH: pythonDeps }, maxBuffer: 1024 * 1024,
  })
  if (run.status !== 0) throw new Error('Local frozen prediction failed')
  return JSON.parse(run.stdout.trim())
})

const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXECUTABLE || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' })
const context = await browser.newContext({ viewport: { width: 1280, height: 720 } })
const page = await context.newPage()
const consoleErrors = []
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
await page.goto(shareUrl, { waitUntil: 'domcontentloaded', timeout: 120000 })
await page.waitForURL(`${previewUrl}/**`, { timeout: 120000 })

async function completeBoot() {
  if (await page.locator('#app .vault-console').count()) return
  const overlay = page.locator('#launch-overlay')
  if (await overlay.count()) await overlay.click({ position: { x: 20, y: 20 } })
  const wake = page.locator('#wake-init-btn')
  await wake.waitFor({ state: 'visible', timeout: 30000 })
  await wake.click()
  await page.waitForSelector('#app .vault-console, #app .survivor-auth-shell', { timeout: 60000 })
}

const remote = await page.evaluate(async (requestPayloads) => {
  const request = async (url, init) => {
    const started = performance.now()
    const response = await fetch(url, init)
    return { status: response.status, contentType: response.headers.get('content-type') || '', body: await response.json(), elapsedMs: performance.now() - started }
  }
  const predictions = []
  for (const payload of requestPayloads) predictions.push(await request('/api/predict-impact', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }))
  return {
    health: await request('/api/health'),
    options: await request('/api/impact-options'),
    predictions,
    repeatedPrediction: await request('/api/predict-impact', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestPayloads[0]) }),
  }
}, payloads)

for (const [key, response] of [['health', remote.health], ['options', remote.options], ...remote.predictions.map((item, index) => [`prediction${index + 1}`, item]), ['repeatedPrediction', remote.repeatedPrediction]])
  if (response.status !== 200 || !response.contentType.includes('application/json')) throw new Error(`${key} contract failed`)
if (remote.options.body.countries.length < 200 || remote.options.body.disaster_types.length < 2) throw new Error('Preview options are incomplete')
if (JSON.stringify(remote.health.body.classes) !== JSON.stringify(['Low', 'Moderate', 'Severe'])) throw new Error('Preview class order changed')
let maxProbabilityDifference = 0
for (const [index, prediction] of remote.predictions.entries()) {
  if (prediction.body.prediction.level !== localPredictions[index].body.prediction.level) throw new Error('Preview label differs from local frozen pipeline')
  for (const label of ['Low', 'Moderate', 'Severe']) {
    maxProbabilityDifference = Math.max(maxProbabilityDifference, Math.abs(prediction.body.prediction.probabilities[label] - localPredictions[index].body.prediction.probabilities[label]))
  }
}
if (maxProbabilityDifference > 1e-12) throw new Error('Preview probabilities differ from local frozen pipeline')
if (JSON.stringify(remote.predictions[0].body) !== JSON.stringify(remote.repeatedPrediction.body)) throw new Error('Repeated Preview prediction changed')

const projectRef = new URL(supabaseUrl).hostname.split('.')[0]
const storageKey = `sb-${projectRef}-auth-token`
async function installSession(session) {
  await page.evaluate(({ key, value }) => localStorage.setItem(key, JSON.stringify(value)), { key: storageKey, value: session })
}
const userAuth = await sessionFor(USER_ID)
await installSession(userAuth.session)
await page.goto(`${previewUrl}/?verify=ordinary#/admin/dashboard`, { waitUntil: 'domcontentloaded', timeout: 120000 })
await completeBoot()
await page.waitForFunction(() => location.hash !== '#/admin/dashboard', null, { timeout: 30000 })
const ordinaryRoute = await page.evaluate(() => location.hash)
if (ordinaryRoute !== '#/user/overview') throw new Error('Ordinary user admin guard failed')

const { data: refreshed, error: refreshError } = await userAuth.client.auth.refreshSession({ refresh_token: userAuth.session.refresh_token })
if (refreshError || !refreshed.session) throw refreshError || new Error('Session refresh failed')
await userAuth.client.auth.signOut()

await page.evaluate((key) => { localStorage.removeItem(key); sessionStorage.setItem('crisis_user', JSON.stringify({ id: 'forged', role: 'admin' })) }, storageKey)
await page.goto(`${previewUrl}/?verify=forged#/admin/dashboard`, { waitUntil: 'domcontentloaded', timeout: 120000 })
await completeBoot()
await page.waitForFunction(() => location.hash !== '#/admin/dashboard', null, { timeout: 30000 })
const forgedRoute = await page.evaluate(() => location.hash)
if (forgedRoute !== '#/auth') throw new Error('Forged sessionStorage guard failed')

const adminAuth = await sessionFor(ADMIN_ID)
await page.evaluate((key) => sessionStorage.removeItem('crisis_user'), storageKey)
await installSession(adminAuth.session)
await page.goto(`${previewUrl}/?verify=admin#/admin/dashboard`, { waitUntil: 'domcontentloaded', timeout: 120000 })
await completeBoot()
await page.waitForFunction(() => location.hash === '#/admin/dashboard', null, { timeout: 30000 })
const adminRoute = await page.evaluate(() => location.hash)
await adminAuth.client.auth.signOut()

await browser.close()
console.log(JSON.stringify({
  health: { status: remote.health.status, model: remote.health.body.model, classes: remote.health.body.classes, elapsed_ms: Math.round(remote.health.elapsedMs) },
  options: { status: remote.options.status, countries: remote.options.body.countries.length, disaster_types: remote.options.body.disaster_types.length, elapsed_ms: Math.round(remote.options.elapsedMs) },
  predictions: remote.predictions.map((item, index) => ({ case: index + 1, status: item.status, level: item.body.prediction.level, elapsed_ms: Math.round(item.elapsedMs) })),
  prediction_consistency: { max_probability_difference: maxProbabilityDifference, repeat_elapsed_ms: Math.round(remote.repeatedPrediction.elapsedMs) },
  auth: { ordinary_admin_route: ordinaryRoute, forged_route: forgedRoute, admin_route: adminRoute, refresh: true, sign_out: true },
  console_errors: consoleErrors,
}, null, 2))
