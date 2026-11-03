// Receives a temporary operator test session through stdin; never logs its input.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { chromium } from '@playwright/test'
const input = JSON.parse(readFileSync(0, 'utf8'))
const origin = 'https://mustaaaaaard-27.eeyramagbetor.workers.dev'
const browser = await chromium.launch({ channel: 'chrome' })
try {
  const context = await browser.newContext()
  await context.addCookies([{ name: 'mustard_session', value: input.cookie, domain: new URL(origin).hostname, path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  const page = await context.newPage()
  await page.goto(origin)
  await page.waitForFunction(() => document.querySelector('.group-picker'))
  const result = await page.evaluate(async ({ group, post }) => {
    const session = await fetch('/api/auth/session', { cache: 'no-store' })
    const csrf = await fetch('/api/me', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ display_name: 'must not change' }) })
    const media = await (await fetch(`/api/groups/${group}/posts/${post}/media`, { cache: 'no-store' })).json()
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'; video.muted = true; video.playsInline = true
    document.body.append(video)
    const played = new Promise(resolve => {
      const timer = setTimeout(() => resolve(false), 20000)
      video.ontimeupdate = () => { if (video.currentTime > 0) { clearTimeout(timer); resolve(true) } }
      video.onerror = () => { clearTimeout(timer); resolve(false) }
    })
    video.src = media.url
    await video.play()
    const moving = await played
    const values = { session: session.status, csrf: csrf.status, httpOnly: !document.cookie.includes('mustard_session'), moving, duration: video.duration, width: video.videoWidth }
    video.pause(); video.remove()
    return values
  }, { group: input.group, post: input.post })
  assert.equal(result.session, 200); assert.equal(result.csrf, 403); assert.equal(result.httpOnly, true)
  assert.equal(result.moving, true); assert.equal(result.width, 320); assert.ok(result.duration >= 5)
  console.log('production_browser=session_HttpOnly,CSRF_rejection,private_R2_video_playback_passed')
} finally { await browser.close() }
