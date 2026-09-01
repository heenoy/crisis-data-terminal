import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backupDir = path.join(root, 'backups', 'private', '2026-08-26-checkpoint-1')
const migrations = [
  'supabase/migrations/20260826055135_add_auth_audit_fields.sql',
  'supabase/migrations/20260826055138_harden_data_api_access.sql',
]
const backupFiles = [
  'backups/private/2026-08-26-checkpoint-1/business-data.json',
  'backups/private/2026-08-26-checkpoint-1/catalog-snapshot.md',
  'backups/private/2026-08-26-checkpoint-1/rollback.sql',
]

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

const envText = await readFile(path.join(root, '.env'), 'utf8')
const secretValues = envText
  .split(/\r?\n/)
  .filter((line) => line && !line.startsWith('#') && line.includes('='))
  .map((line) => line.slice(line.indexOf('=') + 1).trim())
  .filter(Boolean)

const businessText = await readFile(path.join(backupDir, 'business-data.json'), 'utf8')
const business = JSON.parse(businessText)
assert.equal(business.source_project_ref, 'ifltlztsdvnxlellotja')
assert.deepEqual(
  Object.fromEntries(Object.entries(business.tables).map(([name, value]) => [name, value.row_count])),
  { disaster_events: 16856, tags: 8, event_tags: 0, operation_logs: 0 },
)
for (const [name, table] of Object.entries(business.tables)) {
  assert.equal(table.rows.length, table.row_count, `${name} backup count mismatch`)
}

const allBackupText = (await Promise.all(
  backupFiles.map((file) => readFile(path.join(root, file), 'utf8')),
)).join('\n')
for (const secret of secretValues) {
  assert.equal(allBackupText.includes(secret), false, 'A configured secret leaked into a backup file')
}
assert.equal(/"password"\s*:/i.test(businessText), false, 'Password fields must not be backed up')

const migrationReview = []
for (const file of migrations) {
  const sql = await readFile(path.join(root, file), 'utf8')
  const destructiveDataPatterns = {
    drop_table: /\bdrop\s+table\b/i,
    drop_column: /\bdrop\s+column\b/i,
    truncate: /\btruncate\b/i,
    delete_rows: /\bdelete\s+from\b/i,
    update_rows: /\bupdate\s+[\w".]+\s+set\b/i,
  }
  const findings = Object.fromEntries(
    Object.entries(destructiveDataPatterns).map(([name, pattern]) => [name, pattern.test(sql)]),
  )
  assert.equal(Object.values(findings).some(Boolean), false, `${file} contains a destructive data operation`)
  migrationReview.push({
    file,
    sha256: sha256(sql),
    destructive_data_operations: findings,
    drops_policies: (sql.match(/\bdrop\s+policy\b/gi) || []).length,
    revokes_privileges: (sql.match(/\brevoke\b/gi) || []).length,
  })
}

const rollback = await readFile(path.join(backupDir, 'rollback.sql'), 'utf8')
assert.doesNotMatch(rollback, /grant\s+all[\s\S]*\bto\s+anon\b/i)
assert.doesNotMatch(rollback, /create\s+policy[^;]+\bto\s+anon\b/i)

const files = {}
for (const file of [...migrations, ...backupFiles]) {
  const value = await readFile(path.join(root, file))
  files[file] = { sha256: sha256(value), bytes: value.length }
}

const manifest = {
  verified_at: new Date().toISOString(),
  project: { name: 'crisis-data-terminal', ref: 'ifltlztsdvnxlellotja' },
  expected_counts: { disaster_events: 16856, tags: 8, event_tags: 0, operation_logs: 0 },
  excludes: ['auth.users rows', 'app_users rows', 'passwords', 'API keys', 'tokens'],
  migration_review: migrationReview,
  files,
}
await writeFile(path.join(backupDir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, {
  encoding: 'utf8',
  flag: 'w',
})

console.log(JSON.stringify({
  project: manifest.project,
  counts: manifest.expected_counts,
  migration_review: migrationReview,
  backup_files_verified: backupFiles.length,
  secrets_found: 0,
}))
