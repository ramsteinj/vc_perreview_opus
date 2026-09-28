// 테스트마다 겹치지 않는 식별자를 만든다.
// 병렬 워커와 반복 실행에서 사번·부서코드·회차명이 충돌하지 않게 하기 위함이다.

let counter = 0

export function uid() {
  counter += 1
  const time = Date.now().toString(36).slice(-5)
  const rand = Math.random().toString(36).slice(2, 5)
  return `${time}${rand}${counter}`.toUpperCase()
}

export function isoDate(offsetDays = 0) {
  const date = new Date()
  date.setDate(date.getDate() + offsetDays)
  return date.toISOString().slice(0, 10)
}

/** Django 비밀번호 검증기(10자 이상, 흔하지 않음, 숫자만 아님)를 통과하는 값 */
export function password(seed = uid()) {
  return `E2e!Pw${seed}`
}

export const ADMIN = { name: 'ADMIN', employeeNo: 'ADMIN', password: 'admin1234!' }
