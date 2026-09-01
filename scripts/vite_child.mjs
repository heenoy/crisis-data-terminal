import { spawn, spawnSync } from 'node:child_process'

const previewMode = process.argv.includes('--preview')
const host = process.env.LOCAL_WEB_HOST || '127.0.0.1'
const port = Number(process.env.LOCAL_WEB_PORT || (previewMode ? 4173 : 5173))
const redirectEnabled = process.env.ENABLE_LOCALHOST_IPV6_BRIDGE === '1'
let vite = null
let redirect = null
let closing = false

function killProcessTree(child) {
  if (!child || child.exitCode !== null || child.killed) return
  if (process.platform === 'win32' && child.pid) {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', shell: false })
  } else {
    child.kill('SIGTERM')
  }
}

function close(code = 0) {
  if (closing) return
  closing = true
  killProcessTree(redirect)
  killProcessTree(vite)
  process.exit(code)
}

const args = [
  'node_modules/vite/bin/vite.js',
  ...(previewMode ? ['preview'] : []),
  '--host', host,
  '--port', String(port),
  '--strictPort',
]
vite = spawn(process.execPath, args, { cwd: process.cwd(), stdio: 'inherit', env: process.env, shell: false })
vite.on('exit', (code) => { if (!closing) close(code || 1) })

if (redirectEnabled) {
  redirect = spawn(process.execPath, ['scripts/localhost_ipv6_proxy.mjs'], {
    cwd: process.cwd(),
    stdio: ['ignore', 'inherit', 'inherit'],
    env: { ...process.env, LOCAL_WEB_PORT: String(port) },
    shell: false,
  })
  redirect.on('exit', (code) => { if (!closing) close(code || 1) })
  console.log(`  ➜  Local alias: http://localhost:${port}/ → http://127.0.0.1:${port}/`)
}

process.on('message', (message) => { if (message === 'shutdown') close(0) })
process.on('disconnect', () => close(0))
process.on('SIGINT', () => close(0))
process.on('SIGTERM', () => close(0))
