const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  testIgnore: [
    '**/tests/dashboard.bootstrap.spec.js',
    '**/tests/dashboard.owner-pool.spec.js',
    '**/tests/test-entrypoints.spec.js',
    '**/tests/wealth-model.spec.js',
    '**/tests/wealth-workbook.spec.mjs',
  ],
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: false,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1440, height: 2200 },
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:4173/?tab=s10',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
