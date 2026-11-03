import { expect, test } from '@playwright/test'

test('entry invite renders during HTML cold start, gates login and preserves destination', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/ready', route => { attempts++; return route.fulfill({ contentType: 'text/html', body: '<html>Render loading</html>' }) })
  await page.goto('/?invite=synthetic-invite')
  await expect(page.getByRole('heading', { name: 'Welcome to Mustaaaaaard' , exact: false })).toBeVisible()
  await expect(page.getByRole('status')).toContainText('Connecting')
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute('aria-disabled', 'true')
  expect(page.url()).toContain('invite=synthetic-invite')
  expect(attempts).toBeGreaterThan(0)
  await page.unroute('**/api/ready')
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute('aria-disabled', 'false')
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute('href', '/auth/google?return_to=%2F%3Finvite%3Dsynthetic-invite')
})

test('timeout offers Retry and recovery; no session request before readiness', async ({ page }) => {
  await page.clock.install()
  let sessions = 0
  await page.route('**/api/auth/session', route => { sessions++; return route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }) })
  await page.route('**/api/ready', route => route.fulfill({ contentType: 'text/html', body: 'Loading' }))
  await page.goto('/profile')
  await page.clock.runFor(121_000)
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible()
  expect(sessions).toBe(0)
  await page.route('**/api/ready', route => route.fulfill({ contentType: 'application/json', body: '{"ok":true}' }))
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute('aria-disabled', 'false')
  expect(sessions).toBe(1)
  expect(page.url()).toContain('/profile')
})
