import type { components } from './generated'
import { syncTime } from '../lib/time'

export type Session = components['schemas']['SessionOut']
export type Group = components['schemas']['GroupOut']
export type Post = components['schemas']['PostOut']
export type Feed = components['schemas']['FeedOut']
export type Ranking = components['schemas']['LeaderboardOut']
export type Rank = components['schemas']['RankOut']
export type Profile = components['schemas']['ProfileOut']
export type Capture = components['schemas']['CaptureOut']
export type Media = components['schemas']['MediaOut']
export type Invite = components['schemas']['InviteOut']
export type Kind = 'photo' | 'video'
export type Comment = components['schemas']['CommentOut']
type Comments = components['schemas']['CommentsOut']
type Engagement = components['schemas']['EngagementOut']
type Tour = components['schemas']['TourOut']

let csrf: string | null = null
export function setCsrf(token: string | null) { csrf = token }

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) {
    super(message)
    this.name = 'ApiError'
  }
  get retryable() {
    return this.status === 0 || this.status >= 500 || this.status === 429 ||
      ['upload_in_progress', 'cleanup_pending', 'upload_lease_lost'].includes(this.code)
  }
}

export function parseError(status: number, body: unknown): ApiError {
  const item = body as { error?: { code?: string; message?: string; request_id?: string } }
  return new ApiError(status, item?.error?.code || 'request_failed',
    item?.error?.message || 'The server could not complete this request.', item?.error?.request_id)
}

function authFailure(error: ApiError) {
  if (error.status === 401) {
    csrf = null
    window.dispatchEvent(new Event('mustard:session-expired'))
  }
  return error
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const mutation = !['GET', 'HEAD'].includes(options.method || 'GET')
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (mutation && csrf) headers.set('X-CSRF-Token', csrf)
  let response: Response
  try { response = await fetch('/api' + path, { ...options, headers, credentials: 'include' }) }
  catch { throw new ApiError(0, 'network_unavailable', 'Cannot reach the backend. Check your connection and that the API is running.') }
  let body: unknown
  try { body = await response.json() } catch { body = undefined }
  if (!response.ok) throw authFailure(parseError(response.status, body))
  return body as T
}

export const api = {
  async session() {
    try { const session = await request<Session>('/auth/session'); setCsrf(session.csrf_token); return session }
    catch (e) { if (e instanceof ApiError && e.status === 401) return null; throw e }
  },
  async devLogin(subject: string, display_name: string) {
    const session = await request<Session>('/auth/dev', { method: 'POST', body: JSON.stringify({ subject, display_name }) })
    setCsrf(session.csrf_token)
    return session
  },
  logout: () => request('/auth/logout', { method: 'POST' }),
  groups: () => request<Group[]>('/groups'),
  createGroup: (name: string) => request<Group>('/groups', { method: 'POST', body: JSON.stringify({ name }) }),
  join: (token: string) => request<Group>('/groups/join', { method: 'POST', body: JSON.stringify({ token }) }),
  profile: (g: string, u: string) => request<Profile>(`/groups/${g}/members/${u}`),
  editName: (display_name: string) => request('/me', { method: 'PATCH', body: JSON.stringify({ display_name }) }),
  feed: (g: string, cursor: string | null) => request<Feed>(`/groups/${g}/feed?limit=10${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
  async ranks(g: string, period: 'weekly' | 'all', offset = 0) {
    const result = await request<Ranking>(`/groups/${g}/leaderboard?period=${period}&offset=${offset}&limit=20`)
    syncTime(result.server_time)
    return result
  },
  capture: (g: string, kind: Kind) => request<Capture>(`/groups/${g}/captures`, { method: 'POST', body: JSON.stringify({ kind }) }),
  media: (g: string, p: string) => request<Media>(`/groups/${g}/posts/${p}/media`),
  remove: (g: string, p: string) => request(`/groups/${g}/posts/${p}`, { method: 'DELETE' }),
  invite: (g: string, max_uses: number) => request<Invite>(`/groups/${g}/invites`, { method: 'POST', body: JSON.stringify({ max_uses, expires_in_hours: 72 }) }),
  revoke: (g: string, id: string) => request(`/groups/${g}/invites/${id}`, { method: 'DELETE' }),
  removeMember: (g: string, u: string) => request(`/groups/${g}/members/${u}`, { method: 'DELETE' }),
  like: (g: string, p: string, liked: boolean) => request<Engagement>(`/groups/${g}/posts/${p}/like`, { method: liked ? 'PUT' : 'DELETE' }),
  comments: (g: string, p: string, cursor: string | null) => request<Comments>(`/groups/${g}/posts/${p}/comments?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
  comment: (g: string, p: string, text: string, key: string) => request<Comment>(`/groups/${g}/posts/${p}/comments`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ text }) }),
  deleteComment: (g: string, p: string, id: string) => request(`/groups/${g}/posts/${p}/comments/${id}`, { method: 'DELETE' }),
  pin: (g: string, p: string, pinned: boolean) => request(`/groups/${g}/posts/${p}/pin`, { method: 'PATCH', body: JSON.stringify({ pinned }) }),
  tour: () => request<Tour>('/me/tour/1'),
  completeTour: () => request<Tour>('/me/tour/1', { method: 'PUT' }),
}

export type UploadPlan = { group: string; kind: Kind; capture: Capture | null; file: Blob; key: string; caption?: string | null }
export function upload(plan: UploadPlan, onProgress: (value: number) => void): Promise<Post> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const path = plan.capture ? `/captures/${plan.capture.id}/upload` : '/gallery'
    xhr.open('POST', `/api/groups/${plan.group}${path}?kind=${plan.kind}`)
    xhr.withCredentials = true
    xhr.timeout = 240_000
    xhr.setRequestHeader('Idempotency-Key', plan.key)
    if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf)
    xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.min(99, Math.round(event.loaded / event.total * 100))) }
    xhr.onload = () => {
      let body: unknown
      try { body = JSON.parse(xhr.responseText) } catch { body = undefined }
      if (xhr.status >= 200 && xhr.status < 300) { onProgress(100); resolve(body as Post) }
      else reject(authFailure(parseError(xhr.status, body)))
    }
    xhr.onerror = xhr.ontimeout = () => reject(new ApiError(0, 'upload_unknown',
      'Connection lost. Acceptance may have completed. Retry these same bytes with the same key to check.'))
    const form = new FormData()
    const extension = plan.file.type.startsWith('image/jpeg') ? 'jpg' : plan.file.type.startsWith('image/webp') ? 'webp' : plan.file.type.startsWith('video/mp4') ? 'mp4' : plan.kind === 'photo' ? 'png' : 'webm'
    form.append('file', plan.file, `${plan.kind}.${extension}`)
    if (plan.caption) form.append('caption', plan.caption)
    xhr.send(form)
  })
}
