import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createClient } from '@supabase/supabase-js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const projectRef = 'ifltlztsdvnxlellotja'
const adminUserId = '241663c4-6b4f-487e-bff1-7de850695152'
const demoUserId = '17cdbe10-bf86-4d09-b554-efb94c95aeac'
const verifyOnly = process.argv.includes('--verify-only')

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

const fileEnv = {
  ...(await readEnvFile('.env')),
  ...(await readEnvFile('.env.local')),
}
const supabaseUrl = process.env.SUPABASE_URL || fileEnv.SUPABASE_URL || fileEnv.VITE_SUPABASE_URL
const adminKey =
  process.env.SUPABASE_SECRET_KEY ||
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  fileEnv.SUPABASE_SECRET_KEY ||
  fileEnv.SUPABASE_SERVICE_ROLE_KEY

if (!supabaseUrl || !adminKey) {
  throw new Error(
    'Missing server-only Supabase credential. Set SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY locally.',
  )
}
assert.equal(new URL(supabaseUrl).hostname.split('.')[0], projectRef, 'Supabase project ref mismatch')

const supabase = createClient(supabaseUrl, adminKey, {
  auth: { persistSession: false, autoRefreshToken: false },
})

async function getUser(userId) {
  const { data, error } = await supabase.auth.admin.getUserById(userId)
  if (error || !data?.user) {
    throw new Error(`Auth Admin read failed for ${userId}: status ${error?.status ?? 'unknown'}`)
  }
  return data.user
}

async function updateUser(userId, attributes) {
  const { error } = await supabase.auth.admin.updateUserById(userId, attributes)
  if (error) {
    throw new Error(`Auth Admin update failed for ${userId}: status ${error.status ?? 'unknown'}`)
  }
}

const adminBefore = await getUser(adminUserId)
const demoBefore = await getUser(demoUserId)
const adminProviderBefore = adminBefore.app_metadata?.provider
const adminProvidersBefore = structuredClone(adminBefore.app_metadata?.providers ?? [])
const demoAppMetadataBefore = structuredClone(demoBefore.app_metadata ?? {})

if (!verifyOnly) {
  await updateUser(adminUserId, {
    app_metadata: { ...(adminBefore.app_metadata ?? {}), role: 'admin' },
    user_metadata: {
      ...(adminBefore.user_metadata ?? {}),
      username: 'admin',
      display_name: 'Administrator',
    },
  })

  await updateUser(demoUserId, {
    user_metadata: {
      ...(demoBefore.user_metadata ?? {}),
      username: 'demo_user',
      display_name: 'Demo User',
    },
  })
}

const adminAfter = await getUser(adminUserId)
const demoAfter = await getUser(demoUserId)

assert.equal(adminAfter.app_metadata?.role, 'admin')
assert.equal(adminAfter.user_metadata?.username, 'admin')
assert.equal(adminAfter.user_metadata?.display_name, 'Administrator')
assert.equal(adminAfter.app_metadata?.provider, adminProviderBefore)
assert.deepEqual(adminAfter.app_metadata?.providers ?? [], adminProvidersBefore)
assert.equal(demoAfter.user_metadata?.username, 'demo_user')
assert.equal(demoAfter.user_metadata?.display_name, 'Demo User')
assert.notEqual(demoAfter.app_metadata?.role, 'admin')
assert.deepEqual(demoAfter.app_metadata ?? {}, demoAppMetadataBefore)

console.log(
  JSON.stringify({
    project_ref: projectRef,
    mode: verifyOnly ? 'read_only_verification' : 'update_and_verify',
    admin: {
      id: adminUserId,
      role: adminAfter.app_metadata.role,
      username: adminAfter.user_metadata.username,
      display_name: adminAfter.user_metadata.display_name,
      provider_preserved: adminAfter.app_metadata?.provider === adminProviderBefore,
      providers_preserved:
        JSON.stringify(adminAfter.app_metadata?.providers ?? []) === JSON.stringify(adminProvidersBefore),
    },
    demo_user: {
      id: demoUserId,
      username: demoAfter.user_metadata.username,
      display_name: demoAfter.user_metadata.display_name,
      admin_role_absent: demoAfter.app_metadata?.role !== 'admin',
      app_metadata_unchanged:
        JSON.stringify(demoAfter.app_metadata ?? {}) === JSON.stringify(demoAppMetadataBefore),
    },
    password_touched: false,
  }),
)
