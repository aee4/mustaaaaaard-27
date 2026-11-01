import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'

const phase = process.argv[2] || 'after'
const directory = fileURLToPath(new URL(`../../.tools/typography-${phase}/`, import.meta.url))
mkdirSync(directory, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome' })
try {
  for (const [size, viewport] of Object.entries({ mobile: { width: 390, height: 844 }, desktop: { width: 1440, height: 1000 }, narrow: { width: 320, height: 740 } })) {
    const context = await browser.newContext({ viewport })
    const page = await context.newPage()
    async function shot(name) {
      await page.evaluate(() => document.fonts.ready)
      if (phase === 'after') {
        assert.equal(await page.evaluate(() => [...document.fonts].some(font => font.family === 'Inter Variable' && font.status === 'loaded')), true, 'Self-hosted font loaded')
        const problems = await page.evaluate(() => [...document.querySelectorAll('body, h1, h2, h3, p, button, input, textarea, select, span, strong, small, b, label, a, em')]
          .filter(node => node.getBoundingClientRect().width > 0)
          .filter(node => { const style = getComputedStyle(node); return !style.fontFamily.includes('Inter Variable') || style.fontStyle !== 'normal' || Math.abs(parseFloat(style.letterSpacing) || 0) > parseFloat(style.fontSize) * .03 })
          .map(node => node.tagName + '.' + node.className))
        assert.deepEqual(problems, [], `${size}/${name}: shared typography`)
        assert.equal(await page.evaluate(() => [...document.querySelectorAll('.stats strong, .rank-points, .place, .profile-totals b, .countdowns')].every(node => getComputedStyle(node).fontVariantNumeric.includes('tabular-nums'))), true, 'Tabular numerals')
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false, `${size}/${name}: horizontal overflow`)
      }
      await page.screenshot({ path: `${directory}/${size}-${name}.png`, fullPage: true })
    }
    await page.goto('http://localhost:3000')
    await page.getByLabel('Development ID').waitFor()
    await shot('login')
    await page.getByLabel('Development ID').fill('alice')
    await page.getByLabel('Display name', { exact: true }).fill('Alice')
    await page.getByRole('button', { name: 'Enter the season' }).click()
    await page.getByLabel('Your group').locator('option:checked').filter({ hasText: 'Mustaaaaaard' }).waitFor({ state: 'attached' })
    for (const [name, path] of Object.entries({ feed: '/', capture: '/capture', leaderboard: '/leaderboard', profile: '/profile' })) {
      await page.goto('http://localhost:3000' + path)
      await page.locator('#page-content').waitFor()
      await page.waitForTimeout(300)
      await shot(name)
    }
    if (phase === 'after') {
      await page.goto('http://localhost:3000/capture')
      await page.getByRole('button', { name: 'Open camera' }).waitFor()
      await page.evaluate(() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Synthetic permission denial', 'NotAllowedError') } })
      await page.getByRole('button', { name: 'Open camera' }).click()
      await page.getByRole('alert').waitFor()
      await shot('camera-denied')
      await page.getByRole('button', { name: /Gallery/ }).click()
      await shot('gallery')
      const png = await page.evaluate(() => { const canvas = document.createElement('canvas'); canvas.width = canvas.height = 64; const ctx = canvas.getContext('2d'); ctx.fillStyle = '#e9b52e'; ctx.fillRect(0, 0, 64, 64); return canvas.toDataURL('image/png').split(',')[1] })
      await page.getByLabel('Choose gallery photo').setInputFiles({ name: 'synthetic-preview.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') })
      await page.getByAltText('Your photo preview').waitFor()
      await shot('preview')
      await page.locator('nav:visible').getByRole('link', { name: 'Feed', exact: true }).click()
      await page.getByRole('dialog', { name: 'Leave this moment?' }).waitFor()
      await shot('leave-dialog')
      await page.getByRole('button', { name: 'Leave capture' }).click()
      const response = await context.request.post('http://localhost:3000/api/auth/dev', { headers: { Origin: 'http://localhost:3000' }, data: { subject: `visual-${size}-${Date.now()}`, display_name: 'Typography review' } })
      assert.equal(response.status(), 200)
      await page.reload()
      await page.getByRole('heading', { name: 'Your season needs your people.' }).waitFor()
      await shot('no-group')
      await page.getByRole('button', { name: 'Create group', exact: true }).click()
      await shot('create-group')
      await page.getByRole('button', { name: 'Join with invite', exact: true }).click()
      await shot('join-group')
      let release
      const pending = new Promise(resolve => { release = resolve })
      const delayGroups = async route => { await pending; await route.continue() }
      await page.route('**/api/groups', delayGroups)
      await page.reload({ waitUntil: 'domcontentloaded' })
      await page.getByText('Opening your group…', { exact: true }).waitFor()
      await shot('loading')
      release()
      await page.unrouteAll({ behavior: 'wait' })
      await page.getByRole('heading', { name: 'Your season needs your people.' }).waitFor()
    }
    await page.route('**/api/groups', route => route.abort('failed'))
    await page.reload()
    await page.getByRole('button', { name: 'Try again' }).waitFor()
    await shot('error')
    await context.close()
    console.log(`${phase}: ${size} screenshots captured`)
  }
} finally { await browser.close() }
