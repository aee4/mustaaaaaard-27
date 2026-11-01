import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, request, setCsrf, upload, type UploadPlan } from './client'

beforeEach(() => setCsrf(null))
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
describe('session and CSRF contract', () => {
  it('creates groups with only the name and authenticated mutation headers', async () => {
    setCsrf('group-csrf')
    const fetcher = vi.fn().mockResolvedValue(json({ id: 'g', name: 'Our people', role: 'admin' }, 201))
    vi.stubGlobal('fetch', fetcher)
    expect(await api.createGroup('Our people')).toEqual({ id: 'g', name: 'Our people', role: 'admin' })
    const [url, options] = fetcher.mock.calls[0]
    expect(url).toBe('/api/groups'); expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ name: 'Our people' })
    expect(options.credentials).toBe('include')
    expect(options.headers.get('X-CSRF-Token')).toBe('group-csrf')
  })
  it('keeps the cookie and CSRF in the right channels and never writes storage', async () => {
    const store = vi.spyOn(Storage.prototype, 'setItem')
    const fetcher = vi.fn().mockResolvedValueOnce(json({ user: { id: 'u', display_name: 'A' }, csrf_token: 'session-csrf', expires_at: '2027-01-01' })).mockResolvedValue(json({ ok: true }))
    vi.stubGlobal('fetch', fetcher)
    await api.session(); await request('/me', { method: 'PATCH', body: JSON.stringify({ display_name: 'B' }) })
    const options = fetcher.mock.calls[1][1]
    expect(options.credentials).toBe('include')
    expect(options.headers.get('X-CSRF-Token')).toBe('session-csrf')
    expect(options.headers.get('Content-Type')).toBe('application/json')
    expect(fetcher.mock.calls[0][1].headers.has('X-CSRF-Token')).toBe(false)
    expect(store).not.toHaveBeenCalled()
  })
  it('treats 401 as signed out while retaining network errors', async () => {
    const expired = vi.fn(); window.addEventListener('mustard:session-expired', expired)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: { code: 'authentication_required', message: 'Sign in' } }, 401)))
    expect(await api.session()).toBeNull(); expect(expired).toHaveBeenCalledOnce()
    window.removeEventListener('mustard:session-expired', expired)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(api.session()).rejects.toMatchObject({ code: 'network_unavailable', status: 0 })
  })
  it.each([403, 422, 503])('preserves status %s, code and request ID', async status => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: { code: 'stable_code', message: 'Safe message', request_id: 'r123' } }, status)))
    await expect(request('/resource')).rejects.toMatchObject({ status, code: 'stable_code', requestId: 'r123', message: 'Safe message' })
  })
})

class FakeXHR {
  static items: FakeXHR[] = []
  headers: Record<string, string> = {}
  upload = { onprogress: null as null | ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) }
  onload = () => {}; onerror = () => {}; ontimeout = () => {}
  status = 0; responseText = ''; withCredentials = false; timeout = 0; url = ''; body?: FormData
  constructor() { FakeXHR.items.push(this) }
  open(_method: string, url: string) { this.url = url }
  setRequestHeader(key: string, value: string) { this.headers[key] = value }
  send(body: FormData) { this.body = body }
  finish(status: number, body: unknown) { this.status = status; this.responseText = JSON.stringify(body); this.onload() }
}
describe('upload retries', () => {
  it('reuses the same key, operation and bytes after an uncertain result without automatic resubmission', async () => {
    FakeXHR.items = []; vi.stubGlobal('XMLHttpRequest', FakeXHR); setCsrf('csrf')
    const plan: UploadPlan = { group: 'group', kind: 'photo', capture: { id: 'capture', kind: 'photo', expires_at: '2027-01-01' }, file: new Blob(['original'], { type: 'image/png' }), key: 'fixed-key', caption: 'Final year, same people.' }
    const progress = vi.fn()
    const first = upload(plan, progress)
    const rejection = expect(first).rejects.toMatchObject({ status: 0, code: 'upload_unknown' })
    FakeXHR.items[0].onerror(); await rejection
    expect(FakeXHR.items).toHaveLength(1)
    const second = upload(plan, progress)
    const [a, b] = FakeXHR.items
    expect(b.url).toBe(a.url); expect(b.headers['Idempotency-Key']).toBe('fixed-key')
    expect(b.headers['X-CSRF-Token']).toBe('csrf'); expect(b.withCredentials).toBe(true)
    expect(b.headers['Content-Type']).toBeUndefined()
    expect(a.body!.get('caption')).toBe('Final year, same people.')
    expect(b.body!.get('caption')).toBe(a.body!.get('caption'))
    expect((b.body!.get('file') as File).size).toBe((a.body!.get('file') as File).size)
    b.upload.onprogress?.({ lengthComputable: true, loaded: 10, total: 10 })
    expect(progress).toHaveBeenLastCalledWith(99)
    b.finish(200, { id: 'accepted', points: 1 }); expect(await second).toEqual({ id: 'accepted', points: 1 })
    expect(progress).toHaveBeenLastCalledWith(100)
  })
  it('keeps gallery on its explicit zero-point path and exposes conflicting input', async () => {
    FakeXHR.items = []; vi.stubGlobal('XMLHttpRequest', FakeXHR)
    const result = upload({ group: 'g', kind: 'video', capture: null, file: new Blob(['same']), key: 'gallery-key' }, () => {})
    const rejection = expect(result).rejects.toMatchObject({ status: 409, code: 'idempotency_conflict', retryable: false })
    const xhr = FakeXHR.items[0]
    expect(xhr.url).toBe('/api/groups/g/gallery?kind=video')
    xhr.finish(409, { error: { code: 'idempotency_conflict', message: 'Different input' } }); await rejection
    expect(new ApiError(409, 'upload_in_progress', '').retryable).toBe(true)
    expect(new ApiError(409, 'capture_expired', '').retryable).toBe(false)
  })
})
