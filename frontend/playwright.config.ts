// The end-to-end flow (e2e/): a real browser against a running app, by default docker compose on :8080
// (make docker-run, with the demo account seeded: make userdb); BASE_URL=https://... for the live site.
//
//   npm run e2e
//
// It uses the installed Microsoft Edge (channel msedge), so no browser download is needed.
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8080',
    channel: 'msedge',
    trace: 'retain-on-failure',
  },
})
