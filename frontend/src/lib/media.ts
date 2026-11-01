import type { Kind } from '../api/client'
export const GALLERY_LABEL = 'Sharing only · 0 points'
export const scoreLabel = (source: string, points: number) => source === 'gallery' ? GALLERY_LABEL : `+${points} ${points === 1 ? 'point' : 'points'}`
export function recordingMime(): string | null {
  if (typeof MediaRecorder === 'undefined') return null
  return ['video/mp4;codecs=avc1.42E01E,mp4a.40.2', 'video/mp4;codecs=avc1,mp4a.40.2', 'video/webm;codecs=vp8,opus', 'video/webm;codecs=vp9,opus', 'video/mp4', 'video/webm']
    .find(type => MediaRecorder.isTypeSupported(type)) || null
}
export async function validateFile(blob: Blob, kind: Kind): Promise<void> {
  const max = (kind === 'photo' ? 15 : 50) * 1024 * 1024
  if (blob.size === 0 || blob.size > max) throw new Error(`${kind === 'photo' ? 'Photo' : 'Video'} must be nonempty and at most ${kind === 'photo' ? 15 : 50} MiB.`)
  if (kind === 'photo') {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(blob.type)) throw new Error('Choose a JPEG, PNG or WebP image.')
    const image = await createImageBitmap(blob)
    const valid = image.width * image.height <= 40_000_000 && Math.max(image.width, image.height) <= 12000
    image.close()
    if (!valid) throw new Error('Image must be at most 40 million pixels and 12000 pixels per side.')
  } else {
    if (!/^video\/(mp4|webm)/.test(blob.type)) throw new Error('Choose an MP4 or WebM video.')
    const url = URL.createObjectURL(blob)
    try {
      const video = document.createElement('video')
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Video preview timed out. Choose another file.')), 10000)
        video.onloadedmetadata = () => { clearTimeout(timeout); resolve() }
        video.onerror = () => { clearTimeout(timeout); reject(new Error('This browser cannot read that video.')) }
        video.src = url
      })
      // Streaming recordings may report Infinity. The actual recording timer and
      // server decoder validate those; finite gallery durations are checked here.
      if (Number.isFinite(video.duration) && (video.duration < 5 || video.duration > 30)) throw new Error('Video must be 5–30 seconds long.')
      if (Math.min(video.videoWidth, video.videoHeight) > 720 || Math.max(video.videoWidth, video.videoHeight) > 1280) throw new Error('Video must be at most 720p (1280 × 720 landscape or 720 × 1280 portrait). Record with this app or export at 720p.')
    } finally { URL.revokeObjectURL(url) }
  }
}
