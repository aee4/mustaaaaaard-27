import { afterEach, test } from 'node:test'
import assert from 'node:assert/strict'
import worker, { PUBLIC_ORIGIN, BACKEND } from './worker.mjs'
const nativeFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = nativeFetch })

test('static frontend stays available when backend is offline; previews cannot authenticate', async () => {
  globalThis.fetch = () => { throw Error('offline') }
  const env = { ASSETS: { fetch: async () => new Response('static app') } }
  assert.equal(await (await worker.fetch(new Request(PUBLIC_ORIGIN + '/profile'), env)).text(), 'static app')
  assert.equal((await worker.fetch(new Request('https://preview.example/api/auth/session'), env)).status, 403)
})
test('streams to the fixed backend with cookies, CSRF and manual redirects; never caches', async () => {
  const input = new Request(PUBLIC_ORIGIN + '/api/groups/g/gallery?kind=photo&url=https://evil.example', { method: 'POST', body: 'bytes', headers: { Cookie: 'session=test', Origin: PUBLIC_ORIGIN, 'X-CSRF-Token': 'csrf', 'X-Mustard-Origin': 'https://evil.example', 'Idempotency-Key': 'same-key' } })
  globalThis.fetch = async (url, init) => {
    assert.equal(url.origin, BACKEND)
    assert.equal(init.body, input.body)
    assert.equal(init.redirect, 'manual')
    assert.equal(init.cache, 'no-store')
    for (const [name, value] of [['Cookie', 'session=test'], ['Origin', PUBLIC_ORIGIN], ['X-CSRF-Token', 'csrf'], ['Idempotency-Key', 'same-key'], ['X-Mustard-Origin', PUBLIC_ORIGIN]]) assert.equal(init.headers.get(name), value)
    return new Response(null, { status: 303, headers: { Location: BACKEND + '/', 'Set-Cookie': 'test=ok; Secure; HttpOnly; SameSite=Lax; Path=/' } })
  }
  const response = await worker.fetch(input, {})
  assert.equal(response.headers.get('Location'), PUBLIC_ORIGIN + '/')
  assert.match(response.headers.get('Set-Cookie'), /Secure; HttpOnly/)
  assert.match(response.headers.get('Cache-Control'), /no-store/)
})
test('rejects oversized envelopes and reports backend failure as JSON', async () => {
  assert.equal((await worker.fetch(new Request(PUBLIC_ORIGIN + '/api/gallery', { method: 'POST', headers: { 'Content-Length': String(52 * 1024 * 1024) } }), {})).status, 413)
  globalThis.fetch = async () => { throw Error('offline') }
  const response = await worker.fetch(new Request(PUBLIC_ORIGIN + '/api/ready'), {})
  assert.equal(response.status, 503)
  assert.equal((await response.json()).error.code, 'gateway_unavailable')
})
