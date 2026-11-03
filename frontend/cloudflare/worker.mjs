// Only this fixed backend can receive gateway requests. No URL/query/header override.
export const BACKEND = 'https://mustaaaaaard-27.onrender.com'
export const PUBLIC_ORIGIN = 'https://mustaaaaaard-27.eeyramagbetor.workers.dev'
const MAX_BODY = 51 * 1024 * 1024
function failure(status, message) {
  return Response.json({ error: { code: 'gateway_unavailable', message } }, { status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } })
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    const api = url.pathname === '/api' || url.pathname.startsWith('/api/')
    const auth = url.pathname === '/auth' || url.pathname.startsWith('/auth/')
    if (!api && !auth) return env.ASSETS.fetch(request)
    if (url.origin !== PUBLIC_ORIGIN) return failure(403, 'Production authentication is disabled on preview origins.')
    if (auth && !['/auth/google', '/auth/google/callback'].includes(url.pathname)) return failure(404, 'Not found')
    if (Number(request.headers.get('Content-Length') || 0) > MAX_BODY) return failure(413, 'Upload exceeds the 51 MiB request limit.')
    const target = new URL(BACKEND)
    target.pathname = url.pathname
    target.search = url.search
    const headers = new Headers(request.headers)
    for (const name of ['host', 'forwarded', 'x-forwarded-host', 'x-forwarded-proto', 'x-mustard-origin', 'authorization']) headers.delete(name)
    headers.set('X-Mustard-Origin', PUBLIC_ORIGIN)
    headers.set('Cache-Control', 'no-store')
    // Pass the ReadableStream directly; never consume/clone/parse multipart bodies.
    const init = { method: request.method, headers, body: request.body, redirect: 'manual', cache: 'no-store', signal: request.signal, duplex: 'half' }
    let upstream
    try { upstream = await fetch(target, init) } catch {
      if (auth) return new Response(null, { status: 303, headers: { Location: PUBLIC_ORIGIN + '/?connection_retry=1', 'Cache-Control': 'no-store' } })
      return failure(503, 'Cannot connect. Please retry when the backend is ready.')
    }
    if (!(upstream.status >= 300 && upstream.status < 400) && !upstream.headers.get('Content-Type')?.includes('application/json')) {
      await upstream.body?.cancel()
      if (auth) return new Response(null, { status: 303, headers: { Location: PUBLIC_ORIGIN + '/?connection_retry=1', 'Cache-Control': 'no-store' } })
      return failure(503, 'The backend is waking. Please retry when connected.')
    }
    const response = new Response(upstream.body, upstream)
    response.headers.set('Cache-Control', 'no-store, private')
    response.headers.set('CDN-Cache-Control', 'no-store')
    response.headers.set('Cloudflare-CDN-Cache-Control', 'no-store')
    response.headers.set('Referrer-Policy', 'no-referrer')
    response.headers.set('X-Content-Type-Options', 'nosniff')
    // Redirects stay in the browser; never follow Google redirects server-side.
    const location = response.headers.get('Location')
    if (location) {
      const redirect = new URL(location, BACKEND)
      if (redirect.origin === BACKEND) response.headers.set('Location', PUBLIC_ORIGIN + redirect.pathname + redirect.search + redirect.hash)
    }
    return response
  },
}
