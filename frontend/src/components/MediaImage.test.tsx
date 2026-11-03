import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MediaImage } from './MediaImage'

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

it('reserves portrait space and reveals only after decode, with no minimum delay', async () => {
  let decoded!: () => void
  vi.spyOn(HTMLImageElement.prototype, 'complete', 'get').mockReturnValue(false)
  Object.defineProperty(HTMLImageElement.prototype, 'decode', { configurable: true, value: vi.fn(() => new Promise<void>(resolve => { decoded = resolve })) })
  const failure = vi.fn()
  render(<MediaImage src="/private-test" width={600} height={900} alt="Test photo" onFailure={failure} />)
  const img = screen.getByRole('img')
  expect(img.parentElement).toHaveStyle({ aspectRatio: '600 / 900' })
  fireEvent.load(img)
  expect(img.parentElement).toHaveClass('loading')
  await act(async () => decoded())
  expect(img.parentElement).toHaveClass('ready')
  expect(failure).not.toHaveBeenCalled()
})

it('uses already cached images immediately and keeps them mounted on parent updates', async () => {
  vi.spyOn(HTMLImageElement.prototype, 'complete', 'get').mockReturnValue(true)
  vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockReturnValue(500)
  Object.defineProperty(HTMLImageElement.prototype, 'decode', { configurable: true, value: vi.fn().mockResolvedValue(undefined) })
  const props = { src: '/cached', alt: 'Cached', onFailure: vi.fn(), priority: true, eager: true }
  const view = render(<MediaImage {...props} />)
  const img = screen.getByRole('img')
  await act(async () => {})
  expect(img.parentElement).toHaveClass('ready')
  view.rerender(<MediaImage {...props} />)
  expect(screen.getByRole('img')).toBe(img)
  expect(img).toHaveAttribute('fetchpriority', 'high')
  expect(img).toHaveAttribute('loading', 'eager')
})

it('stops loading after a timeout and reports failure only once', async () => {
  vi.useFakeTimers()
  vi.spyOn(HTMLImageElement.prototype, 'complete', 'get').mockReturnValue(false)
  const failure = vi.fn()
  render(<MediaImage src="/stalled" alt="Stalled" onFailure={failure} />)
  await act(async () => vi.advanceTimersByTime(20000))
  fireEvent.error(screen.getByRole('img'))
  expect(failure).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('img').parentElement).toHaveClass('error')
})
