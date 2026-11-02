import { test, expect, type Page } from '@playwright/test'

async function login(page: Page, subject: string, name: string) {
  await page.goto('/')
  await page.getByLabel('Development ID').fill(subject)
  await page.getByLabel('Display name', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Enter the season' }).click()
  await expect(page.getByLabel('Your group')).toBeVisible()
  { const session = await (await page.request.get('/api/auth/session')).json(); await page.request.put('/api/me/tour/1', { headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token } }); await page.reload() }
  await expect(page.getByLabel('Your group')).toBeVisible()
}
const nav = (page: Page, label: string) => page.locator('.mobile-nav').getByRole('link', { name: label, exact: true })

test('two users join, capture photo/video, share gallery, see feed/ranks and moderate', async ({ browser, page }) => {
  await login(page, 'alice', 'Alice')
  await nav(page, 'Profile').click()
  await page.getByRole('button', { name: 'Create 72-hour invite' }).click()
  const invite = await page.getByLabel('Invite link').inputValue()
  const friendName = 'Kofi ' + Date.now()
  const friend = await browser.newContext({ viewport: { width: 390, height: 844 }, permissions: ['camera', 'microphone'] })
  const bob = await friend.newPage()
  const postIds: string[] = []
  for (const target of [page, bob]) target.on('response', async response => {
    if (response.request().method() === 'POST' && /\/api\/groups\/.+\/(gallery|captures\/.+\/upload)\?/.test(response.url()) && response.status() === 200) {
      const body = await response.json(); postIds.push(body.id)
    }
  })
  try {
    await login(bob, 'friend-' + Date.now(), friendName)
    await bob.getByRole('button', { name: 'Join with invite', exact: true }).click()
    await bob.getByLabel('Invite token or link').fill(invite)
    await bob.getByRole('button', { name: 'Join your people' }).click()
    await expect(bob.getByLabel('Your group')).toBeVisible()
    await nav(page, 'Capture').click()
    await page.getByRole('button', { name: 'Open camera' }).click()
    const live = page.getByLabel('Live camera preview')
    await expect(live).toBeVisible()
    await expect.poll(() => live.evaluate((video: HTMLVideoElement) => video.videoWidth)).toBeGreaterThan(0)
    await page.getByRole('button', { name: 'Take photo' }).click()
    await expect(page.getByAltText('Your photo preview')).toBeVisible()
    await page.getByLabel('Caption (optional)').fill('Final year, same people. 🌼')
    await page.getByRole('button', { name: 'Share this moment' }).click()
    await expect(page.locator('.post-card').first()).toContainText('+1 point')
    await expect(page.locator('.post-caption')).toHaveText('Final year, same people. 🌼')
    await nav(bob, 'Capture').click()
    await bob.getByRole('button', { name: 'Video', exact: true }).click()
    await bob.getByRole('button', { name: 'Open camera' }).click()
    await expect(bob.getByLabel('Live camera preview')).toBeVisible()
    const shutter = await bob.getByRole('button', { name: 'Start recording' }).boundingBox()
    const navigation = await bob.locator('.mobile-nav').boundingBox()
    expect(shutter!.y + shutter!.height).toBeLessThanOrEqual(navigation!.y)
    await bob.screenshot({ path: 'test-results/capture-mobile.png', fullPage: true })
    await bob.getByRole('button', { name: 'Start recording' }).click()
    await expect(bob.getByRole('button', { name: 'Stop recording' })).toBeEnabled({ timeout: 10000 })
    await bob.getByRole('button', { name: 'Stop recording' }).click()
    await expect(bob.getByLabel('Your video preview')).toBeVisible()
    await bob.getByRole('button', { name: 'Share this moment' }).click()
    await expect(bob.locator('.post-card').first()).toContainText('+3 points')
    await nav(bob, 'Capture').click()
    await bob.getByRole('button', { name: 'Upload from gallery' }).click()
    await expect(bob.getByText('Sharing only · 0 points', { exact: true }).first()).toBeVisible()
    const image = await bob.evaluate(async () => {
      const canvas = document.createElement('canvas'); canvas.width = canvas.height = 20
      const ctx = canvas.getContext('2d')!; const pixels = ctx.createImageData(20, 20); crypto.getRandomValues(pixels.data); ctx.putImageData(pixels, 0, 0)
      return canvas.toDataURL('image/png').split(',')[1]
    })
    await bob.getByLabel('Choose gallery photo').setInputFiles({ name: 'gallery.png', mimeType: 'image/png', buffer: Buffer.from(image, 'base64') })
    await bob.getByRole('button', { name: 'Share this moment' }).click()
    await expect(bob.locator('article').filter({ hasText: 'Sharing only · 0 points' })).toBeVisible()
    await expect(bob.locator('article video')).toBeVisible()
    await bob.locator('article video').evaluate(async (video: HTMLVideoElement) => { video.muted = true; await video.play() })
    await expect.poll(() => bob.locator('article video').evaluate((video: HTMLVideoElement) => video.currentTime)).toBeGreaterThan(0)
    await bob.locator('article video').evaluate((video: HTMLVideoElement) => video.pause())
    await nav(bob, 'Leaderboard').click()
    await expect(bob.locator('.rank-list li').filter({ hasText: friendName })).toContainText('3 pts')
    await bob.screenshot({ path: 'test-results/leaderboard-mobile.png', fullPage: true })
    await bob.getByRole('button', { name: 'All time', exact: true }).click()
    await expect(bob.locator('.rank-list li').filter({ hasText: friendName })).toContainText('1 gallery shares')
    await nav(page, 'Feed').click()
    await page.reload()
    await expect(page.locator('article')).toHaveCount(3)
    await expect(page.locator('article img').first()).toBeVisible()
    await expect(page.locator('.streak-badge')).not.toContainText('—')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: 'test-results/feed-mobile.png', fullPage: true })
    await page.setViewportSize({ width: 1440, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: 'test-results/feed-desktop.png', fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    page.once('dialog', dialog => dialog.accept())
    await page.locator('article').filter({ hasText: '+3 points' }).getByRole('button', { name: /Remove post/ }).click()
    await expect(page.locator('article')).toHaveCount(2)
    await nav(bob, 'Feed').click()
    await bob.reload()
    bob.once('dialog', dialog => dialog.accept())
    await bob.locator('article').filter({ hasText: 'Sharing only · 0 points' }).getByRole('button', { name: /Remove post/ }).click()
    await expect(bob.locator('article')).toHaveCount(1)
  } finally {
    const session = await page.request.get('/api/auth/session')
    if (session.ok()) {
      const { csrf_token } = await session.json()
      const groups = await (await page.request.get('/api/groups')).json()
      const group = groups[0].id
      for (const post of new Set(postIds)) await page.request.delete(`/api/groups/${group}/posts/${post}`, { headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': csrf_token } })
      const friendSession = await bob.request.get('/api/auth/session')
      if (friendSession.ok()) {
        const user = (await friendSession.json()).user
        await page.request.delete(`/api/groups/${group}/members/${user.id}`, { headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': csrf_token } })
      }
    }
    await friend.close()
  }
})

test('camera denial, navigation warning and track cleanup', async ({ page }) => {
  await login(page, 'alice', 'Alice')
  await nav(page, 'Capture').click()
  await page.evaluate(() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Denied', 'NotAllowedError') } })
  await page.getByRole('button', { name: 'Open camera' }).click()
  await expect(page.getByRole('alert')).toContainText('Camera permission denied')
  await page.reload()
  await page.getByRole('button', { name: 'Open camera' }).click()
  await expect(page.getByLabel('Live camera preview')).toBeVisible()
  await page.evaluate(() => {
    const media = (document.querySelector('video') as HTMLVideoElement).srcObject as MediaStream
    ;(window as unknown as { captureTracks: MediaStreamTrack[] }).captureTracks = media.getTracks()
  })
  await nav(page, 'Feed').click()
  await expect(page.getByRole('dialog', { name: 'Leave this moment?' })).toBeVisible()
  await page.getByRole('button', { name: 'Stay here' }).focus()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Leave capture' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Stay here' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByLabel('Live camera preview')).toBeVisible()
  await nav(page, 'Feed').click()
  await page.getByRole('button', { name: 'Leave capture' }).click()
  await expect(page.getByLabel('Your group')).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { captureTracks: MediaStreamTrack[] }).captureTracks.every(track => track.readyState === 'ended'))).toBe(true)
})

test('backend unavailable is explicit, no fabricated feed', async ({ page }) => {
  await page.route('**/api/auth/session', route => route.abort())
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('Backend unavailable')
  await expect(page.locator('article')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})

test('a lost acceptance response retries the same operation without a duplicate', async ({ page }) => {
  await login(page, 'alice', 'Alice')
  const session = await (await page.request.get('/api/auth/session')).json()
  const group = (await (await page.request.get('/api/groups')).json())[0].id
  const keys: string[] = []
  let postId = ''
  await page.route(/\/api\/groups\/[^/]+\/gallery\?kind=photo/, async route => {
    keys.push(route.request().headers()['idempotency-key'])
    if (keys.length === 1) {
      const result = await route.fetch()
      expect(result.status()).toBe(200)
      postId = (await result.json()).id
      await route.abort('connectionfailed')
    } else await route.continue()
  })
  try {
    await nav(page, 'Capture').click()
    await page.getByRole('button', { name: 'Upload from gallery' }).click()
    const image = await page.evaluate(() => {
      const canvas = document.createElement('canvas'); canvas.width = canvas.height = 20
      const ctx = canvas.getContext('2d')!; const pixels = ctx.createImageData(20, 20)
      crypto.getRandomValues(pixels.data); ctx.putImageData(pixels, 0, 0)
      return canvas.toDataURL('image/png').split(',')[1]
    })
    await page.getByLabel('Choose gallery photo').setInputFiles({ name: 'retry.png', mimeType: 'image/png', buffer: Buffer.from(image, 'base64') })
    await page.getByLabel('Caption (optional)').fill('x'.repeat(281))
    await page.getByRole('button', { name: 'Share this moment' }).click()
    await expect(page.getByRole('alert')).toContainText('at most 280 characters')
    expect(keys).toHaveLength(0)
    await page.getByLabel('Caption (optional)').fill('<b>Just us.</b>\nNo HTML, only memories.')
    await page.getByRole('button', { name: 'Share this moment' }).click()
    await expect(page.getByRole('alert')).toContainText('Acceptance may have completed')
    await expect(page.getByLabel('Caption (optional)')).toBeDisabled()
    const retry = page.getByRole('button', { name: 'Retry same upload' })
    await expect(retry).toBeEnabled()
    await retry.click()
    await expect(page.locator('article')).toHaveCount(1)
    await expect(page.locator('article')).toContainText('Sharing only · 0 points')
    await expect(page.locator('.post-caption')).toHaveText('<b>Just us.</b>\nNo HTML, only memories.')
    await expect(page.locator('.post-caption b')).toHaveCount(0)
    expect(keys).toHaveLength(2); expect(keys[0]).toBe(keys[1])
    const feed = await (await page.request.get(`/api/groups/${group}/feed`)).json()
    expect(feed.items.map((p: { id: string }) => p.id)).toEqual([postId])
  } finally {
    if (postId) await page.request.delete(`/api/groups/${group}/posts/${postId}`, { headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token } })
  }
})

test('removed membership produces a real backend permission denial', async ({ page, browser }) => {
  await login(page, 'alice', 'Alice')
  const session = await (await page.request.get('/api/auth/session')).json()
  const group = (await (await page.request.get('/api/groups')).json())[0].id
  const headers = { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token }
  const invite = await (await page.request.post(`/api/groups/${group}/invites`, { headers, data: { max_uses: 1 } })).json()
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const member = await context.newPage()
  try {
    await login(member, 'denied-' + Date.now(), 'Removed member')
    await member.getByRole('button', { name: 'Join with invite', exact: true }).click()
    await member.getByLabel('Invite token or link').fill(invite.token)
    await member.getByRole('button', { name: 'Join your people' }).click()
    await expect(member.getByLabel('Your group')).toBeVisible()
    const user = (await (await member.request.get('/api/auth/session')).json()).user.id
    const response = await page.request.delete(`/api/groups/${group}/members/${user}`, { headers })
    expect(response.status()).toBe(200)
    // Keep the currently selected group in memory, invalidate the cached feed
    // by visiting Capture then returning. Real API authorization returns 403.
    await nav(member, 'Capture').click()
    await member.getByRole('button', { name: 'Open camera' }).click()
    await expect(member.getByRole('alert')).toContainText('Permission denied')
  } finally {
    await page.request.delete(`/api/groups/${group}/invites/${invite.id}`, { headers })
    await context.close()
  }
})
