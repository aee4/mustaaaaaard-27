import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

async function enter(page: Page) {
  await page.goto('/')
  await page.getByLabel('Development ID').fill('quality-' + crypto.randomUUID())
  await page.getByLabel('Display name', { exact: true }).fill('Synthetic photo verification')
  await page.getByRole('button', { name: 'Enter the season' }).click()
  await expect(page.getByLabel('Your group')).toBeVisible()
  { const session = await (await page.request.get('/api/auth/session')).json(); await page.request.put('/api/me/tour/1', { headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token } }); await page.reload() }
  await page.getByRole('button', { name: 'Create group', exact: true }).click()
  const name = 'Photo quality ' + crypto.randomUUID()
  await page.getByLabel('Group name').fill(name)
  await page.getByRole('button', { name: 'Create and open feed' }).click()
  await expect(page.getByLabel('Your group').locator('option:checked')).toHaveText(name)
  return page.getByLabel('Your group').inputValue()
}

async function removePosts(page: Page, group: string, ids: string[]) {
  const session = await (await page.request.get('/api/auth/session')).json()
  for (const id of ids) await page.request.delete(`/api/groups/${group}/posts/${id}`, {
    headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token },
  })
}

async function syntheticCamera(page: Page, native: boolean, width = 1920, height = 1080) {
  await page.addInitScript(({ native, width, height }) => {
    const state = window as typeof window & { qualitySource?: HTMLCanvasElement; qualityRequest?: MediaStreamConstraints }
    const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height
    const draw = canvas.getContext('2d')!
    draw.fillStyle = '#fff'; draw.fillRect(0, 0, width, height)
    draw.fillStyle = '#111'
    for (let x = 0; x < width; x += 4) draw.fillRect(x, 0, 1, height)
    draw.fillStyle = `rgb(${crypto.getRandomValues(new Uint8Array(3)).join(',')})`
    draw.fillRect(10, 10, 100, 100)
    state.qualitySource = canvas
    navigator.mediaDevices.getUserMedia = async constraints => {
      state.qualityRequest = constraints
      const stream = canvas.captureStream(30), track = stream.getVideoTracks()[0]
      const timer = setInterval(() => draw.fillRect(width - 1, height - 1, 1, 1), 100)
      const stop = track.stop.bind(track)
      track.stop = () => { clearInterval(timer); stop() }
      return stream
    }
    Object.defineProperty(window, 'ImageCapture', { configurable: true, value: native ? class {
      getPhotoCapabilities = async () => ({ imageWidth: { min: 640, max: width, step: 1 }, imageHeight: { min: 480, max: height, step: 1 } })
      takePhoto = async () => new Promise<Blob>(resolve => canvas.toBlob(blob => resolve(blob!), 'image/jpeg', 0.97))
    } : undefined })
  }, { native, width, height })
}

for (const native of [true, false]) {
  test(`${native ? 'native still' : 'canvas fallback'} retains 1080p detail through the real backend`, async ({ page }) => {
    await syntheticCamera(page, native)
    const group = await enter(page), ids: string[] = []
    try {
      await page.locator('.mobile-nav').getByRole('link', { name: 'Capture', exact: true }).click()
      await expect(page.getByRole('button', { name: 'Upload from gallery', exact: true })).toBeVisible()
      await page.getByRole('button', { name: 'Open camera' }).click()
      const preview = page.getByLabel('Live camera preview')
      await expect.poll(() => preview.evaluate((v: HTMLVideoElement) => v.videoWidth)).toBe(1920)
      const requested = await page.evaluate(() => (window as typeof window & { qualityRequest: MediaStreamConstraints }).qualityRequest)
      expect(requested).toMatchObject({ video: { width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      await page.getByRole('button', { name: 'Take photo' }).click()
      const still = page.getByAltText('Your photo preview')
      await expect(still).toBeVisible()
      expect(await still.evaluate((img: HTMLImageElement) => [img.naturalWidth, img.naturalHeight])).toEqual([1920, 1080])
      await page.getByLabel('Caption (optional)').fill('1080p synthetic detail check')
      const accepted = page.waitForResponse(r => r.request().method() === 'POST' && r.url().includes('/upload?kind=photo') && r.status() === 200)
      await page.getByRole('button', { name: 'Share this moment' }).click()
      const post = await (await accepted).json(); ids.push(post.id)
      expect(post.points).toBe(1)
      const quality = await page.evaluate(async ({ group, post }) => {
        const source = (window as typeof window & { qualitySource: HTMLCanvasElement }).qualitySource
        const media = await (await fetch(`/api/groups/${group}/posts/${post}/media`)).json()
        const image = await createImageBitmap(await (await fetch(media.url)).blob())
        const output = document.createElement('canvas'); output.width = image.width; output.height = image.height
        output.getContext('2d')!.drawImage(image, 0, 0); image.close()
        const low = document.createElement('canvas'); low.width = 1280; low.height = 720
        low.getContext('2d')!.drawImage(source, 0, 0, 1280, 720)
        const before = document.createElement('canvas'); before.width = source.width; before.height = source.height
        before.getContext('2d')!.drawImage(low, 0, 0, before.width, before.height)
        const reference = source.getContext('2d')!.getImageData(0, 0, source.width, source.height).data
        function error(canvas: HTMLCanvasElement) {
          const pixels = canvas.getContext('2d')!.getImageData(0, 0, canvas.width, canvas.height).data
          let sum = 0
          for (let i = 0; i < pixels.length; i += 4) for (let c = 0; c < 3; c++) sum += Math.abs(reference[i + c] - pixels[i + c])
          return sum / (source.width * source.height * 3)
        }
        return { width: output.width, height: output.height, beforeError: error(before), afterError: error(output) }
      }, { group, post: post.id })
      expect(quality.width).toBe(1920); expect(quality.height).toBe(1080)
      expect(quality.afterError).toBeLessThan(quality.beforeError * 0.6)
      console.log(`${native ? 'Native' : 'Fallback'} synthetic quality: 1920x1080; 720p baseline MAE ${quality.beforeError.toFixed(2)}, new MAE ${quality.afterError.toFixed(2)} (lower is better).`)
      await expect(page.locator('article img')).toBeVisible()
      expect(await page.locator('article img').evaluate(img => getComputedStyle(img).objectFit)).toBe('contain')
    } finally { await removePosts(page, group, ids) }
  })
}

test('gallery photo/video selection, preview, caption, progress and lost-response retry stay zero-point', async ({ page }) => {
  const group = await enter(page), ids: string[] = []
  try {
    await page.locator('.mobile-nav').getByRole('link', { name: 'Capture', exact: true }).click()
    await page.getByRole('button', { name: 'Upload from gallery', exact: true }).click()
    await expect(page.getByText('No points. No streak activity. Just a memory.')).toBeVisible()
    const encoded = await page.evaluate(() => {
      const canvas = document.createElement('canvas'); canvas.width = 1920; canvas.height = 1080
      const context = canvas.getContext('2d')!; context.fillStyle = `rgb(${crypto.getRandomValues(new Uint8Array(3)).join(',')})`; context.fillRect(0, 0, 1920, 1080)
      return canvas.toDataURL('image/jpeg', 0.95).split(',')[1]
    })
    let first = true, originalKey = ''
    await page.route(url => url.pathname.endsWith('/gallery') && url.searchParams.get('kind') === 'photo', async route => {
      if (!first) { expect(route.request().headers()['idempotency-key']).toBe(originalKey); await route.continue(); return }
      first = false; originalKey = route.request().headers()['idempotency-key']
      await new Promise(resolve => setTimeout(resolve, 500))
      const response = await route.fetch(); expect(response.status()).toBe(200)
      ids.push((await response.json()).id); await route.abort('connectionreset')
    })
    await page.getByLabel('Choose gallery photo').setInputFiles({ name: 'full-size.jpg', mimeType: 'image/jpeg', buffer: Buffer.from(encoded, 'base64') })
    await expect(page.getByAltText('Your photo preview')).toBeVisible()
    await page.getByLabel('Caption (optional)').fill('Gallery photo keeps its caption')
    await page.getByRole('button', { name: 'Share this moment' }).click()
    await expect(page.getByRole('progressbar', { name: 'Upload progress' })).toBeVisible()
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.getByLabel('Caption (optional)')).toBeDisabled()
    const retry = page.getByRole('button', { name: 'Retry same upload' })
    await expect(retry).toBeEnabled({ timeout: 10000 }); await retry.click()
    await expect(page.locator('article')).toHaveCount(1)
    await expect(page.locator('.post-caption')).toHaveText('Gallery photo keeps its caption')
    await page.locator('.mobile-nav').getByRole('link', { name: 'Capture', exact: true }).click()
    await page.getByRole('button', { name: 'Upload from gallery', exact: true }).click()
    await page.getByRole('button', { name: 'Video', exact: true }).click()
    await page.getByLabel('Choose gallery video').setInputFiles({ name: 'gallery.mp4', mimeType: 'video/mp4', buffer: readFileSync('../.tools/frontend-h264-aac.mp4') })
    await expect(page.getByLabel('Your video preview')).toBeVisible()
    await page.getByLabel('Caption (optional)').fill('Gallery video earns no points')
    const accepted = page.waitForResponse(r => r.request().method() === 'POST' && r.url().includes('/gallery?kind=video') && r.status() === 200)
    await page.getByRole('button', { name: 'Share this moment' }).click()
    const post = await (await accepted).json(); ids.push(post.id); expect(post.points).toBe(0)
    await expect(page.locator('article')).toHaveCount(2)
    const ranking = await (await page.request.get(`/api/groups/${group}/leaderboard?period=all`)).json()
    expect(ranking.items[0]).toMatchObject({ points: 0, gallery_photos: 1, gallery_videos: 1, capture_photos: 0, capture_videos: 0, streak: { current: 0 } })
  } finally { await removePosts(page, group, ids) }
})
