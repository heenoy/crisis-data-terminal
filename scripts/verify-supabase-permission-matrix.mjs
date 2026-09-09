import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createClient } from '@supabase/supabase-js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const projectRef = 'ifltlztsdvnxlellotja'
const adminUserId = '241663c4-6b4f-487e-bff1-7de850695152'
const demoUserId = '17cdbe10-bf86-4d09-b554-efb94c95aeac'

async function readEnvFile(filename) {
  try {
    const text = await readFile(path.join(root, filename), 'utf8')
    return Object.fromEntries(
      text
        .split(/\r?\n/)
        .filter((line) => line && !line.startsWith('#') && line.includes('='))
        .map((line) => {
          const separator = line.indexOf('=')
          return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()]
        }),
    )
  } catch (error) {
    if (error.code === 'ENOENT') return {}
    throw error
  }
}

const fileEnv = { ...(await readEnvFile('.env')), ...(await readEnvFile('.env.local')) }
const supabaseUrl = process.env.SUPABASE_URL || fileEnv.SUPABASE_URL || fileEnv.VITE_SUPABASE_URL
const publishableKey =
  process.env.SUPABASE_PUBLISHABLE_KEY || fileEnv.SUPABASE_PUBLISHABLE_KEY || fileEnv.VITE_SUPABASE_ANON_KEY
const adminKey =
  process.env.SUPABASE_SECRET_KEY ||
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  fileEnv.SUPABASE_SECRET_KEY ||
  fileEnv.SUPABASE_SERVICE_ROLE_KEY

if (!supabaseUrl || !publishableKey || !adminKey) throw new Error('Missing Supabase server test configuration')
assert.equal(new URL(supabaseUrl).hostname.split('.')[0], projectRef, 'Supabase project ref mismatch')

const clientOptions = {
  auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
}
const service = createClient(supabaseUrl, adminKey, clientOptions)
const anon = createClient(supabaseUrl, publishableKey, clientOptions)

function safeResult(error, data) {
  return {
    request_succeeded: !error,
    error_code: error?.code ?? null,
    returned_rows: Array.isArray(data) ? data.length : null,
  }
}

async function createUserSession(userId) {
  const { data: userData, error: userError } = await service.auth.admin.getUserById(userId)
  if (userError || !userData?.user?.email) throw new Error(`Admin read failed for ${userId}`)

  const { data: linkData, error: linkError } = await service.auth.admin.generateLink({
    type: 'magiclink',
    email: userData.user.email,
  })
  const tokenHash = linkData?.properties?.hashed_token
  if (linkError || !tokenHash) throw new Error(`Magic-link generation failed for ${userId}`)

  const client = createClient(supabaseUrl, publishableKey, clientOptions)
  const { data, error } = await client.auth.verifyOtp({ token_hash: tokenHash, type: 'magiclink' })
  if (error || !data?.session || data.user?.id !== userId) throw new Error(`Session creation failed for ${userId}`)
  return { client, user: data.user }
}

const runId = randomUUID()
const testPrefix = `[4.2 SECURITY TEST ${runId}]`
const createdIds = new Set()
const failures = []
const results = {}
let demoSession
let adminSession

function expect(name, condition) {
  if (!condition) failures.push(name)
}

async function cleanup() {
  if (createdIds.size) {
    await service.from('disaster_events').delete().in('id', [...createdIds])
  }
  if (demoSession) await demoSession.client.auth.signOut({ scope: 'global' })
  if (adminSession) await adminSession.client.auth.signOut({ scope: 'global' })
}

try {
  demoSession = await createUserSession(demoUserId)
  adminSession = await createUserSession(adminUserId)
  assert.notEqual(demoSession.user.app_metadata?.role, 'admin')
  assert.equal(adminSession.user.app_metadata?.role, 'admin')

  const anonRead = await anon.from('disaster_events').select('id').limit(1)
  results.anon_select = safeResult(anonRead.error, anonRead.data)
  expect('anon SELECT must be denied', Boolean(anonRead.error))

  const demoRead = await demoSession.client.from('disaster_events').select('id').limit(1)
  results.user_select = safeResult(demoRead.error, demoRead.data)
  expect('ordinary user SELECT must succeed', !demoRead.error && demoRead.data?.length === 1)

  const adminRead = await adminSession.client.from('disaster_events').select('id').limit(1)
  results.admin_select = safeResult(adminRead.error, adminRead.data)
  expect('admin SELECT must succeed', !adminRead.error && adminRead.data?.length === 1)

  const unauthorizedPayload = {
    title: `${testPrefix} unauthorized insert`,
    disaster_type: 'Other',
    country: 'TEST',
    event_date: '2026-08-26',
    severity: 'low',
    status: 'archived',
    created_by_auth: demoUserId,
  }
  const anonInsert = await anon.from('disaster_events').insert(unauthorizedPayload).select('id')
  for (const row of anonInsert.data ?? []) createdIds.add(row.id)
  results.anon_insert = safeResult(anonInsert.error, anonInsert.data)
  expect('anon INSERT must be denied', Boolean(anonInsert.error))

  const demoInsert = await demoSession.client.from('disaster_events').insert(unauthorizedPayload).select('id')
  for (const row of demoInsert.data ?? []) createdIds.add(row.id)
  results.user_insert = safeResult(demoInsert.error, demoInsert.data)
  expect('ordinary user INSERT must be denied', Boolean(demoInsert.error))

  const testPayload = {
    title: `${testPrefix} admin CRUD`,
    disaster_type: 'Other',
    country: 'TEST',
    event_date: '2026-08-26',
    severity: 'low',
    status: 'archived',
    description: 'Dedicated temporary permission-matrix record',
    source_name: 'Fourth Stage 4.2 permission matrix',
    created_by_auth: adminUserId,
  }
  const adminInsert = await adminSession.client.from('disaster_events').insert(testPayload).select('id,created_by_auth').single()
  results.admin_insert = safeResult(adminInsert.error, adminInsert.data ? [adminInsert.data] : null)
  expect('admin INSERT must succeed', !adminInsert.error && adminInsert.data?.created_by_auth === adminUserId)
  if (!adminInsert.data?.id) throw new Error('Cannot continue matrix without the dedicated test record')
  const testId = adminInsert.data.id
  createdIds.add(testId)

  const anonUpdate = await anon.from('disaster_events').update({ description: 'anon must not update' }).eq('id', testId).select('id')
  results.anon_update = safeResult(anonUpdate.error, anonUpdate.data)
  expect('anon UPDATE must be denied', Boolean(anonUpdate.error) || anonUpdate.data?.length === 0)

  const demoUpdate = await demoSession.client.from('disaster_events').update({ description: 'user must not update' }).eq('id', testId).select('id')
  results.user_update = safeResult(demoUpdate.error, demoUpdate.data)
  expect('ordinary user UPDATE must be denied', Boolean(demoUpdate.error) || demoUpdate.data?.length === 0)

  const anonDelete = await anon.from('disaster_events').delete().eq('id', testId).select('id')
  results.anon_delete = safeResult(anonDelete.error, anonDelete.data)
  expect('anon DELETE must be denied', Boolean(anonDelete.error) || anonDelete.data?.length === 0)

  const demoDelete = await demoSession.client.from('disaster_events').delete().eq('id', testId).select('id')
  results.user_delete = safeResult(demoDelete.error, demoDelete.data)
  expect('ordinary user DELETE must be denied', Boolean(demoDelete.error) || demoDelete.data?.length === 0)

  const unauthorizedMutationCheck = await service
    .from('disaster_events')
    .select('id,description')
    .eq('id', testId)
    .single()
  results.unauthorized_mutation_blocked =
    !unauthorizedMutationCheck.error &&
    unauthorizedMutationCheck.data?.description === 'Dedicated temporary permission-matrix record'
  expect('unauthorized UPDATE/DELETE must leave the test record unchanged', results.unauthorized_mutation_blocked)

  const adminUpdate = await adminSession.client
    .from('disaster_events')
    .update({ description: 'Admin update verified' })
    .eq('id', testId)
    .select('id,description,created_by_auth')
    .single()
  results.admin_update = safeResult(adminUpdate.error, adminUpdate.data ? [adminUpdate.data] : null)
  expect(
    'admin UPDATE must succeed',
    !adminUpdate.error &&
      adminUpdate.data?.description === 'Admin update verified' &&
      adminUpdate.data?.created_by_auth === adminUserId,
  )

  const adminDelete = await adminSession.client.from('disaster_events').delete().eq('id', testId).select('id').single()
  results.admin_delete = safeResult(adminDelete.error, adminDelete.data ? [adminDelete.data] : null)
  expect('admin DELETE must succeed', !adminDelete.error && adminDelete.data?.id === testId)
  if (!adminDelete.error) createdIds.delete(testId)

  const deletedCheck = await service.from('disaster_events').select('id').eq('id', testId)
  results.test_record_removed = !deletedCheck.error && deletedCheck.data?.length === 0
  expect('dedicated test record must be removed', results.test_record_removed)

  const anonView = await anon.from('dashboard_stats').select('*').limit(1)
  results.anon_stats_view = safeResult(anonView.error, anonView.data)
  expect('anon statistics view must be denied', Boolean(anonView.error))

  const userView = await demoSession.client.from('dashboard_stats').select('*').limit(1)
  results.user_stats_view = safeResult(userView.error, userView.data)
  expect('ordinary user statistics view must succeed', !userView.error)

  const adminView = await adminSession.client.from('dashboard_stats').select('*').limit(1)
  results.admin_stats_view = safeResult(adminView.error, adminView.data)
  expect('admin statistics view must succeed', !adminView.error)

  const finalCount = await service.from('disaster_events').select('id', { count: 'exact', head: true })
  results.final_disaster_count = finalCount.count
  expect('final disaster count must remain 16856', !finalCount.error && finalCount.count === 16856)
} finally {
  await cleanup()
}

if (failures.length) throw new Error(`Permission matrix failed: ${failures.join('; ')}`)

console.log(JSON.stringify({
  project_ref: projectRef,
  auth_method: 'admin_generated_magic_link_no_password',
  results,
  failures: 0,
  cleanup_complete: createdIds.size === 0,
  passwords_touched: false,
}))
