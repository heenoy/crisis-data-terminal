import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const { createClient } = require('@supabase/supabase-js')
for (const name of ['.env', '.env.local']) {
  try { for (const line of readFileSync(name, 'utf8').split(/\r?\n/)) { const m = line.match(/^([^#=]+)=(.*)$/); if (m && process.env[m[1].trim()] === undefined) process.env[m[1].trim()] = m[2].trim().replace(/^['"]|['"]$/g, '') } } catch {}
}
const baseUrl = process.env.MODEL_PAGE_VERIFY_URL || 'http://127.0.0.1:5173'
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
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('pageerror', (error) => pageErrors.push(error.message))
async function install(session) { await page.goto(baseUrl); await page.evaluate(({ key, session }) => localStorage.setItem(key, JSON.stringify(session)), { key: storageKey, session }) }
async function boot(route) {
  await page.goto(`${baseUrl}/#/${route}`, { waitUntil: 'domcontentloaded' })
  const launch = page.locator('#launch-overlay')
  if (await launch.isVisible()) await launch.click({ position: { x: 20, y: 20 } })
  const wake = page.locator('#wake-init-btn')
  if (!await page.locator('#app .vault-console, #app .survivor-auth-shell').count()) {
    await wake.waitFor({ state: 'visible' })
    await wake.click()
  }
  await page.waitForSelector('#app .vault-console, #app .survivor-auth-shell')
}

await boot('admin/models')
if (await page.evaluate(() => location.hash) !== '#/auth') throw new Error('Unauthenticated route guard failed')
await install(await sessionFor(USER_ID)); await boot('admin/models')
if (await page.evaluate(() => location.hash) !== '#/user/overview') throw new Error('User route guard failed')
await install(await sessionFor(ADMIN_ID)); await boot('admin/models')
await page.waitForSelector('.admin-models .model-chart canvas')
const desktop = await page.evaluate(() => {
  const weights = document.querySelector('[data-chart="weights"]')
  return { route: location.hash, productionCards: document.querySelectorAll('[data-status="Production"]').length, modelCards: document.querySelectorAll('.model-archive-card').length, charts: [...document.querySelectorAll('.model-chart')].filter((node) => node.querySelector('canvas')).length, buttons: document.querySelectorAll('[data-model-detail]').length, weightSeries: Number(weights?.dataset.seriesCount), weightPoints: Number(weights?.dataset.pointCount), removedProductionCopy: !document.querySelector('.model-production')?.textContent.includes('不是灾害发生预测或实时预警'), removedStatusExplanation: !document.querySelector('.model-evidence-grid')?.textContent.includes('Candidate不代表可一键部署'), horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth }
})
if (desktop.route !== '#/admin/models' || desktop.productionCards !== 1 || desktop.modelCards !== 6 || desktop.charts !== 5 || desktop.buttons !== 6 || desktop.weightSeries !== 3 || desktop.weightPoints !== 15 || !desktop.removedProductionCopy || !desktop.removedStatusExplanation || desktop.horizontalOverflow) throw new Error(`Desktop model page failed: ${JSON.stringify(desktop)}`)
await boot('admin/models')
await page.waitForSelector('[data-chart="weights"] canvas')
const refreshedWeightChart = await page.locator('[data-chart="weights"]').evaluate((node) => ({ series: Number(node.dataset.seriesCount), points: Number(node.dataset.pointCount) }))
if (refreshedWeightChart.series !== 3 || refreshedWeightChart.points !== 15) throw new Error(`Weight chart did not survive refresh: ${JSON.stringify(refreshedWeightChart)}`)
await page.locator('[data-model-detail="rf-t2-final"]').click(); await page.waitForSelector('.model-detail-dialog[open]'); await page.locator('[data-model-detail-close]').click()
const viewports = []
for (const viewport of [{ width: 1280, height: 720 }, { width: 960, height: 600 }, { width: 390, height: 844 }]) {
  await page.setViewportSize(viewport); await page.waitForTimeout(100)
  viewports.push({ ...viewport, horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth) })
}
if (viewports.some((v) => v.horizontalOverflow)) throw new Error('Responsive horizontal overflow detected')
await browser.close()
console.log(JSON.stringify({ desktop, refreshedWeightChart, viewports, consoleErrors, pageErrors }, null, 2))
