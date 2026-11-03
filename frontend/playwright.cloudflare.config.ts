// Only the read-only readiness scenarios may target the hosted production origin.
import { defineConfig } from '@playwright/test'
import local from './playwright.config'
export default defineConfig({
  ...local,
  testMatch: 'readiness.spec.ts',
  use: { ...local.use, baseURL: 'https://mustaaaaaard-27.eeyramagbetor.workers.dev' },
})
