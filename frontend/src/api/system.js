import client from './client'

/**
 * 잠든 백엔드를 미리 깨운다.
 *
 * Render 무료 플랜의 웹 서비스는 15분 무활동 시 잠들고 깨는 데 약 1분이 걸린다.
 * 로그인 화면이 열리자마자 요청을 보내 두면 사용자가 입력하는 동안 서버가 깨어난다.
 * 결과는 기다리지 않으며 실패해도 무시한다.
 */
export function wakeServer() {
  client.get('/health/').catch(() => {})
}
