import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { scoreLabel, recordingMime, validateFile, GALLERY_LABEL } from './media'
import { countdowns } from './time'
import { ErrorBox } from '../components/Common'
import { ApiError } from '../api/client'

it('distinguishes gallery from scoring captures without inventing points', () => {
  expect(scoreLabel('gallery', 0)).toBe('Sharing only · 0 points')
  expect(scoreLabel('capture', 1)).toBe('+1 point')
  expect(scoreLabel('capture', 3)).toBe('+3 points')
  render(<p>{GALLERY_LABEL}</p>); expect(screen.getByText('Sharing only · 0 points')).toBeVisible()
})
it('checks browser codecs rather than assuming a recorder format', () => {
  vi.stubGlobal('MediaRecorder', { isTypeSupported: (mime: string) => mime === 'video/mp4' })
  expect(recordingMime()).toBe('video/mp4')
  vi.stubGlobal('MediaRecorder', undefined); expect(recordingMime()).toBeNull()
})
it('prefers explicit H.264/AAC over WebM when both recorders are available', () => {
  vi.stubGlobal('MediaRecorder', { isTypeSupported: () => true })
  expect(recordingMime()).toBe('video/mp4;codecs=avc1.42E01E,mp4a.40.2')
  vi.unstubAllGlobals()
})
it.each([[1280, 720, true], [720, 1280, true], [1920, 1080, false], [722, 722, false]])('checks actual preview dimensions %i × %i', async (width, height, valid) => {
  const video = document.createElement('video')
  Object.defineProperties(video, {
    videoWidth: { value: width }, videoHeight: { value: height }, duration: { value: 5 },
    src: { set: () => queueMicrotask(() => video.dispatchEvent(new Event('loadedmetadata'))) },
  })
  const create = vi.spyOn(document, 'createElement').mockReturnValueOnce(video)
  const revoke = vi.fn()
  vi.stubGlobal('URL', { createObjectURL: () => 'blob:test', revokeObjectURL: revoke })
  try {
    const result = validateFile(new Blob(['test'], { type: 'video/mp4' }), 'video')
    if (valid) await expect(result).resolves.toBeUndefined()
    else await expect(result).rejects.toThrow('720p')
    expect(revoke).toHaveBeenCalledWith('blob:test')
  } finally { create.mockRestore(); vi.unstubAllGlobals() }
})
it('rejects oversized or empty media before a network upload', async () => {
  await expect(validateFile(new Blob([]), 'photo')).rejects.toThrow('nonempty')
  await expect(validateFile(new Blob([new Uint8Array(50 * 1024 * 1024 + 1)]), 'video')).rejects.toThrow('50 MiB')
})
it('rolls Accra days and Monday weeks at the correct boundary', () => {
  expect(countdowns(Date.parse('2026-11-01T23:59:59Z'))).toEqual({ day: '00:00:01', week: '00:00:01' })
  expect(countdowns(Date.parse('2026-11-02T00:00:00Z'))).toEqual({ day: '1d 00:00:00', week: '7d 00:00:00' })
})
it('separates permission denial from backend unavailability', () => {
  const { rerender } = render(<ErrorBox error={new ApiError(403, 'membership_required', 'Active membership required')} />)
  expect(screen.getByRole('alert')).toHaveTextContent('Permission denied')
  rerender(<ErrorBox error={new ApiError(0, 'network_unavailable', 'API is offline')} />)
  expect(screen.getByRole('alert')).toHaveTextContent('Backend unavailable')
  expect(screen.getByRole('alert')).not.toHaveTextContent('Permission denied')
})
