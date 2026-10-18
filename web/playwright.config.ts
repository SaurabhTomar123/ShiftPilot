import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:3001', channel: 'chrome', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1600, height: 1050 } } },
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium', channel: 'chrome' } },
  ],
  webServer: { command: `node node_modules/next/dist/bin/next ${process.env.PLAYWRIGHT_SERVER_MODE === 'production' ? 'start' : 'dev'} --hostname 127.0.0.1 --port 3001`, url: 'http://127.0.0.1:3001', reuseExistingServer: true, timeout: 60000 },
});
