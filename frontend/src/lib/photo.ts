import type { Kind } from '../api/client'
import { IMAGE_MAX_DIMENSION, IMAGE_MAX_PIXELS, validateFile } from './media'

type PhotoRange = { min?: number; max?: number; step?: number }
type PhotoSettings = { imageWidth: number; imageHeight: number }
type StillCamera = {
  takePhoto: (settings?: PhotoSettings) => Promise<Blob>
  getPhotoCapabilities?: () => Promise<{ imageWidth?: PhotoRange; imageHeight?: PhotoRange }>
}
type StillConstructor = new (track: MediaStreamTrack) => StillCamera

export async function openCameraStream(kind: Kind): Promise<MediaStream> {
  const video: MediaTrackConstraints = kind === 'photo'
    ? { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }
    : { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30, max: 30 } }
  try {
    return await navigator.mediaDevices.getUserMedia({ video, audio: kind === 'video' })
  } catch (error) {
    // Some camera drivers reject resolution negotiation even for ideal values.
    // Permission/device failures should be shown immediately, not prompt again.
    if (kind !== 'photo' || !(error instanceof DOMException) || error.name !== 'OverconstrainedError') throw error
    return navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
  }
}

async function nativePhotoSettings(camera: StillCamera): Promise<PhotoSettings | undefined> {
  if (!camera.getPhotoCapabilities) return
  const { imageWidth: width, imageHeight: height } = await camera.getPhotoCapabilities()
  if (!width?.max || !height?.max || !(width.max > 0 && height.max > 0 && Number.isFinite(width.max * height.max))) return
  const scale = Math.min(1, IMAGE_MAX_DIMENSION / Math.max(width.max, height.max), Math.sqrt(IMAGE_MAX_PIXELS / (width.max * height.max)))
  const align = (range: PhotoRange) => {
    const step = range.step && range.step > 0 ? range.step : 1
    const min = range.min ?? 1
    return Math.floor(min + Math.floor(((range.max ?? 0) * scale - min) / step) * step)
  }
  const imageWidth = align(width), imageHeight = align(height)
  if (imageWidth < (width.min ?? 1) || imageHeight < (height.min ?? 1) || imageWidth * imageHeight > IMAGE_MAX_PIXELS) return
  return { imageWidth, imageHeight }
}

export async function captureStill(video: HTMLVideoElement, track: MediaStreamTrack): Promise<Blob> {
  const NativeCapture = (globalThis as typeof globalThis & { ImageCapture?: StillConstructor }).ImageCapture
  if (NativeCapture && track.readyState === 'live') {
    try {
      const camera = new NativeCapture(track)
      const settings = await nativePhotoSettings(camera).catch(() => undefined)
      // Keep the camera's encoded original: no canvas/JPEG round trip.
      const file = settings
        ? await camera.takePhoto(settings).catch(() => camera.takePhoto())
        : await camera.takePhoto()
      await validateFile(file, 'photo')
      return file
    } catch {
      // Missing/partial ImageCapture support falls back to the actual live frame.
    }
  }
  const width = video.videoWidth, height = video.videoHeight
  if (track.readyState !== 'live' || !width || !height) throw new Error('The camera is still getting ready. Try again in a moment.')
  if (width * height > IMAGE_MAX_PIXELS || Math.max(width, height) > IMAGE_MAX_DIMENSION) throw new Error('Image must be at most 40 million pixels and 12000 pixels per side.')
  const canvas = document.createElement('canvas')
  canvas.width = width; canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Could not capture this photo. Try the gallery instead.')
  // Intrinsic dimensions only: never use CSS dimensions or enlarge a small frame.
  context.drawImage(video, 0, 0)
  return new Promise<Blob>((resolve, reject) => canvas.toBlob(
    file => file ? resolve(file) : reject(new Error('Could not capture this photo.')),
    'image/jpeg', 0.95,
  ))
}
