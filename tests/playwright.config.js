// Playwright 설정 (specs/11-e2e-testing.md)
import { defineConfig, devices } from '@playwright/test'

import { BACKEND_PORT, BACKEND_URL, FRONTEND_PORT, FRONTEND_URL } from './e2e/support/env.js'

const isCI = Boolean(process.env.CI)
// 서버 로그는 기본으로 숨긴다. 서버가 뜨지 않을 때 E2E_VERBOSE=1로 다시 실행한다
const serverOutput = process.env.E2E_VERBOSE ? 'pipe' : 'ignore'

export default defineConfig({
  testDir: './e2e',
  // 테스트마다 고유한 사번·부서코드·회차를 만들어 쓰므로 병렬 실행해도 서로 간섭하지 않는다
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 2 : undefined,
  timeout: 30_000,
  expect: { timeout: 7_000 },

  reporter: isCI
    ? [['list'], ['html', { open: 'never' }]]
    : [['list'], ['html', { open: 'on-failure' }]],

  use: {
    baseURL: FRONTEND_URL,
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      // Playwright 번들 Chromium. `npx playwright install chromium`만으로 준비된다 (sudo 불필요)
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // 실제 Google Chrome. `sudo npx playwright install chrome`로 설치해야 한다
      name: 'chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],

  webServer: [
    {
      command: './scripts/start-backend.sh',
      url: `${BACKEND_URL}/api/health/`,
      reuseExistingServer: !isCI,
      timeout: 120_000,
      stdout: serverOutput,
      stderr: serverOutput,
      env: { E2E_BACKEND_PORT: String(BACKEND_PORT) },
    },
    {
      command: `npm --prefix ../frontend run dev -- --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      url: FRONTEND_URL,
      reuseExistingServer: !isCI,
      timeout: 120_000,
      stdout: serverOutput,
      stderr: serverOutput,
      env: { VITE_API_PROXY_TARGET: BACKEND_URL },
    },
  ],
})
