import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import {
  normalizeUsername,
  roleFromAppMetadata,
  usernameToInternalEmail,
} from '../src/authIdentity.js'
import { authorizeRoute, ROUTES } from '../src/router/routes.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => readFile(path.join(root, relativePath), 'utf8')

assert.equal(normalizeUsername('  Vault_User  '), 'vault_user')
assert.equal(usernameToInternalEmail('Vault_User'), 'vault_user@users.cytuna.cn')
assert.equal(usernameToInternalEmail('vault_user'), usernameToInternalEmail(' VAULT_USER '))
assert.throws(() => normalizeUsername('ab'), /3–24/)
assert.throws(() => normalizeUsername('中文用户'), /英文字母/)
assert.throws(() => normalizeUsername('vault-user'), /英文字母/)

assert.equal(roleFromAppMetadata({ role: 'admin' }), 'admin')
assert.equal(roleFromAppMetadata({ role: 'user' }), 'user')
assert.equal(roleFromAppMetadata(undefined), 'user')
assert.equal(roleFromAppMetadata({}), 'user')

const normalUser = { id: 'auth-user', role: 'user' }
const adminUser = { id: 'auth-admin', role: 'admin' }
assert.equal(authorizeRoute(ROUTES.ADMIN_DASHBOARD, null).route, ROUTES.AUTH)
assert.equal(authorizeRoute(ROUTES.ADMIN_DASHBOARD, normalUser).route, ROUTES.USER_OVERVIEW)
assert.equal(authorizeRoute(ROUTES.ADMIN_DASHBOARD, adminUser).allowed, true)

const authSource = await read('src/auth.js')
assert.match(authSource, /signInWithPassword/)
assert.match(authSource, /supabase\.auth\.signUp/)
assert.match(authSource, /onAuthStateChange/)
assert.doesNotMatch(authSource, /\.from\(['"]app_users['"]\)/)
assert.doesNotMatch(authSource, /sessionStorage\.getItem\(SESSION_KEY\)/)
assert.doesNotMatch(authSource, /user_metadata\?\.role/)

const disasterSource = await read('src/disasterEvents.js')
assert.match(disasterSource, /created_by_auth: userRef\.id/)
assert.match(disasterSource, /delete\(\).*select\(['"]id['"]\)\.maybeSingle\(\)/s)
assert.doesNotMatch(disasterSource, /\.from\(['"]app_users['"]\)/)

const migrationOne = await read('supabase/migrations/20260826055135_add_auth_audit_fields.sql')
assert.match(migrationOne, /references auth\.users \(id\)/i)
assert.match(migrationOne, /on delete set null/i)
assert.doesNotMatch(migrationOne, /update\s+public\.disaster_events/i)

const migrationTwo = await read('supabase/migrations/20260826055138_harden_data_api_access.sql')
assert.match(migrationTwo, /revoke all privileges on table public\.app_users from anon, authenticated/i)
assert.match(migrationTwo, /authenticated can read disaster events/i)
assert.match(migrationTwo, /admins can insert disaster events/i)
assert.match(migrationTwo, /created_by_auth = \(select auth\.uid\(\)\)/i)
assert.match(migrationTwo, /security_invoker = true/i)
assert.doesNotMatch(migrationTwo, /to anon\s+using \(true\)/i)

console.log('4.2-A auth and migration preparation checks passed.')
