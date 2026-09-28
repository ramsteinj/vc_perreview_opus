// 로그인 · 세션 · 권한 (specs/03-auth.md, specs/04-employee-features.md FR-E-01)
import { expect, test, toast } from './support/fixtures.js'
import { ADMIN } from './support/data.js'

async function fillLogin(page, { name, employeeNo, password }) {
  await page.getByLabel('성명').fill(name)
  await page.getByLabel('사번').fill(employeeNo)
  await page.getByLabel('비밀번호', { exact: true }).fill(password)
  await page.getByRole('button', { name: '로그인' }).click()
}

test.describe('로그인', () => {
  test('기본 관리자 계정으로 로그인하면 대시보드로 이동한다', async ({ page }) => {
    await page.goto('/login')
    await fillLogin(page, ADMIN)

    await expect(page).toHaveURL(/\/admin\/dashboard$/)
    await expect(page.getByRole('heading', { name: '대시보드', level: 1 })).toBeVisible()
  })

  test('기본 비밀번호를 쓰는 관리자에게 변경 안내 배너가 보인다', async ({ page }) => {
    await page.goto('/login')
    await fillLogin(page, ADMIN)

    await expect(page.getByText('기본 비밀번호를 사용 중입니다.')).toBeVisible()
  })

  test('직원은 로그인하면 내 평가 화면으로 이동한다', async ({ page, api }) => {
    const user = await api.createUser()

    await page.goto('/login')
    await fillLogin(page, user)

    await expect(page).toHaveURL(/\/my\/evaluations$/)
    await expect(page.getByRole('heading', { name: '내 평가', level: 1 })).toBeVisible()
  })

  test('성명이 다르면 사번·비밀번호가 맞아도 로그인되지 않는다', async ({ page, api }) => {
    const user = await api.createUser()

    await page.goto('/login')
    await fillLogin(page, { ...user, name: '다른이름' })

    await expect(page.getByRole('alert')).toContainText('성명, 사번 또는 비밀번호가 올바르지 않습니다.')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('실패 사유를 구분하지 않는다 (사용자 열거 방지)', async ({ page, api }) => {
    const user = await api.createUser()
    const cases = [
      { ...user, name: '다른이름' },
      { ...user, password: 'wrong-password-123' },
      { ...user, employeeNo: 'NO-SUCH-USER' },
    ]

    const messages = []
    for (const credentials of cases) {
      await page.goto('/login')
      await fillLogin(page, credentials)
      messages.push(await page.getByRole('alert').textContent())
    }

    expect(new Set(messages.map((m) => m.trim())).size).toBe(1)
  })

  test('빈 칸으로 제출하면 필드별 안내가 나온다', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: '로그인' }).click()

    await expect(page.getByText('성명을 입력하세요.')).toBeVisible()
    await expect(page.getByText('사번을 입력하세요.')).toBeVisible()
    await expect(page.getByText('비밀번호를 입력하세요.')).toBeVisible()
  })

  test('비밀번호 표시 토글이 동작한다', async ({ page }) => {
    await page.goto('/login')
    const input = page.getByLabel('비밀번호', { exact: true })

    await expect(input).toHaveAttribute('type', 'password')
    await page.getByRole('button', { name: '비밀번호 표시' }).click()
    await expect(input).toHaveAttribute('type', 'text')
  })
})

test.describe('세션', () => {
  test('새로고침해도 로그인 상태가 유지된다', async ({ page }) => {
    await page.goto('/login')
    await fillLogin(page, ADMIN)
    await expect(page).toHaveURL(/\/admin\/dashboard$/)

    await page.reload()

    await expect(page).toHaveURL(/\/admin\/dashboard$/)
    await expect(page.getByRole('heading', { name: '대시보드', level: 1 })).toBeVisible()
  })

  test('로그인하지 않고 보호된 경로로 가면 로그인 화면으로 보내고, 로그인 후 원래 경로로 돌아간다', async ({ page }) => {
    await page.goto('/admin/users')

    await expect(page).toHaveURL(/\/login\?next=/)
    await fillLogin(page, ADMIN)

    await expect(page).toHaveURL(/\/admin\/users$/)
  })

  test('로그아웃하면 로그인 화면으로 가고 새로고침해도 복구되지 않는다', async ({ page }) => {
    await page.goto('/login')
    await fillLogin(page, ADMIN)
    await expect(page).toHaveURL(/\/admin\/dashboard$/)

    await page.getByRole('button', { name: /ADMIN/ }).click()
    await page.getByRole('button', { name: '로그아웃' }).click()

    await expect(page).toHaveURL(/\/login$/)
    await expect(toast(page, '로그아웃되었습니다.')).toBeVisible()

    await page.goto('/admin/dashboard')
    await expect(page).toHaveURL(/\/login/)
  })
})

test.describe('권한', () => {
  test('직원이 관리자 화면에 접근하면 403 화면이 나온다', async ({ page, api, loginAs }) => {
    const user = await api.createUser()
    await loginAs(user, '/admin/users')

    await expect(page).toHaveURL(/\/403$/)
    await expect(page.getByText('접근 권한이 없습니다')).toBeVisible()
  })

  test('직원 내비게이션에는 관리자 메뉴가 없다', async ({ page, api, loginAs }) => {
    const user = await api.createUser()
    await loginAs(user, '/my/evaluations')

    await expect(page.getByRole('link', { name: /내 평가/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /사용자/ })).toHaveCount(0)
  })

  test('비밀번호를 변경하면 새 비밀번호로만 로그인된다', async ({ page, api, loginAs }) => {
    const user = await api.createUser()
    const next = `${user.password}X`
    await loginAs(user, '/account/password')

    await page.getByLabel('현재 비밀번호').fill(user.password)
    await page.getByLabel('새 비밀번호', { exact: true }).fill(next)
    await page.getByLabel('새 비밀번호 확인').fill(next)
    await page.getByRole('button', { name: '변경하기' }).click()

    await expect(toast(page, '비밀번호가 변경되었습니다.')).toBeVisible()

    const oldLogin = await api.context.post('auth/login/', {
      data: { name: user.name, employee_no: user.employeeNo, password: user.password },
    })
    expect(oldLogin.status()).toBe(401)
    await api.login({ ...user, password: next })
  })
})
