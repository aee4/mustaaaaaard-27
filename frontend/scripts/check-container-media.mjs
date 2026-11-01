// URLs arrive only on stdin. Never echo input or browser exception messages.
import { readFileSync } from 'node:fs'
import { chromium } from '@playwright/test'

let browser
try {
  const { base, url } = JSON.parse(readFileSync(0, 'utf8'))
  if (!['127.0.0.1', 'localhost'].includes(new URL(base).hostname) ||
      !['127.0.0.1', 'localhost'].includes(new URL(url).hostname)) throw new Error('Local synthetic test only')
  browser = await chromium.launch({ headless: true, ...(process.env.PW_BROWSER_CHANNEL === 'chrome' ? { channel: 'chrome' } : {}) })
  const page = await browser.newPage()
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 })
  const result = await page.evaluate(async src => {
    const video = document.createElement('video')
    video.muted = true; video.controls = true; document.body.replaceChildren(video)
    return await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Playback deadline')), 20000)
      video.onerror = () => { clearTimeout(timeout); reject(new Error('Decode failed')) }
      video.ontimeupdate = () => {
        if (video.currentTime > 0.2) {
          clearTimeout(timeout); video.pause()
          resolve({ passed: true, width: video.videoWidth, height: video.videoHeight, duration: video.duration })
        }
      }
      video.src = src
      video.play().catch(() => { clearTimeout(timeout); reject(new Error('Playback failed')) })
    })
  }, url)
  console.log(JSON.stringify(result))
} catch {
  console.log(JSON.stringify({ passed: false, failure: 'browser_playback_failed' }))
  process.exitCode = 1
} finally {
  await browser?.close()
}
