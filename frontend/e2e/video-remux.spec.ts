import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

test('real signed remuxed MP4 and WebM play in Chrome; unsigned storage stays private', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Development ID').fill('remux-' + Date.now())
  await page.getByLabel('Display name', { exact: true }).fill('Synthetic video check')
  await page.getByRole('button', { name: 'Enter the season' }).click()
  await expect(page.getByLabel('Your group')).toBeVisible()
  { const session = await (await page.request.get('/api/auth/session')).json(); await page.request.put('/api/me/tour/1', { headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token } }); await page.reload() }
  await expect(page.getByRole('button', { name: 'Create group', exact: true })).toBeVisible()
  const session = await (await page.request.get('/api/auth/session')).json()
  const headers = { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token }
  const created = await page.request.post('/api/groups', { headers, data: { name: 'Synthetic remux ' + Date.now() } })
  expect(created.ok()).toBe(true)
  const group = (await created.json()).id
  const ids: string[] = []
  try {
    for (const [name, extension] of [['h264-aac', 'mp4'], ['vp8-opus', 'webm'], ['vp9-vorbis', 'webm']]) {
      const response = await page.request.post(`/api/groups/${group}/gallery?kind=video`, {
        headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
        multipart: { file: { name: `${name}.${extension}`, mimeType: `video/${extension}`, buffer: readFileSync(`../.tools/frontend-${name}.${extension}`) } },
      })
      expect(response.status(), await response.text()).toBe(200)
      const post = await response.json()
      ids.push(post.id)
      expect(post.points).toBe(0)
      const media = await (await page.request.get(`/api/groups/${group}/posts/${post.id}/media`)).json()
      const signed = await page.request.get(media.url)
      expect(signed.status()).toBe(200)
      expect(signed.headers()['content-type']).toContain(`video/${extension}`)
      const unsigned = new URL(media.url); unsigned.search = ''
      expect((await page.request.get(unsigned.href)).status()).toBe(403)
    }
    await page.reload()
    // Below-fold media is mounted only as it approaches the viewport.
    for (const article of await page.locator('article').all()) {
      await article.scrollIntoViewIfNeeded()
      await page.waitForTimeout(100)
    }
    await expect(page.locator('article video')).toHaveCount(3)
    for (const video of await page.locator('article video').all()) {
      await video.evaluate(async (element: HTMLVideoElement) => { element.muted = true; await element.play() })
      await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeGreaterThan(0)
      expect(await video.evaluate((element: HTMLVideoElement) => element.videoWidth)).toBe(128)
      await video.evaluate((element: HTMLVideoElement) => element.pause())
    }
    const ranks = await (await page.request.get(`/api/groups/${group}/leaderboard?period=all`)).json()
    expect(ranks.items[0].points).toBe(0)
  } finally {
    for (const id of ids) await page.request.delete(`/api/groups/${group}/posts/${id}`, { headers })
  }
})
