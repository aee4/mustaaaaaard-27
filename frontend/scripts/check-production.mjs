import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const browser = await chromium.launch({ channel: process.env.PW_BROWSER_CHANNEL === 'chromium' ? undefined : 'chrome' })
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
  const base = process.env.PW_BASE_URL || 'http://localhost:3000'
  await page.goto(base)
  assert.equal(await page.title(), 'Mustaaaaaard ’27')
  for (const name of ['favicon-16.png', 'favicon-32.png', 'favicon.ico', 'apple-touch-icon.png']) {
    assert.equal((await page.request.get(`${base}/${name}`)).status(), 200)
  }
  await page.getByRole('link', { name: 'Continue with Google' }).waitFor()
  assert.equal(await page.getByLabel('Development ID').count(), 0, 'Production must not show development authentication')
  assert.equal(await page.locator('.dev-login').count(), 0)
  const google = page.getByRole('link', { name: 'Continue with Google' })
  if (await google.getAttribute('aria-disabled') === 'true') assert.equal(await google.getAttribute('href'), null)
  else assert.equal(await google.getAttribute('href'), '/auth/google?return_to=%2F')
  await page.evaluate(() => document.fonts.ready)
  assert.equal(await page.evaluate(() => [...document.fonts].some(font => font.family === 'Inter Variable' && font.status === 'loaded')), true, 'Production font must load')
  const license = await page.request.get(`${base}/INTER-LICENSE.txt`)
  assert.equal(license.status(), 200)
  assert.match(await license.text(), /SIL OPEN FONT LICENSE/)
  mkdirSync('test-results', { recursive: true })
  await page.screenshot({ path: 'test-results/login-production.png', fullPage: true })
  console.log(`Production login verified: Google entry present, development form absent. Chrome ${browser.version()}`)
} finally { await browser.close() }
