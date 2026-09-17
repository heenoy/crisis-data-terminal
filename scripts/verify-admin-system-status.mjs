import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const { createClient } = require('@supabase/supabase-js')
for (const name of ['.env', '.env.local']) {
  try {
    for (const line of readFileSync(name, 'utf8').split(/\r?\n/)) {
      const match = line.match(/^([^#=]+)=(.*)$/)
      if (match && process.env[match[1].trim()] === undefined) process.env[match[1].trim()] = match[2].trim().replace(/^['"]|['"]$/g, '')
    }
  } catch {}
}

const baseUrl = process.env.SYSTEM_STATUS_VERIFY_URL || 'http://127.0.0.1:5173'
const previewShareUrl = process.env.SYSTEM_STATUS_PREVIEW_SHARE_URL
const verifyRealAi = process.env.SYSTEM_STATUS_VERIFY_REAL_AI === '1'
const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL
const anonKey = process.env.SUPABASE_ANON_KEY || process.env.VITE_SUPABASE_ANON_KEY
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SECRET_KEY
if (![supabaseUrl, anonKey, serviceKey].every(Boolean)) throw new Error('Verification environment is incomplete')

const ADMIN_ID = '241663c4-6b4f-487e-bff1-7de850695152'
const USER_ID = '17cdbe10-bf86-4d09-b554-efb94c95aeac'
const adminClient = createClient(supabaseUrl, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } })
async function sessionFor(id) {
  const { data: userData, error: userError } = await adminClient.auth.admin.getUserById(id)
  if (userError || !userData.user?.email) throw userError || new Error('Test user unavailable')
  const { data: link, error: linkError } = await adminClient.auth.admin.generateLink({ type: 'magiclink', email: userData.user.email })
  if (linkError) throw linkError
  const client = createClient(supabaseUrl, anonKey, { auth: { persistSession: false, autoRefreshToken: false } })
  const { data, error } = await client.auth.verifyOtp({ token_hash: link.properties.hashed_token, type: 'magiclink' })
  if (error || !data.session) throw error || new Error('Session unavailable')
  return data.session
}

const projectRef = new URL(supabaseUrl).hostname.split('.')[0]
const storageKey = `sb-${projectRef}-auth-token`
const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXECUTABLE || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
const consoleErrors = []
const pageErrors = []
let aiRequests = 0
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('request', (request) => { if (request.url().includes('/api/ai-chat')) aiRequests += 1 })

async function install(session) {
  await page.goto(baseUrl)
  await page.evaluate(({ key, session }) => localStorage.setItem(key, JSON.stringify(session)), { key: storageKey, session })
}
async function initializeShell() {
  const launch = page.locator('#launch-overlay')
  if (await launch.isVisible()) await launch.click({ position: { x: 20, y: 20 } })
  const wake = page.locator('#wake-init-btn')
  if (!await page.locator('#app .vault-console, #app .survivor-auth-shell').count()) {
    await wake.waitFor({ state: 'visible' })
    await wake.click()
  }
  await page.waitForSelector('#app .vault-console, #app .survivor-auth-shell')
}
async function boot(route) {
  await page.goto(`${baseUrl}/#/${route}`, { waitUntil: 'domcontentloaded' })
  await initializeShell()
}
async function waitForSafeChecks() {
  await page.waitForFunction(() => [...document.querySelectorAll('[data-health-card="database"], [data-health-card="prediction"]')].every((node) => node.dataset.state !== 'loading'))
}

if (previewShareUrl) await page.goto(previewShareUrl, { waitUntil: 'domcontentloaded' })

await boot('admin/system')
if (await page.evaluate(() => location.hash) !== '#/auth') throw new Error('Unauthenticated route guard failed')
await install(await sessionFor(USER_ID)); await boot('admin/system')
if (await page.evaluate(() => location.hash) !== '#/user/overview') throw new Error('User route guard failed')
await install(await sessionFor(ADMIN_ID)); await boot('admin/system'); await waitForSafeChecks()

const real = await page.evaluate(() => ({
  route: location.hash,
  title: document.querySelector('.admin-system-status h1')?.textContent,
  databaseState: document.querySelector('[data-health-card="database"]')?.dataset.state,
  databaseText: document.querySelector('[data-health-card="database"]')?.textContent,
  predictionState: document.querySelector('[data-health-card="prediction"]')?.dataset.state,
  predictionText: document.querySelector('[data-health-card="prediction"]')?.textContent,
  aiState: document.querySelector('[data-health-card="ai"]')?.dataset.state,
  summaryState: document.querySelector('[data-health-summary]')?.dataset.state,
  mascotCount: document.querySelectorAll('#ai-face').length,
  horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
}))
if (real.route !== '#/admin/system' || real.title !== '系统状态') throw new Error(`Admin route failed: ${JSON.stringify(real)}`)
if (real.databaseState !== 'ready' || !real.databaseText.includes('16,856 条')) throw new Error(`Real Data API check failed: ${JSON.stringify(real)}`)
if (real.predictionState !== 'ready' || !real.predictionText.includes('Random Forest T2') || !real.predictionText.includes('Low / Moderate / Severe')) throw new Error(`Real prediction check failed: ${JSON.stringify(real)}`)
if (real.aiState !== 'unchecked' || aiRequests !== 0) throw new Error(`AI must remain manual: ${JSON.stringify({ real, aiRequests })}`)
if (real.summaryState !== 'degraded' || real.mascotCount !== 1 || real.horizontalOverflow) throw new Error(`Summary or layout failed: ${JSON.stringify(real)}`)

let realAi = null
if (verifyRealAi) {
  await page.locator('[data-health-ai-check]').click()
  await page.waitForFunction(() => document.querySelector('[data-health-card="ai"]')?.dataset.state !== 'loading')
  realAi = await page.locator('[data-health-card="ai"]').evaluate((node) => ({
    state: node.dataset.state,
    verified: node.textContent.includes('真实生成验证通过'),
  }))
  if (realAi.state !== 'ready' || !realAi.verified || aiRequests !== 1) {
    throw new Error(`Real AI manual check failed: ${JSON.stringify({ realAi, aiRequests })}`)
  }
  await page.reload({ waitUntil: 'domcontentloaded' })
  await initializeShell()
  await waitForSafeChecks()
}

await page.route('**/api/health', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, status: 'ready', model: 'Wrong Model', classes: ['Low', 'Moderate', 'Severe'] }) }))
await page.locator('[data-health-refresh]').click(); await waitForSafeChecks()
const mismatch = await page.locator('[data-health-card="prediction"]').evaluate((node) => ({ state: node.dataset.state, text: node.textContent }))
if (mismatch.state !== 'degraded' || !mismatch.text.includes('冻结模型合同异常')) throw new Error(`Contract mismatch branch failed: ${JSON.stringify(mismatch)}`)
if (await page.locator('[data-health-card="database"]').getAttribute('data-state') !== 'ready') throw new Error('One service failure affected database result')
await page.unroute('**/api/health')

await page.route('**/api/health', (route) => route.abort())
await page.locator('[data-health-refresh]').click(); await waitForSafeChecks()
if (await page.locator('[data-health-card="prediction"]').getAttribute('data-state') !== 'unavailable') throw new Error('Network error branch failed')
await page.unroute('**/api/health')
const expectedMockConsoleErrors = consoleErrors.splice(0)
if (!expectedMockConsoleErrors.some((message) => message.includes('ERR_FAILED'))) throw new Error('Expected mocked network failure was not observed')

await page.route('**/api/ai-chat', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ answer: '测试通过', model: 'mock-health-model' }) }))
await page.locator('[data-health-ai-check]').click()
await page.waitForFunction(() => document.querySelector('[data-health-card="ai"]')?.dataset.state !== 'loading')
const aiMock = await page.locator('[data-health-card="ai"]').evaluate((node) => ({ state: node.dataset.state, text: node.textContent }))
if (aiMock.state !== 'ready' || !aiMock.text.includes('真实生成验证通过')) throw new Error(`AI manual check UI failed: ${JSON.stringify(aiMock)}`)
await page.unroute('**/api/ai-chat')

await page.reload({ waitUntil: 'domcontentloaded' })
await initializeShell()
await waitForSafeChecks()
const refreshed = await page.evaluate(() => ({ route: location.hash, database: document.querySelector('[data-health-card="database"]')?.dataset.state, prediction: document.querySelector('[data-health-card="prediction"]')?.dataset.state, ai: document.querySelector('[data-health-card="ai"]')?.dataset.state }))
if (refreshed.database !== 'ready' || refreshed.prediction !== 'ready' || refreshed.ai !== 'unchecked') throw new Error(`Refresh check failed: ${JSON.stringify(refreshed)}`)

let duplicateRequests = 0
await page.route('**/api/health', async (route) => {
  duplicateRequests += 1
  await new Promise((resolve) => setTimeout(resolve, 180))
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, status: 'ready', model: 'Random Forest T2', classes: ['Low', 'Moderate', 'Severe'] }) })
})
await page.locator('[data-health-refresh]').click()
if (await page.locator('[data-health-refresh]').isEnabled()) throw new Error('Refresh button was not locked during a check')
await page.evaluate(() => document.querySelector('[data-health-refresh]')?.click())
await waitForSafeChecks()
if (duplicateRequests !== 1) throw new Error(`Duplicate health requests detected: ${duplicateRequests}`)
await page.unroute('**/api/health')

let staleRequests = 0
await page.route('**/api/health', async (route) => {
  staleRequests += 1
  if (staleRequests === 1) {
    await new Promise((resolve) => setTimeout(resolve, 260))
    try { await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, status: 'ready', model: 'Stale Model', classes: ['Low', 'Moderate', 'Severe'] }) }) } catch {}
    return
  }
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, status: 'ready', model: 'Random Forest T2', classes: ['Low', 'Moderate', 'Severe'] }) })
})
await page.locator('[data-health-refresh]').click()
await page.evaluate(() => { location.hash = '#/admin/dashboard' })
await page.waitForSelector('.admin-module-grid')
await page.evaluate(() => { location.hash = '#/admin/system' })
await page.waitForSelector('.admin-system-status')
await waitForSafeChecks()
await page.waitForTimeout(320)
const staleCycle = await page.locator('[data-health-card="prediction"]').evaluate((node) => ({ state: node.dataset.state, text: node.textContent }))
if (staleCycle.state !== 'ready' || !staleCycle.text.includes('Random Forest T2') || staleCycle.text.includes('Stale Model')) throw new Error(`Stale cycle overwrote current state: ${JSON.stringify(staleCycle)}`)
await page.unroute('**/api/health')

const viewports = []
for (const viewport of [{ width: 1920, height: 1080 }, { width: 1280, height: 720 }, { width: 960, height: 600 }, { width: 390, height: 844 }]) {
  await page.setViewportSize(viewport)
  await page.waitForTimeout(100)
  viewports.push({ ...viewport, horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth) })
}
if (viewports.some((item) => item.horizontalOverflow)) throw new Error(`Responsive overflow: ${JSON.stringify(viewports)}`)

const adminRoutes = []
for (const route of ['admin/dashboard', 'admin/disasters', 'admin/users', 'admin/models']) {
  await boot(route)
  const current = await page.evaluate(() => ({ route: location.hash, mascotCount: document.querySelectorAll('#ai-face').length }))
  if (current.route !== `#/${route}` || current.mascotCount !== 1) throw new Error(`Admin route regression: ${JSON.stringify({ route, current })}`)
  adminRoutes.push(current)
}

const source = readFileSync('src/pages/admin/systemMonitor.js', 'utf8')
if (!source.includes('cycleId') || !source.includes('cycleController?.abort()') || !source.includes('if (aiChecking) return')) throw new Error('Concurrency/lifecycle guards are missing')
if (/Math\.random|setInterval/.test(source)) throw new Error('Random or polling status detected')
if (consoleErrors.length || pageErrors.length) throw new Error(`Browser errors: ${JSON.stringify({ consoleErrors, pageErrors })}`)

await browser.close()
console.log(JSON.stringify({ real, realAi, mismatch, aiMock, refreshed, duplicateRequests, staleRequests, staleCycle, viewports, adminRoutes, aiRequests, expectedMockConsoleErrors, consoleErrors, pageErrors }, null, 2))
