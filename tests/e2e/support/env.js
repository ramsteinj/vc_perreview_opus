// E2E 서버 주소. playwright.config.js와 테스트 코드가 함께 쓴다.
export const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8001)
export const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 5174)

export const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`
export const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`
