import { spawn, spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'

const root = process.cwd()
const previewMode = process.argv.includes('--preview')
const apiHost = process.env.LOCAL_API_HOST || '127.0.0.1'
const apiPort = Number(process.env.LOCAL_API_PORT || 8000)
const webHost = process.env.LOCAL_WEB_HOST || '127.0.0.1'
const webPort = Number(process.env.LOCAL_WEB_PORT || (previewMode ? 4173 : 5173))
if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535 || !Number.isInteger(webPort) || webPort < 1 || webPort > 65535) {
  console.error('[dev] LOCAL_API_PORT 和 LOCAL_WEB_PORT 必须是 1 至 65535 的整数。')
  process.exit(1)
}
const apiOrigin = `http://${apiHost}:${apiPort}`
const dependencyProbe = 'import joblib,numpy,pandas,sklearn,scipy; from ml_inference.service import health_response; assert health_response()["success"]'

const explicitPython = process.env.PYTHON_EXECUTABLE
const candidates = [
  explicitPython && { command: explicitPython, prefix: [] },
  { command: process.platform === 'win32' ? path.join(root, '.venv', 'Scripts', 'python.exe') : path.join(root, '.venv', 'bin', 'python'), prefix: [] },
  process.platform === 'win32' && { command: 'py', prefix: ['-3.12'] },
  { command: process.platform === 'win32' ? 'python' : 'python3', prefix: [] },
].filter(Boolean)

function canRun(candidate) {
  if (candidate.command.includes(path.sep) && !existsSync(candidate.command)) return false
  const result = spawnSync(candidate.command, [...candidate.prefix, '-c', dependencyProbe], {
    cwd: root,
    stdio: 'ignore',
    shell: false,
  })
  return result.status === 0
}

const python = candidates.find(canRun)
if (!python) {
  console.error('[dev] 没有找到具备冻结模型推理依赖的 Python 环境。')
  console.error('[dev] 请先创建项目 .venv 并执行：.venv\\Scripts\\python -m pip install -r requirements.txt')
  process.exit(1)
}

let stopping = false
let api = null
let web = null

function killChild(child) {
  if (!child || child.exitCode !== null || child.killed) return
  if (process.platform === 'win32' && child.pid) {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', shell: false })
    return
  }
  child.kill('SIGTERM')
}

function stop(code = 0) {
  if (stopping) return
  stopping = true
  killChild(web)
  killChild(api)
  process.exit(code)
}

async function waitForApiReady(timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (api.exitCode !== null) throw new Error(`Python API 已退出，code=${api.exitCode}`)
    try {
      const response = await fetch(`${apiOrigin}/api/health`, { headers: { Accept: 'application/json' } })
      const contentType = response.headers.get('content-type') || ''
      const body = contentType.includes('application/json') ? await response.json() : null
      if (response.ok && body?.success === true && body?.status === 'ready') return
    } catch {
      // The API imports the frozen model before listening; retry until ready or timeout.
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error(`Python API 未能在 ${timeoutMs / 1000} 秒内就绪`)
}

async function main() {
  const pythonArgs = [...python.prefix, 'scripts/run_inference_api.py']
  console.log(`[dev] 启动冻结模型 API：${apiOrigin}`)
  api = spawn(python.command, pythonArgs, {
    cwd: root,
    stdio: ['pipe', 'inherit', 'inherit'],
    env: { ...process.env, LOCAL_API_HOST: apiHost, LOCAL_API_PORT: String(apiPort) },
    shell: false,
  })
  api.on('exit', (code) => {
    if (!stopping) {
      console.error(`[dev] Python API 意外退出，code=${code ?? 'unknown'}`)
      stop(code || 1)
    }
  })

  await waitForApiReady()
  console.log('[dev] Python API 健康检查通过；现在启动前端。')

  const viteArgs = ['scripts/vite_child.mjs', ...(previewMode ? ['--preview'] : [])]
  web = spawn(process.execPath, viteArgs, {
    cwd: root,
    stdio: ['ignore', 'inherit', 'inherit', 'ipc'],
    env: {
      ...process.env,
      VITE_LOCAL_API_ORIGIN: apiOrigin,
      LOCAL_WEB_HOST: webHost,
      LOCAL_WEB_PORT: String(webPort),
      ENABLE_LOCALHOST_IPV6_BRIDGE: process.env.ENABLE_LOCALHOST_IPV6_BRIDGE || (webHost === '127.0.0.1' ? '1' : '0'),
    },
    shell: false,
  })
  web.on('exit', (code) => {
    if (!stopping) stop(code || 0)
  })
}

process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))
process.on('SIGBREAK', () => stop(0))
if (process.stdin.isTTY && typeof process.stdin.setRawMode === 'function') {
  readline.emitKeypressEvents(process.stdin)
  process.stdin.setRawMode(true)
  process.stdin.resume()
  process.stdin.on('keypress', (_text, key) => {
    if (key?.ctrl && key?.name === 'c') stop(0)
  })
}
process.on('exit', () => {
  killChild(web)
  killChild(api)
})

main().catch((error) => {
  console.error(`[dev] 完整开发环境启动失败：${error.message}`)
  stop(1)
})
