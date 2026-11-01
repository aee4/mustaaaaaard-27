import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'
export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1, timeout: 90000,
  expect: { timeout: 15000 },
  use: { baseURL: 'http://localhost:3000', viewport: { width: 390, height: 844 },
    launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', `--use-file-for-fake-video-capture=${resolve('../.tools/frontend-camera.y4m')}`] },
    channel: process.env.PW_BROWSER_CHANNEL === 'chromium' ? undefined : 'chrome', screenshot: 'only-on-failure', trace: 'off', video: 'off',
  },
  reporter: 'list',
})
