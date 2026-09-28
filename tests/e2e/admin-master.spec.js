// 부서 · 사용자 관리 (specs/05-admin-features.md FR-A-02, FR-A-03)
import { uid } from './support/data.js'
import { dialog, expect, test, toast } from './support/fixtures.js'

/** 첫 번째 칸에 주어진 텍스트가 있는 행. 다른 칸의 select option 텍스트에 걸리지 않게 한다 */
function rowByFirstCell(page, text) {
  return page.locator('tbody tr').filter({ has: page.locator('td:first-child', { hasText: text }) })
}

test.describe('부서 관리', () => {
  test('부서를 만들고 하위 부서를 붙이면 트리로 표시된다', async ({ page, loginAs }) => {
    const code = `P${uid()}`
    const childCode = `C${uid()}`
    await loginAs(undefined, '/admin/departments')

    await page.getByRole('button', { name: '+ 부서 추가' }).click()
    const create = dialog(page, '부서 추가')
    await create.getByLabel('부서코드').fill(code)
    await create.getByLabel('부서명').fill(`본부${code}`)
    await create.getByRole('button', { name: '저장' }).click()
    await expect(toast(page, '부서를 생성했습니다.')).toBeVisible()

    const parentRow = page.locator('tbody tr').filter({ hasText: code })
    await parentRow.getByRole('button', { name: '하위 추가' }).click()

    const child = dialog(page, '부서 추가')
    // 하위 추가로 열면 상위 부서가 미리 선택되어 있어야 한다
    await expect(child.getByLabel('상위 부서')).toHaveValue(/\d+/)
    await child.getByLabel('부서코드').fill(childCode)
    await child.getByLabel('부서명').fill(`팀${childCode}`)
    await child.getByRole('button', { name: '저장' }).click()
    await expect(toast(page, '부서를 생성했습니다.')).toBeVisible()

    const childRow = page.locator('tbody tr').filter({ hasText: childCode })
    await expect(childRow).toContainText('└')
  })

  test('상위 부서 선택지에 자기 자신과 자손이 나오지 않는다 (순환 방지)', async ({ page, api, loginAs }) => {
    const parent = await api.createDepartment()
    const child = await api.createDepartment({ parent: parent.id })
    await loginAs(undefined, '/admin/departments')

    await page.locator('tbody tr').filter({ hasText: parent.code }).getByRole('button', { name: '수정' }).click()

    const options = dialog(page, '부서 수정').getByLabel('상위 부서').locator('option')
    await expect(options.filter({ hasText: `(${parent.code})` })).toHaveCount(0)
    await expect(options.filter({ hasText: `(${child.code})` })).toHaveCount(0)
  })

  test('소속 직원이 있는 부서는 완전 삭제를 고를 수 없다', async ({ page, api, loginAs }) => {
    const department = await api.createDepartment()
    await api.createUser({ department: department.id })
    await loginAs(undefined, '/admin/departments')

    await page.locator('tbody tr').filter({ hasText: department.code }).getByRole('button', { name: '삭제' }).click()

    const modal = dialog(page, '부서 삭제')
    await expect(modal.getByLabel(/완전 삭제/)).toBeDisabled()
    await modal.getByRole('button', { name: '진행' }).click()

    await expect(toast(page, '부서를 비활성화했습니다.')).toBeVisible()
    await expect(page.locator('tbody tr').filter({ hasText: department.code })).toContainText('비활성')
  })
})

test.describe('사용자 관리', () => {
  test('비밀번호를 비워 두면 임시 비밀번호가 발급되고 그 비밀번호로 로그인된다', async ({ page, api, loginAs }) => {
    const employeeNo = `N${uid()}`
    const name = `신입${employeeNo.slice(-4)}`
    await loginAs(undefined, '/admin/users')

    await page.getByRole('button', { name: '+ 사용자 추가' }).click()
    const modal = dialog(page, '사용자 추가')
    await modal.getByLabel('사번').fill(employeeNo)
    await modal.getByLabel('성명').fill(name)
    await modal.getByRole('button', { name: '저장' }).click()

    const credential = dialog(page, '임시 비밀번호가 발급되었습니다')
    await expect(credential).toContainText(employeeNo)
    const password = (await credential.locator('code').textContent()).trim()
    await credential.getByRole('button', { name: '확인했습니다' }).click()

    await api.login({ name, employeeNo, password })
  })

  test('중복 사번으로 추가하면 모달에 오류가 표시된다', async ({ page, api, loginAs }) => {
    const existing = await api.createUser()
    await loginAs(undefined, '/admin/users')

    await page.getByRole('button', { name: '+ 사용자 추가' }).click()
    const modal = dialog(page, '사용자 추가')
    await modal.getByLabel('사번').fill(existing.employeeNo)
    await modal.getByLabel('성명').fill('중복시도')
    await modal.getByRole('button', { name: '저장' }).click()

    await expect(modal.locator('.alert-danger')).toBeVisible()
    await expect(modal).toBeVisible()
  })

  test('사번으로 검색하면 해당 사용자만 남는다', async ({ page, api, loginAs }) => {
    const user = await api.createUser()
    await loginAs(undefined, '/admin/users')

    await page.getByLabel('검색 (사번 · 성명)').fill(user.employeeNo)

    await expect(page.locator('tbody tr')).toHaveCount(1)
    await expect(rowByFirstCell(page, user.employeeNo)).toBeVisible()
  })

  test('비활성화한 사용자는 로그인할 수 없다', async ({ page, api, loginAs }) => {
    const user = await api.createUser()
    await loginAs(undefined, '/admin/users')
    await page.getByLabel('검색 (사번 · 성명)').fill(user.employeeNo)

    const row = rowByFirstCell(page, user.employeeNo)
    await row.getByRole('button', { name: '비활성화' }).click()
    await dialog(page, '사용자 비활성화').getByRole('button', { name: '비활성화' }).click()

    await expect(toast(page, '사용자를 비활성화했습니다.')).toBeVisible()
    await expect(row).toContainText('비활성')

    const res = await api.context.post('auth/login/', {
      data: { name: user.name, employee_no: user.employeeNo, password: user.password },
    })
    expect(res.status()).toBe(401)
  })

  test('관리자 본인 행의 비활성화 버튼은 눌리지 않는다', async ({ page, loginAs }) => {
    await loginAs(undefined, '/admin/users')
    await page.getByLabel('검색 (사번 · 성명)').fill('ADMIN')

    await expect(rowByFirstCell(page, 'ADMIN').getByRole('button', { name: '비활성화' })).toBeDisabled()
  })
})

test.describe('CSV 일괄 등록', () => {
  const header = 'employee_no,name,department_code,position,role,hired_on'

  function csvFile(rows) {
    return {
      name: 'users.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(`﻿${[header, ...rows].join('\r\n')}\r\n`, 'utf-8'),
    }
  }

  test('정상 파일을 올리면 전원이 등록되고 임시 비밀번호가 표시된다', async ({ page, api, loginAs }) => {
    const department = await api.createDepartment()
    const numbers = [`B${uid()}`, `B${uid()}`]
    await loginAs(undefined, '/admin/users')

    await page.getByRole('button', { name: 'CSV 일괄 등록' }).click()
    const modal = dialog(page, '사용자 CSV 일괄 등록')
    await modal.getByLabel('CSV 파일').setInputFiles(
      csvFile([
        `${numbers[0]},"김,철수",${department.code},선임,EMPLOYEE,2026-01-01`,
        `${numbers[1]},이영희,,,,`,
      ])
    )
    await modal.getByRole('button', { name: '등록' }).click()

    await expect(modal).toContainText('2명을 등록했습니다.')
    const passwordCell = modal.locator('tbody tr').filter({ hasText: numbers[0] }).locator('code').last()
    const password = (await passwordCell.textContent()).trim()

    await api.login({ name: '김,철수', employeeNo: numbers[0], password })
  })

  test('오류가 한 행이라도 있으면 아무도 등록되지 않고 행별 사유가 표시된다', async ({ page, api, loginAs }) => {
    const valid = `V${uid()}`
    await loginAs(undefined, '/admin/users')

    await page.getByRole('button', { name: 'CSV 일괄 등록' }).click()
    const modal = dialog(page, '사용자 CSV 일괄 등록')
    await modal.getByLabel('CSV 파일').setInputFiles(
      csvFile([`${valid},정상행,,,,`, `R${uid()},,NOPE,,BAD,2026-13-01`])
    )
    await modal.getByRole('button', { name: '등록' }).click()

    await expect(modal).toContainText('등록된 사용자는 없습니다.')
    // 모달에는 컬럼 안내 표도 있으므로 '사유' 열이 있는 오류 표로 좁힌다
    const errorTable = modal.locator('table', { has: page.getByRole('columnheader', { name: '사유' }) })
    const errors = errorTable.locator('tbody tr')
    await expect(errors).toHaveCount(4)
    await expect(errors.first()).toContainText('3')

    const { body } = await api.call('GET', `admin/users/?search=${valid}`)
    expect(body.count).toBe(0)
  })
})
