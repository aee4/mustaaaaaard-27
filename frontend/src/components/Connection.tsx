import { useSyncExternalStore } from 'react'
import { readiness } from '../lib/readiness'

export const useReadiness = () => useSyncExternalStore(readiness.subscribe, readiness.getSnapshot)

export function Connection() {
  const status = useReadiness()
  if (status === 'idle' || status === 'ready') return null
  return <div className="connection-status" role="status" aria-live="polite"><strong>Mustaaaaaard ’27</strong> {status === 'timeout'
    ? <><span>Couldn’t connect. Your place is saved.</span><button className="text-button" onClick={readiness.retry}>Retry</button></>
    : <span>Connecting… <small>Our free backend may need a moment to wake up.</small></span>}</div>
}
