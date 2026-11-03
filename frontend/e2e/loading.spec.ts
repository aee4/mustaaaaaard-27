import { test, expect, type Page } from '@playwright/test'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

async function fixture(page: Page, count = 1) {
  const session = await (await page.request.post('/api/auth/dev', { headers: { Origin: 'http://localhost:3000' }, data: { subject: 'loading-' + crypto.randomUUID(), display_name: 'Loading verification' } })).json()
  const headers = { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token }
  const group = await (await page.request.post('/api/groups', { headers, data: { name: 'Loading ' + crypto.randomUUID() } })).json()
  await page.request.put('/api/me/tour/1', { headers })
  await page.goto('/')
  const ids: string[] = []
  for (let index = 0; index < count; index++) {
    const bytes = await page.evaluate(index => {
      const canvas = document.createElement('canvas'); canvas.width = 1920; canvas.height = 1080
      const ctx = canvas.getContext('2d')!, pixels = ctx.createImageData(1920, 1080)
      const noise = crypto.getRandomValues(new Uint8Array(64000))
      for (let i = 0; i < pixels.data.length; i += 4) { pixels.data[i] = noise[(i / 4) % noise.length]; pixels.data[i + 1] = (i / 7680) % 256; pixels.data[i + 2] = (index * 19 + i / 4) % 256; pixels.data[i + 3] = 255 }
      ctx.putImageData(pixels, 0, 0)
      return canvas.toDataURL('image/jpeg', 0.9).split(',')[1]
    }, index)
    const response = await page.request.post(`/api/groups/${group.id}/gallery?kind=photo`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, multipart: { file: { name: 'synthetic.jpg', mimeType: 'image/jpeg', buffer: Buffer.from(bytes, 'base64') } } })
    expect(response.ok()).toBe(true); ids.push((await response.json()).id)
  }
  return { group: group.id as string, headers, ids, cleanup: async () => { for (const id of ids) await page.request.delete(`/api/groups/${group.id}/posts/${id}`, { headers }) } }
}

test('private thumbnails reduce real transfers; refresh, pagination, viewer and navigation retain content', async ({ page }) => {
  test.setTimeout(180000)
  const data = await fixture(page, 12)
  try {
    // Render the actual previous release bundle against the same disposable backend/data.
    const baseline = join(tmpdir(), 'mustard-before-loading-20261103', 'frontend', 'dist')
    let mediaRequests = 0, imageRequests = 0
    page.on('response', response => { if (response.request().resourceType() === 'image') imageRequests++ })
    page.on('request', request => { if (/\/posts\/[^/]+\/media/.test(request.url())) mediaRequests++ })
    await page.route('http://localhost:3000/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path.startsWith('/api/') || path.startsWith('/auth/')) return route.continue()
      const file = path.startsWith('/assets/') ? path : '/index.html'
      await route.fulfill({ path: join(baseline, file), contentType: file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.woff2') ? 'font/woff2' : 'text/html' })
    })
    await page.reload()
    await expect.poll(() => mediaRequests).toBeGreaterThan(0)
    await page.waitForTimeout(500)
    const before = { mediaRequests, imageRequests }
    await page.unroute('http://localhost:3000/**')
    mediaRequests = 0; imageRequests = 0
    await page.reload()
    await expect(page.locator('.media-image.ready').first()).toBeVisible()
    await page.waitForTimeout(500)
    const after = { mediaRequests, imageRequests }
    console.log('Synthetic initial transfer comparison:', JSON.stringify({ before, after }))
    expect(after.mediaRequests).toBeLessThan(before.mediaRequests)
    const first = page.locator('.post-card').first(), image = first.locator('img')
    await expect(image).toHaveAttribute('fetchpriority', 'high')
    const originalSrc = await image.getAttribute('src'), count = imageRequests, links = mediaRequests
    await first.getByRole('button', { name: 'Like post', exact: true }).click()
    await expect(first.locator('.like-count')).toHaveText('1 like')
    await first.getByRole('button', { name: 'Open comments' }).click()
    await page.getByLabel('Add a comment').fill('Synthetic loading test')
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    await expect(page.locator('.comment')).toHaveCount(1)
    await page.getByRole('button', { name: 'Close comments' }).click()
    expect(await image.getAttribute('src')).toBe(originalSrc)
    expect(imageRequests).toBe(count); expect(mediaRequests).toBe(links)
    await first.getByRole('button', { name: 'Open full-quality photo' }).click()
    await expect(page.getByRole('dialog', { name: 'Full-quality photo' }).locator('.media-image.ready')).toBeVisible()
    await page.getByRole('button', { name: 'Close photo' }).click()
    await page.evaluate(() => window.scrollTo(0, 600))
    const y = await page.evaluate(() => window.scrollY)
    await page.locator('.mobile-nav').getByRole('link', { name: 'Profile', exact: true }).click()
    await page.locator('.mobile-nav').getByRole('link', { name: 'Feed', exact: true }).click()
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(y)
    await page.getByRole('button', { name: 'A little further back' }).click()
    await expect(page.locator('.post-card')).toHaveCount(12)
    for (const width of [320, 390, 1440]) { await page.setViewportSize({ width, height: 844 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true) }
  } finally { await data.cleanup() }
})

test('slow, broken and expired media have stable dimensions, bounded renewal and explicit retry', async ({ page }) => {
  const data = await fixture(page)
  try {
    let requests = 0
    await page.route('**/api/groups/*/posts/*/media?*', async route => { requests++; await route.continue() })
    await page.route('http://127.0.0.1:59000/**', async route => { await new Promise(resolve => setTimeout(resolve, 600)); await route.continue() })
    await page.reload()
    await expect(page.locator('.media-image.loading')).toBeVisible()
    const loading = await page.locator('.private-media').boundingBox()
    await expect(page.locator('.media-image.ready')).toBeVisible()
    const ready = await page.locator('.private-media').boundingBox()
    expect(ready!.height).toBeCloseTo(loading!.height, 0)
    await page.unroute('http://127.0.0.1:59000/**')
    await page.route('http://127.0.0.1:59000/**', route => route.fulfill({ status: 403, body: 'Expired synthetic URL' }))
    requests = 0
    await page.reload()
    await expect(page.getByRole('button', { name: 'Retry photo or video' })).toBeVisible()
    expect(requests).toBe(2)
    await page.unroute('http://127.0.0.1:59000/**')
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.getByRole('button', { name: 'Retry photo or video' }).click()
    await expect(page.locator('.media-image.ready')).toBeVisible()
    expect(await page.locator('.media-image img').evaluate(img => getComputedStyle(img).transitionDuration)).toBe('0s')
  } finally { await data.cleanup() }
})

test('synthetic front/rear switching, frame readiness, safe areas, revoke and gallery fallback', async ({ page }) => {
  const data = await fixture(page, 0)
  try {
    await page.addInitScript(() => {
      const state = window as typeof window & { tracks: MediaStreamTrack[]; cameraRequests: MediaStreamConstraints[] }
      state.tracks = []; state.cameraRequests = []
      navigator.mediaDevices.getUserMedia = async constraints => {
        state.cameraRequests.push(constraints!)
        const canvas = document.createElement('canvas'); canvas.width = 1080; canvas.height = 1920
        const draw = canvas.getContext('2d')!; draw.fillStyle = '#d2a422'; draw.fillRect(0, 0, 1080, 1920); draw.fillText('Readable text', 30, 60)
        const stream = canvas.captureStream(30); state.tracks.push(...stream.getTracks())
        const timer = setInterval(() => draw.fillRect(0, 0, 1, 1), 100)
        stream.getTracks().forEach(track => { const stop = track.stop.bind(track); track.stop = () => { clearInterval(timer); stop() } })
        return stream
      }
    })
    await page.goto('/capture')
    await page.getByRole('button', { name: 'Open camera' }).click()
    await expect(page.getByRole('button', { name: 'Take photo' })).toBeEnabled()
    await page.getByRole('button', { name: 'Switch camera' }).click()
    await expect(page.getByRole('button', { name: 'Take photo' })).toBeEnabled()
    const live = page.getByLabel('Live camera preview')
    expect(await live.evaluate(node => getComputedStyle(node).transform)).toBe('matrix(-1, 0, 0, 1, 0, 0)')
    expect(await page.evaluate(() => (window as typeof window & { tracks: MediaStreamTrack[] }).tracks[0].readyState)).toBe('ended')
    for (const width of [320, 390, 1440]) {
      await page.setViewportSize({ width, height: 844 })
      const shutter = await page.getByRole('button', { name: 'Take photo' }).boundingBox()
      expect(shutter!.y).toBeGreaterThanOrEqual(0); expect(shutter!.y + shutter!.height).toBeLessThan(760)
    }
    await page.getByRole('button', { name: 'Take photo' }).click()
    const preview = page.getByAltText('Your photo preview')
    await expect(preview).toBeVisible()
    expect(await preview.evaluate((img: HTMLImageElement) => [img.naturalWidth, img.naturalHeight])).toEqual([1080, 1920])
    expect(await preview.evaluate(img => getComputedStyle(img).transform)).toBe('none')
    expect(await page.evaluate(() => (window as typeof window & { tracks: MediaStreamTrack[] }).tracks.every(track => track.readyState === 'ended'))).toBe(true)
    await page.getByRole('button', { name: 'Retake', exact: true }).click()
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('button', { name: 'Open camera' }).click()
    await expect(page.getByRole('button', { name: 'Take photo' })).toBeEnabled()
    await live.evaluate((node: HTMLVideoElement) => (node.srcObject as MediaStream).getVideoTracks()[0].dispatchEvent(new Event('ended')))
    await expect(page.getByRole('alert')).toContainText('Camera access ended')
    const chooser = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Upload from gallery', exact: true }).click()
    expect(await chooser).toBeTruthy()
  } finally { await data.cleanup() }
})
