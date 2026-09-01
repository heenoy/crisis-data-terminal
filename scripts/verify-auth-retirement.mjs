import assert from 'node:assert/strict'
import { access, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => readFile(path.join(root, relativePath), 'utf8')

const activeFiles = [
  'src/auth.js',
  'src/authIdentity.js',
  'src/authPage.js',
  'src/disasterEvents.js',
  'src/main.js',
  'src/router/routes.js',
  'src/services/adminStats.js',
]

for (const relativePath of activeFiles) {
  const source = await read(relativePath)
  assert.doesNotMatch(source, /\.from\(['"]app_users['"]\)/, `${relativePath} still queries app_users`)
  assert.doesNotMatch(source, /sessionStorage\.clear\(\)|localStorage\.clear\(\)/, `${relativePath} clears unrelated browser storage`)
}

const authSource = await read('src/auth.js')
assert.match(authSource, /sessionStorage\.removeItem\(LEGACY_SESSION_KEY\)/)
assert.match(authSource, /localStorage\.removeItem\(LEGACY_SESSION_KEY\)/)
assert.match(authSource, /signInWithPassword/)
assert.match(authSource, /app_metadata/)
assert.doesNotMatch(authSource, /password.*\.from\(|\.from\(.*password/s)

const migration = await read('supabase/migrations/20260901090000_retire_legacy_app_users.sql')
assert.match(migration, /revoke all privileges on table public\.app_users from public, anon, authenticated/i)
assert.match(migration, /DEPRECATED/i)
assert.doesNotMatch(migration, /drop\s+table|drop\s+column|truncate|delete\s+from|cascade/i)

for (const obsoletePath of [
  'scripts/disaster_events.sql',
  'scripts/migrate-operator-role-to-user.sql',
  'scripts/seed-app-users.sql',
  'scripts/verify_created_by_fkey.sql',
]) {
  await assert.rejects(access(path.join(root, obsoletePath)), `${obsoletePath} should be retired`)
}

console.log('4.2-C legacy authentication retirement checks passed.')
