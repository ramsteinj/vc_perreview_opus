// 평가 회차 · 항목 · 가중치 · 평가자 배정 (specs/05-admin-features.md FR-A-04, 05, 10)
import { isoDate, uid } from './support/data.js'
import { dialog, expect, test, toast } from './support/fixtures.js'

function rowByFirstCell(page, text) {
  return page.locator('tbody tr').filter({ has: page.locator('td:first-child', { hasText: text }) })
}

async function addItem(page, { code, title, weight }) {
  await page.getByRole('button', { name: '+ 항목 추가' }).click()
  const modal = dialog(page, '평가 항목 추가')
  await modal.getByLabel('코드').fill(code)
  await modal.getByLabel('문항').fill(title)
  await modal.getByLabel('가중치 (%)').fill(String(weight))
  await modal.getByRole('button', { name: '저장' }).click()
  await expect(toast(page, '항목을 추가했습니다.').last()).toBeVisible()
}

test('회차를 만든다', async ({ page, loginAs }) => {
  const name = `E2E 회차 ${uid()}`
  await loginAs(undefined, '/admin/cycles')

  await page.getByRole('button', { name: '+ 회차 추가' }).click()
  const modal = dialog(page, '평가 회차 추가')
  await modal.getByLabel('회차명').fill(name)
  await modal.getByLabel('응답 시작일').fill(isoDate(0))
  await modal.getByLabel('응답 마감일').fill(isoDate(30))
  await modal.getByRole('button', { name: '저장' }).click()

  await expect(toast(page, '회차를 생성했습니다.')).toBeVisible()
  await expect(rowByFirstCell(page, name)).toContainText('준비중')
})

test('가중치 합계가 100이 아니면 경고가 보이고 회차를 열 수 없다', async ({ page, api, loginAs }) => {
  const cycle = await api.createCycle()
  await loginAs(undefined, `/admin/cycles/${cycle.id}/items`)

  await addItem(page, { code: 'PERF', title: '업무 성과', weight: 50 })
  await addItem(page, { code: 'COLLAB', title: '협업', weight: 30 })

  await expect(page.locator('.card-footer .badge')).toContainText('80.00%')
  await expect(page.getByText('합계가 100%가 아니면 이 회차를 열 수 없습니다.')).toBeVisible()

  await page.goto('/admin/cycles')
  await rowByFirstCell(page, cycle.name).getByRole('button', { name: '열기' }).click()

  await expect(toast(page, '가중치 합계가 100이 아닙니다')).toContainText('80.00%')
  await expect(rowByFirstCell(page, cycle.name)).toContainText('준비중')
})

test('가중치를 100으로 맞추면 합계 배지가 정상으로 바뀐다', async ({ page, api, loginAs }) => {
  const cycle = await api.createCycle()
  await loginAs(undefined, `/admin/cycles/${cycle.id}/items`)

  await addItem(page, { code: 'PERF', title: '업무 성과', weight: 50 })
  await addItem(page, { code: 'COLLAB', title: '협업', weight: 30 })
  await addItem(page, { code: 'ATT', title: '태도', weight: 20 })

  await expect(page.locator('.card-footer .badge')).toContainText('100.00% ✓')
  await expect(page.getByText('합계가 100%가 아니면')).toHaveCount(0)
})

test('2차 평가자 없이 1차 평가자만 배정할 수 있다', async ({ page, api, loginAs }) => {
  const department = await api.createDepartment()
  const evaluator = await api.createUser({ department: department.id })
  const target = await api.createUser({ department: department.id })
  const cycle = await api.createCycle()
  await loginAs(undefined, `/admin/cycles/${cycle.id}/assignments`)

  await page.getByLabel('검색').fill(target.employeeNo)
  const row = rowByFirstCell(page, target.employeeNo)
  await expect(row).toContainText('미배정')

  await row.locator('select').first().selectOption(String(evaluator.id))
  await row.getByRole('button', { name: '저장' }).click()

  await expect(toast(page, '배정을 저장했습니다.')).toBeVisible()
  await expect(row).not.toContainText('미배정')
  await expect(row.locator('select').nth(1)).toHaveValue('')
})

test('평가자 선택지에 피평가자 본인은 나오지 않는다', async ({ page, api, loginAs }) => {
  const target = await api.createUser()
  const cycle = await api.createCycle()
  await loginAs(undefined, `/admin/cycles/${cycle.id}/assignments`)

  await page.getByLabel('검색').fill(target.employeeNo)
  const row = rowByFirstCell(page, target.employeeNo)
  const primary = row.locator('select').first()

  await expect(primary.locator(`option[value="${target.id}"]`)).toHaveCount(0)
})

test('미배정 대상이 있으면 확인을 받은 뒤 회차가 열린다', async ({ page, api, loginAs }) => {
  const cycle = await api.createCycle()
  await api.createStandardItems(cycle.id)
  await loginAs(undefined, '/admin/cycles')

  await rowByFirstCell(page, cycle.name).getByRole('button', { name: '열기' }).click()

  const confirm = dialog(page, '미배정 대상이 있습니다')
  await expect(confirm).toContainText('미배정 직원')
  await confirm.getByRole('button', { name: '진행' }).click()

  await expect(toast(page, '회차를 열었습니다.')).toBeVisible()
  await expect(rowByFirstCell(page, cycle.name)).toContainText('진행중')
})
