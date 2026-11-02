import { afterEach, expect, it, vi } from 'vitest'
import { captureStill, openCameraStream } from './photo'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('requests 1080p photos independently of unchanged 720p/30fps video constraints', async () => {
  const getUserMedia = vi.fn().mockResolvedValue({})
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  await openCameraStream('photo'); await openCameraStream('video')
  expect(getUserMedia.mock.calls[0][0]).toEqual({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
  expect(getUserMedia.mock.calls[1][0]).toEqual({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30, max: 30 } }, audio: true })
})

it('relaxes photo negotiation only on a constraint error, never on permission denial', async () => {
  const getUserMedia = vi.fn().mockRejectedValueOnce(new DOMException('Resolution unavailable', 'OverconstrainedError')).mockResolvedValueOnce({})
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  await openCameraStream('photo')
  expect(getUserMedia).toHaveBeenLastCalledWith({ video: { facingMode: { ideal: 'environment' } }, audio: false })
  getUserMedia.mockReset().mockRejectedValue(new DOMException('Denied', 'NotAllowedError'))
  await expect(openCameraStream('photo')).rejects.toThrow('Denied')
  expect(getUserMedia).toHaveBeenCalledTimes(1)
})

const track = { readyState: 'live' } as MediaStreamTrack
const video = (width = 640, height = 480) => {
  const element = document.createElement('video')
  Object.defineProperties(element, { videoWidth: { value: width }, videoHeight: { value: height } })
  element.style.width = '200px'; element.style.height = '100px'
  return element
}

it('keeps the native still original at its camera resolution without canvas recompression', async () => {
  const file = new Blob(['native JPEG'], { type: 'image/jpeg' })
  const takePhoto = vi.fn().mockResolvedValue(file)
  vi.stubGlobal('ImageCapture', class {
    takePhoto = takePhoto
    getPhotoCapabilities = async () => ({ imageWidth: { min: 640, max: 4032, step: 1 }, imageHeight: { min: 480, max: 3024, step: 1 } })
  })
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({ width: 4032, height: 3024, close: vi.fn() }))
  const preview = video()
  const create = vi.spyOn(document, 'createElement')
  expect(await captureStill(preview, track)).toBe(file)
  expect(takePhoto).toHaveBeenCalledWith({ imageWidth: 4032, imageHeight: 3024 })
  expect(create).not.toHaveBeenCalled()
})

it('bounds native still requests by existing safety limits and supported steps', async () => {
  const takePhoto = vi.fn().mockResolvedValue(new Blob(['native'], { type: 'image/jpeg' }))
  vi.stubGlobal('ImageCapture', class {
    takePhoto = takePhoto
    getPhotoCapabilities = async () => ({ imageWidth: { min: 640, max: 16000, step: 16 }, imageHeight: { min: 480, max: 12000, step: 16 } })
  })
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({ width: 1920, height: 1080, close: vi.fn() }))
  await captureStill(video(), track)
  const requested = takePhoto.mock.calls[0][0]
  expect(requested.imageWidth * requested.imageHeight).toBeLessThanOrEqual(40_000_000)
  expect(Math.max(requested.imageWidth, requested.imageHeight)).toBeLessThanOrEqual(12000)
  expect((requested.imageWidth - 640) % 16).toBe(0)
})

it('uses the device default still when explicit photo settings are unsupported', async () => {
  const file = new Blob(['native'], { type: 'image/jpeg' })
  const takePhoto = vi.fn().mockRejectedValueOnce(new DOMException('Unsupported', 'NotSupportedError')).mockResolvedValue(file)
  vi.stubGlobal('ImageCapture', class {
    takePhoto = takePhoto
    getPhotoCapabilities = async () => ({ imageWidth: { min: 640, max: 1920 }, imageHeight: { min: 480, max: 1080 } })
  })
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({ width: 1920, height: 1080, close: vi.fn() }))
  expect(await captureStill(video(), track)).toBe(file)
  expect(takePhoto).toHaveBeenLastCalledWith()
})

it.each([[1920, 1080], [640, 480], [1080, 1920]])('fallback captures actual %i×%i pixels, ignoring CSS size without upscaling', async (width, height) => {
  vi.stubGlobal('ImageCapture', undefined)
  const drawImage = vi.fn()
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D)
  const encode = vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (this: HTMLCanvasElement, callback) {
    expect(this.width).toBe(width); expect(this.height).toBe(height)
    callback(new Blob(['high quality'], { type: 'image/jpeg' }))
  })
  const preview = video(width, height)
  expect((await captureStill(preview, track)).type).toBe('image/jpeg')
  expect(drawImage).toHaveBeenCalledWith(preview, 0, 0)
  expect(encode).toHaveBeenCalledWith(expect.any(Function), 'image/jpeg', 0.95)
})

it('falls back when ImageCapture fails and rejects an unready frame', async () => {
  vi.stubGlobal('ImageCapture', class { takePhoto = async () => { throw new Error('Camera stills unavailable') } })
  await expect(captureStill(video(0, 0), track)).rejects.toThrow('still getting ready')
})

it('rejects an unsafe fallback size before allocating a canvas', async () => {
  vi.stubGlobal('ImageCapture', undefined)
  const preview = video(13000, 1080)
  const create = vi.spyOn(document, 'createElement')
  await expect(captureStill(preview, track)).rejects.toThrow('12000 pixels')
  expect(create).not.toHaveBeenCalled()
})
