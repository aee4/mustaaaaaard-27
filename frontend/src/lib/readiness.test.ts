import { afterEach, expect, it, vi } from 'vitest'
import { ReadinessController } from './readiness'

afterEach(() => vi.useRealTimers())
const ok = () => new Response('{"ok":true}', { headers: { 'Content-Type': 'application/json' } })

it('starts immediately, shares one request and stops after ready', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn().mockResolvedValue(ok())
  const controller = new ReadinessController(fetcher)
  controller.start(); controller.start()
  expect(fetcher).toHaveBeenCalledOnce()
  expect(fetcher.mock.calls[0][1]).toMatchObject({ cache: 'no-store', redirect: 'error' })
  await vi.advanceTimersByTimeAsync(60_000)
  expect(controller.getSnapshot()).toBe('ready')
  expect(fetcher).toHaveBeenCalledOnce()
  controller.stop()
})

it('rejects HTML and invalid JSON with bounded backoff, times out and retries', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response('<html>Render loading</html>', { headers: { 'Content-Type': 'text/html' } })))
  const controller = new ReadinessController(fetcher, 10_000)
  controller.start()
  await vi.advanceTimersByTimeAsync(10_000)
  expect(controller.getSnapshot()).toBe('timeout')
  expect(fetcher).toHaveBeenCalledTimes(4)
  fetcher.mockImplementation(() => Promise.resolve(ok()))
  controller.retry()
  await vi.advanceTimersByTimeAsync(0)
  expect(controller.getSnapshot()).toBe('ready')
  controller.stop()
})

it('aborts hanging requests without overlap and ignores obsolete responses', async () => {
  vi.useFakeTimers()
  const signals: AbortSignal[] = []
  let finish: (response: Response) => void = () => {}
  const fetcher = vi.fn().mockImplementation((_url, init) => {
    signals.push(init.signal)
    return new Promise<Response>(resolve => { finish = resolve })
  })
  const controller = new ReadinessController(fetcher, 5000, 1000)
  controller.start()
  await vi.advanceTimersByTimeAsync(1000)
  expect(signals[0].aborted).toBe(true)
  expect(fetcher).toHaveBeenCalledOnce()
  await vi.advanceTimersByTimeAsync(4000)
  expect(controller.getSnapshot()).toBe('timeout')
  finish(ok())
  await vi.advanceTimersByTimeAsync(0)
  expect(controller.getSnapshot()).toBe('timeout')
})
