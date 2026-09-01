import { defineConfig, loadEnv } from 'vite'
import aiChatHandler from './api/ai-chat.js'

const SERVER_ENV_KEYS = [
  'DEEPSEEK_API_KEY',
  'DEEPSEEK_BASE_URL',
  'DEEPSEEK_MODEL',
  'SUPABASE_URL',
  'SUPABASE_SERVICE_ROLE_KEY',
  'SUPABASE_ANON_KEY',
  'VITE_SUPABASE_URL',
  'VITE_SUPABASE_ANON_KEY',
]

function loadServerEnv(mode) {
  const env = loadEnv(mode, process.cwd(), '')
  SERVER_ENV_KEYS.forEach((key) => {
    if (process.env[key] === undefined && env[key] !== undefined) process.env[key] = env[key]
  })
}

async function readJsonBody(req) {
  let raw = ''
  for await (const chunk of req) {
    raw += chunk
    if (Buffer.byteLength(raw) > 64 * 1024) throw new Error('Request body is too large')
  }
  return raw ? JSON.parse(raw) : {}
}

function attachLocalAiChat(middlewares) {
  middlewares.use(async (req, res, next) => {
    if (new URL(req.url, 'http://localhost').pathname !== '/api/ai-chat') return next()

    try {
      req.body = req.method === 'POST' ? await readJsonBody(req) : {}
      res.status = (status) => {
        res.statusCode = status
        return res
      }
      res.json = (body) => {
        res.setHeader('Content-Type', 'application/json; charset=utf-8')
        res.setHeader('Cache-Control', 'no-store')
        res.end(JSON.stringify(body))
        return res
      }
      await aiChatHandler(req, res)
    } catch (error) {
      console.error('[local-ai-chat] request failed:', error)
      if (!res.writableEnded) {
        res.statusCode = error instanceof SyntaxError ? 400 : 500
        res.setHeader('Content-Type', 'application/json; charset=utf-8')
        res.end(JSON.stringify({ error: error instanceof SyntaxError ? 'Invalid JSON body' : 'AI service is temporarily unavailable' }))
      }
    }
  })
}

function localAiChat() {
  return {
    name: 'local-ai-chat',
    configureServer: ({ middlewares }) => attachLocalAiChat(middlewares),
    configurePreviewServer: ({ middlewares }) => attachLocalAiChat(middlewares),
  }
}

export default defineConfig(({ mode }) => {
  loadServerEnv(mode)
  const inferenceProxy = {
    '^/api/(health|impact-options|predict-impact)(?:\\?.*)?$': {
      target: process.env.VITE_LOCAL_API_ORIGIN || 'http://127.0.0.1:8000',
      changeOrigin: false,
    },
  }

  return {
    plugins: [localAiChat()],
    server: { proxy: inferenceProxy },
    preview: { proxy: inferenceProxy },
  }
})
