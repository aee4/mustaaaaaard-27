import { execFileSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Chromium's default fake camera repeats identical frames between runs. The
// backend intentionally retains duplicate fingerprints after deletion. A fresh
// synthetic source makes reruns distinct without changing application media.
const directory = resolve('../.tools')
mkdirSync(directory, { recursive: true })
execFileSync(process.env.FFMPEG || 'ffmpeg', ['-nostdin', '-v', 'error', '-f', 'lavfi',
  '-i', 'testsrc2=size=640x480:rate=30', '-vf', `drawbox=x=8:y=8:w=90:h=90:color=0x${randomBytes(3).toString('hex')}:t=fill`,
  '-t', '2', '-pix_fmt', 'yuv420p', '-f', 'yuv4mpegpipe', '-y', resolve(directory, 'frontend-camera.y4m')],
{ timeout: 30000, stdio: ['ignore', 'ignore', 'pipe'] })
console.log('Prepared distinct synthetic camera fixture (not a physical device).')
for (const [name, codec, audio, extension] of [
  ['h264-aac', 'libx264', 'aac', 'mp4'],
  ['vp8-opus', 'libvpx', 'libopus', 'webm'],
  ['vp9-vorbis', 'libvpx-vp9', 'libvorbis', 'webm'],
]) {
  execFileSync(process.env.FFMPEG || 'ffmpeg', ['-nostdin', '-v', 'error',
    '-f', 'lavfi', '-i', 'testsrc2=size=128x72:rate=10',
    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
    '-t', '5', '-threads', '1', '-c:v', codec, '-pix_fmt', 'yuv420p', '-c:a', audio,
    '-metadata', 'location=+05.6037-000.1870/', '-metadata', 'title=Synthetic private title',
    '-y', resolve(directory, `frontend-${name}.${extension}`)],
  { timeout: 30000, stdio: ['ignore', 'ignore', 'pipe'] })
}
