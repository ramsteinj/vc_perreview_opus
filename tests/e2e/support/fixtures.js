// 공용 fixture.
//
//   api      : 테스트 데이터 준비용 API 클라이언트
//   loginAs  : UI 로그인 절차 없이 특정 사용자로 로그인된 상태를 만든다
//
// 로그인 흐름 자체를 검증하는 auth.spec.js는 UI로 로그인하고,
// 나머지 스펙은 loginAs로 준비 시간을 줄인다.
import { test as base, expect } from '@playwright/test'

import { Api } from './api.js'
import { ADMIN } from './data.js'

const REFRESH_KEY = 'perreview.refresh'

export const test = base.extend({
  api: async ({}, use) => {
    const api = await Api.create()
    await use(api)
    await api.dispose()
  },

  loginAs: async ({ page, api }, use) => {
    /**
     * refresh 토큰을 localStorage에 심고 이동한다. 앱은 부팅 시 이 토큰으로
     * 세션을 복구한다 (stores/auth.js restore).
     *
     * 토큰은 addInitScript로 앱이 부팅되기 **전에** 심는다. 이미 열린 페이지에서
     * page.evaluate로 심으면, 그 페이지의 앱이 부팅 중 refresh를 회전시키며
     * 새 토큰을 늦게 써서 방금 심은 토큰을 덮어쓰는 경쟁이 생긴다
     * (같은 테스트에서 사용자를 바꿀 때 병렬 부하에서만 드러났다).
     *
     * 단, init script는 매 탐색마다 실행되므로 그대로 두면 새로고침할 때
     * 이미 회전·폐기된 옛 토큰으로 되돌린다. sessionStorage 플래그로 1회만 심는다.
     */
    await use(async (user = ADMIN, path = '/') => {
      const { refresh } = await api.login(user)
      const flag = `e2e-login:${refresh.slice(-24)}`
      await page.addInitScript(
        ([key, token, marker]) => {
          if (sessionStorage.getItem(marker)) return
          localStorage.setItem(key, token)
          sessionStorage.setItem(marker, '1')
        },
        [REFRESH_KEY, refresh, flag]
      )
      await page.goto(path)
    })
  },
})

export { expect }

/** 우측 상단 토스트 중 주어진 문구를 포함한 것 */
export function toast(page, text) {
  return page.locator('.toast-host .toast').filter({ hasText: text })
}

/** 열려 있는 모달 */
export function dialog(page, title) {
  const modal = page.getByRole('dialog')
  return title ? modal.filter({ has: page.getByRole('heading', { name: title }) }) : modal
}
