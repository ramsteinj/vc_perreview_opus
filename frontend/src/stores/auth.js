import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as authApi from '@/api/auth'

const REFRESH_STORAGE_KEY = 'perreview.refresh'

function readStoredRefresh() {
  try {
    return localStorage.getItem(REFRESH_STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStoredRefresh(token) {
  try {
    if (token) localStorage.setItem(REFRESH_STORAGE_KEY, token)
    else localStorage.removeItem(REFRESH_STORAGE_KEY)
  } catch {
    // 프라이빗 모드 등에서 저장이 막혀도 세션은 메모리로 유지된다
  }
}

export const useAuthStore = defineStore('auth', () => {
  // access 토큰은 메모리에만 둔다 (specs/03-auth.md §2)
  const accessToken = ref(null)
  const refreshToken = ref(readStoredRefresh())
  const user = ref(null)
  const restoring = ref(false)
  const restored = ref(false)

  const isAuthenticated = computed(() => Boolean(accessToken.value && user.value))
  const isAdmin = computed(() => user.value?.role === 'ADMIN')
  const passwordIsDefault = computed(() => user.value?.password_is_default === true)

  function setSession({ access, refresh, user: profile }) {
    accessToken.value = access ?? accessToken.value
    if (refresh !== undefined) {
      refreshToken.value = refresh
      writeStoredRefresh(refresh)
    }
    if (profile !== undefined) {
      user.value = profile
    }
  }

  async function clearSession() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    writeStoredRefresh(null)
  }

  async function login(credentials) {
    const { data } = await authApi.login(credentials)
    setSession({ access: data.access, refresh: data.refresh, user: data.user })
    return data.user
  }

  async function refresh() {
    if (!refreshToken.value) throw new Error('NO_REFRESH_TOKEN')
    const { data } = await authApi.refreshToken(refreshToken.value)
    setSession({ access: data.access, refresh: data.refresh })
    return data.access
  }

  async function loadProfile() {
    const { data } = await authApi.fetchMe()
    user.value = data
    return data
  }

  /** 앱 부팅 시 저장된 refresh 토큰으로 세션을 복구한다. */
  async function restore() {
    if (restored.value || restoring.value) return
    restoring.value = true
    try {
      if (refreshToken.value) {
        await refresh()
        await loadProfile()
      }
    } catch {
      await clearSession()
    } finally {
      restoring.value = false
      restored.value = true
    }
  }

  async function logout() {
    const token = refreshToken.value
    try {
      if (token && accessToken.value) await authApi.logout(token)
    } catch {
      // 서버 폐기에 실패해도 클라이언트 세션은 반드시 정리한다
    } finally {
      await clearSession()
    }
  }

  return {
    accessToken,
    refreshToken,
    user,
    restoring,
    restored,
    isAuthenticated,
    isAdmin,
    passwordIsDefault,
    setSession,
    clearSession,
    login,
    refresh,
    loadProfile,
    restore,
    logout,
  }
})
