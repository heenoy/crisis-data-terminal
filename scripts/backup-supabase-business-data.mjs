import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createClient } from '@supabase/supabase-js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputDir = process.argv[2]

if (!outputDir) {
  throw new Error('Usage: node scripts/backup-supabase-business-data.mjs <output-directory>')
}

const envText = await readFile(path.join(root, '.env'), 'utf8')
const env = Object.fromEntries(
  envText
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith('#') && line.includes('='))
    .map((line) => {
      const separator = line.indexOf('=')
      return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()]
    }),
)

const url = env.VITE_SUPABASE_URL
const anonKey = env.VITE_SUPABASE_ANON_KEY
if (!url || !anonKey) throw new Error('Missing Supabase URL or anon key in .env')

const supabase = createClient(url, anonKey, {
  auth: { persistSession: false, autoRefreshToken: false },
})

const tables = ['disaster_events', 'tags', 'event_tags', 'operation_logs']
const pageSize = 1000
const output = {
  captured_at: new Date().toISOString(),
  source_project_ref: new URL(url).hostname.split('.')[0],
  tables: {},
}

for (const table of tables) {
  const rows = []
  let expectedCount = null

  for (let from = 0; ; from += pageSize) {
    const request = supabase
      .from(table)
      .select('*', from === 0 ? { count: 'exact' } : undefined)
      .range(from, from + pageSize - 1)

    const { data, error, count } = await request
    if (error) throw new Error(`Backup read failed for ${table}: ${error.code ?? 'unknown'}`)
    if (from === 0) expectedCount = count
    rows.push(...data)
    if (data.length < pageSize) break
  }

  if (expectedCount !== rows.length) {
    throw new Error(`Row-count mismatch for ${table}: expected ${expectedCount}, read ${rows.length}`)
  }
  output.tables[table] = { row_count: rows.length, rows }
}

const json = `${JSON.stringify(output, null, 2)}\n`
const destination = path.resolve(root, outputDir, 'business-data.json')
await mkdir(path.dirname(destination), { recursive: true })
await writeFile(destination, json, { encoding: 'utf8', flag: 'wx' })

const sha256 = createHash('sha256').update(json).digest('hex')
console.log(JSON.stringify({
  destination,
  sha256,
  counts: Object.fromEntries(tables.map((table) => [table, output.tables[table].row_count])),
}))
