import http from 'node:http'

const port = Number(process.env.LOCAL_WEB_PORT)
const server = http.createServer((request, response) => {
  const location = `http://127.0.0.1:${port}${request.url || '/'}`
  response.writeHead(307, {
    Location: location,
    'Cache-Control': 'no-store',
    'Content-Type': 'text/plain; charset=utf-8',
  })
  response.end('Redirecting to the local development server')
})

server.listen({ host: '::1', port, ipv6Only: true })
process.on('SIGINT', () => server.close(() => process.exit(0)))
process.on('SIGTERM', () => server.close(() => process.exit(0)))
