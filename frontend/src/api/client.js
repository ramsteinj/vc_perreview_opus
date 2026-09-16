import axios from 'axios'

import { useAuthStore } from '@/stores/auth'

const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// 동시 다발 401을 하나의 refresh 요청으로 합류시킨다
let refreshPromise = null

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error

    if (!response || response.status !== 401 || config?._retried) {
      return Promise.reject(error)
    }

    // refresh 요청 자체가 401이면 재시도하지 않는다 (무한 루프 방지)
    if (config.url?.includes('/auth/refresh/') || config.url?.includes('/auth/login/')) {
      return Promise.reject(error)
    }

    const auth = useAuthStore()
    if (!auth.refreshToken) {
      return Promise.reject(error)
    }

    config._retried = true

    try {
      refreshPromise = refreshPromise || auth.refresh()
      await refreshPromise
      refreshPromise = null
    } catch (refreshError) {
      refreshPromise = null
      await auth.clearSession()
      return Promise.reject(refreshError)
    }

    config.headers.Authorization = `Bearer ${auth.accessToken}`
    return client(config)
  }
)

/** 서버 오류 응답에서 사용자에게 보여줄 메시지를 뽑아낸다. */
export function extractErrorMessage(error, fallback = '일시적인 오류입니다. 다시 시도해 주세요.') {
  const data = error?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return fallback
  if (data.detail) return data.detail
  if (data.fields) {
    const first = Object.values(data.fields)[0]
    if (Array.isArray(first)) return first[0]
    if (typeof first === 'string') return first
  }
  return fallback
}

export function extractErrorCode(error) {
  return error?.response?.data?.code ?? null
}

export default client
