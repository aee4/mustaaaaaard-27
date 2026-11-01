import { test, expect, type Page } from '@playwright/test'

async function login(page: Page, subject: string, name: string) {
  await page.goto('/')
  await page.getByLabel('Development ID').fill(subject)
  await page.getByLabel('Display name', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Enter the season' }).click()
  await expect(page.getByLabel('Your group')).toBeVisible()
}
const nav = (page: Page, label: string) => page.locator('.mobile-nav').getByRole('link', { name: label, exact: true })

test('bootstrapped Alice sees the initial group as admin', async ({ page }) => {
  await login(page, 'alice', 'Alice')
  await expect(page.getByLabel('Your group').locator('option:checked')).toHaveText('Mustaaaaaard ’27')
  await expect(page.locator('.section-label')).toContainText('Private & just us')
  await nav(page, 'Profile').click()
  await expect(page.getByRole('button', { name: 'Create 72-hour invite' })).toBeVisible()
  const groups = await (await page.request.get('/api/groups')).json()
  expect(groups.find((group: { name: string }) => group.name === 'Mustaaaaaard ’27').role).toBe('admin')
})

test('no-group user creates, invites and copies, joins as member and switches scoped groups', async ({ browser, page }) => {
  const unique = `${Date.now()}-${Math.floor(Math.random() * 100000)}`
  await login(page, 'owner-' + unique, 'Ama')
  await expect(page.getByRole('heading', { name: 'Your season needs your people.' })).toBeVisible()
  await expect(page.getByText('You haven’t joined a group yet.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create group', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Join with invite', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Create group', exact: true }).click()
  await page.getByLabel('Group name').fill('First people ' + unique)
  await page.getByRole('button', { name: 'Create and open feed' }).click()
  await expect(page).toHaveURL('http://localhost:3000/')
  await expect(page.locator('.section-label')).toContainText('Private & just us')
  await expect(page.getByLabel('Your group').locator('option:checked')).toHaveText('First people ' + unique)
  const firstId = await page.getByLabel('Your group').inputValue()
  await nav(page, 'Profile').click()
  await page.getByRole('button', { name: 'Create 72-hour invite' }).click()
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
  await page.getByRole('button', { name: 'Copy link', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Copied', exact: true })).toBeVisible()
  const link = await page.getByLabel('Invite link').inputValue()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(link)
  await page.screenshot({ path: 'test-results/group-admin-invite.png', fullPage: true })

  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const friend = await context.newPage()
  const session = await (await page.request.get('/api/auth/session')).json()
  const headers = { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token }
  const seeded: { group: string; id: string }[] = []
  async function seed(group: string, caption: string) {
    const image = await page.evaluate(() => {
      const canvas = document.createElement('canvas'); canvas.width = canvas.height = 16
      const ctx = canvas.getContext('2d')!; const pixels = ctx.createImageData(16, 16)
      crypto.getRandomValues(pixels.data); ctx.putImageData(pixels, 0, 0)
      return canvas.toDataURL('image/png').split(',')[1]
    })
    const response = await page.request.post(`/api/groups/${group}/gallery?kind=photo`, {
      headers: { ...headers, 'Idempotency-Key': 'scope-' + crypto.randomUUID() },
      multipart: { file: { name: 'scope.png', mimeType: 'image/png', buffer: Buffer.from(image, 'base64') }, caption },
    })
    expect(response.status()).toBe(200)
    seeded.push({ group, id: (await response.json()).id })
  }
  try {
    await seed(firstId, 'First group only')
    await login(friend, 'member-' + unique, 'Kojo')
    await friend.getByRole('button', { name: 'Join with invite', exact: true }).click()
    await friend.getByLabel('Invite token or link').fill(link)
    await friend.getByRole('button', { name: 'Join your people' }).click()
    await expect(friend.locator('.section-label')).toContainText('Private & just us')
    await expect(friend.getByLabel('Your group')).toHaveValue(firstId)
    await expect(friend.locator('.post-caption')).toHaveText('First group only')
    await nav(friend, 'Profile').click()
    await expect(friend.getByRole('button', { name: 'Create 72-hour invite' })).toHaveCount(0)
    const session = await (await friend.request.get('/api/auth/session')).json()
    const forbidden = await friend.request.post(`/api/groups/${firstId}/invites`, {
      headers: { Origin: 'http://localhost:3000', 'X-CSRF-Token': session.csrf_token }, data: {},
    })
    expect(forbidden.status()).toBe(403)

    await page.getByRole('button', { name: 'Manage groups', exact: true }).click()
    await page.getByRole('button', { name: 'Create group', exact: true }).click()
    await page.getByLabel('Group name').fill('Second people ' + unique)
    await page.getByRole('button', { name: 'Create and open feed' }).click()
    await expect(page.getByLabel('Your group').locator('option:checked')).toHaveText('Second people ' + unique)
    const secondId = await page.getByLabel('Your group').inputValue()
    expect(secondId).not.toBe(firstId)
    await expect(page.getByLabel('Your group').locator('option:checked')).toHaveText('Second people ' + unique)
    expect((await friend.request.get(`/api/groups/${secondId}/feed`)).status()).toBe(403)
    await seed(secondId, 'Second group only')
    await page.reload()
    await page.getByLabel('Your group').selectOption(secondId)
    await expect(page.locator('.post-caption')).toHaveText('Second group only')
    await nav(page, 'Profile').click()
    await expect(page.getByLabel('Invite link')).toHaveCount(0)
    await page.getByRole('button', { name: 'Create 72-hour invite' }).click()
    const secondLink = await page.getByLabel('Invite link').inputValue()
    expect(secondLink).not.toBe(link)
    await friend.getByRole('button', { name: 'Manage groups', exact: true }).click()
    await friend.getByRole('button', { name: 'Join with invite', exact: true }).click()
    await friend.getByLabel('Invite token or link').fill(secondLink)
    await friend.getByRole('button', { name: 'Join your people' }).click()
    await expect(friend.getByLabel('Your group')).toHaveValue(secondId)
    await expect(friend.locator('.section-label')).toContainText('Private & just us')
    await expect(friend.locator('.post-caption')).toHaveText('Second group only')
    await friend.getByLabel('Your group').selectOption(firstId)
    await expect(friend.getByLabel('Your group')).toHaveValue(firstId)
    await expect(friend.locator('.section-label')).toContainText('Private & just us')
    await expect(friend.locator('.post-caption')).toHaveText('First group only')
    await expect(friend.getByText('Second group only', { exact: true })).toHaveCount(0)
    await page.getByLabel('Your group').selectOption(firstId)
    await expect(page.locator('.section-label')).toContainText('Private & just us')
    await nav(page, 'Profile').click()
    await expect(page.getByLabel('Invite link')).toHaveCount(0)
    await page.screenshot({ path: 'test-results/group-switching.png', fullPage: true })
  } finally {
    for (const post of seeded) await page.request.delete(`/api/groups/${post.group}/posts/${post.id}`, { headers })
    await context.close()
  }
})
