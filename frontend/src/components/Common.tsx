import { useEffect, useState } from 'react'
import { AlertCircle, Clock3, RefreshCw, ShieldCheck } from 'lucide-react'
import { ApiError, type Rank } from '../api/client'
import { countdowns, serverNow } from '../lib/time'

export function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  const api = error instanceof ApiError ? error : null
  return <div className="error-box" role="alert"><AlertCircle size={20} /><div>
    <strong>{api?.status === 403 ? 'Permission denied' : api?.status === 401 ? 'Please sign in again' : api?.status === 0 ? 'Backend unavailable' : 'Couldn’t complete that'}</strong>
    <p>{message}</p>{api?.requestId && <small>Request {api.requestId}</small>}
    {retry && <button className="text-button" onClick={retry}><RefreshCw size={14} /> Try again</button>}
  </div></div>
}
export function Loading({ text = 'Getting your season…' }: { text?: string }) {
  return <div className="loading" role="status"><span className="spinner" />{text}</div>
}
export function Avatar({ name }: { name: string }) {
  return <span className="avatar" aria-hidden="true">{name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase()}</span>
}
export function Stats({ rank }: { rank: Rank | undefined }) {
  return <div className="stats"><div><strong>{rank ? rank.points : '—'}</strong><span>points</span></div>
    <div><strong>{rank ? rank.streak.current : '—'}</strong><span>day streak</span></div>
    <div><ShieldCheck size={24} /><span>{rank ? rank.streak.grace_used_this_week ? 'Grace used' : 'Grace available' : 'Grace syncing'}</span></div></div>
}
export function Countdowns() {
  const [now, setNow] = useState(serverNow)
  useEffect(() => { const id = setInterval(() => setNow(serverNow()), 1000); return () => clearInterval(id) }, [])
  const value = now === null ? null : countdowns(now)
  return <div className="countdowns"><span><Clock3 size={15} /> Today ends in <b>{value?.day || 'syncing…'}</b></span>
    <span>Week ends in <b>{value?.week || 'syncing…'}</b></span><small>Africa/Accra · server-synced</small></div>
}

export function Skeleton({ kind }: { kind: 'feed' | 'profile' | 'leaderboard' | 'comments' }) {
  return <div className={`loading-skeleton ${kind}`} role="status" aria-label={`Loading ${kind}`}>
    <span className="sr-only">Loading {kind}</span>
    {Array.from({ length: kind === 'feed' ? 2 : 3 }, (_, i) => <div className="skeleton-row" key={i} aria-hidden="true"><div className="skeleton skeleton-avatar" /><div className="skeleton skeleton-line" />{kind === 'feed' && <div className="skeleton skeleton-photo" />}</div>)}
  </div>
}
