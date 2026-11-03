export type Readiness = 'idle' | 'connecting' | 'ready' | 'timeout'

// One controller per document, independent of routes and React's mount cycle.
export class ReadinessController {
  private state: Readiness = 'idle'
  private listeners = new Set<() => void>()
  private active?: AbortController
  private timer?: ReturnType<typeof setTimeout>
  private deadline?: ReturnType<typeof setTimeout>
  private generation = 0
  constructor(private fetcher: typeof fetch = (...args) => fetch(...args), private budget = 120_000, private requestBudget = 12_000) {}
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private set(state: Readiness) { this.state = state; this.listeners.forEach(listener => listener()) }
  start = () => {
    if (this.state === 'connecting' || this.state === 'ready') return
    this.stop()
    const generation = this.generation
    this.set('connecting')
    this.deadline = setTimeout(() => { this.stop(); this.set('timeout') }, this.budget)
    void this.probe(generation, 0)
  }
  retry = () => { this.stop(); this.set('idle'); this.start() }
  unavailable = () => { if (this.state === 'ready') this.retry() }
  stop = () => {
    this.generation++
    clearTimeout(this.timer); clearTimeout(this.deadline)
    this.active?.abort(); this.active = undefined
  }
  private async probe(generation: number, attempt: number) {
    const controller = new AbortController()
    this.active = controller
    const timeout = setTimeout(() => controller.abort(), this.requestBudget)
    let ready = false
    try {
      const response = await this.fetcher('/api/ready', { cache: 'no-store', credentials: 'include', redirect: 'error', signal: controller.signal, headers: { Accept: 'application/json' } })
      if (response.ok && response.headers.get('Content-Type')?.includes('application/json')) {
        ready = (await response.json() as { ok?: boolean }).ok === true
      } else { await response.body?.cancel() }
    } catch { /* Render's HTML startup page and network failures mean not ready. */ }
    finally { clearTimeout(timeout) }
    if (generation !== this.generation) return
    this.active = undefined
    if (ready) { clearTimeout(this.deadline); this.set('ready'); return }
    this.timer = setTimeout(() => void this.probe(generation, attempt + 1), Math.min(1000 * 2 ** attempt, 8000))
  }
}

export const readiness = new ReadinessController()
