// 응답 현황 모니터링 · 반려 (specs/05-admin-features.md FR-A-06)
import { dialog, expect, test, toast } from './support/fixtures.js'

/**
 * 1차 평가자는 제출, 2차 평가자는 미시작인 회차.
 * 기대 응답 2건 중 제출 1건 → 제출률 50%.
 */
async function seedHalfSubmitted(api) {
  const seed = await api.seedOpenEvaluation({ secondary: true })
  const responseId = await api.submitSheet(seed.evaluator, seed.assignment.id, [4, 5, 3])
  return { ...seed, responseId }
}

test('요약 탭은 미시작 건을 분모에 포함한 제출률을 보여준다', async ({ page, api, loginAs }) => {
  const { cycle } = await seedHalfSubmitted(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/status`)

  await expect(page.getByRole('img', { name: '전체 제출률 50퍼센트' })).toBeVisible()
  await expect(page.getByText('제출 1 / 기대 2건')).toBeVisible()
})

test('부서별 제출률은 평가자 소속 부서 기준으로 집계된다', async ({ page, api, loginAs }) => {
  const { cycle, department } = await seedHalfSubmitted(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/status`)

  const row = page.locator('tbody tr').filter({ hasText: department.name })
  // 1차·2차 평가자 모두 같은 부서 → 기대 2, 미시작 1, 제출 1
  await expect(row.locator('td').nth(1)).toHaveText('2')
  await expect(row.locator('td').nth(2)).toHaveText('1')
  await expect(row.locator('td').nth(4)).toHaveText('1')
})

test('미응답자 탭에 아직 시작하지 않은 평가자가 나온다', async ({ page, api, loginAs }) => {
  const { cycle, secondary, evaluator, target } = await seedHalfSubmitted(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/status`)

  await page.getByRole('button', { name: /^미응답자/ }).click()

  const group = page.locator('.list-group-item').filter({ hasText: secondary.name })
  await expect(group).toContainText('미시작 1')
  await expect(page.locator('.list-group-item').filter({ hasText: evaluator.name })).toHaveCount(0)

  await group.getByRole('button', { name: '대상 보기' }).click()
  await expect(group.locator('tbody tr').filter({ hasText: target.name })).toContainText('2차')
})

test('상세 탭에서 상태 필터를 적용하면 해당 행만 남는다', async ({ page, api, loginAs }) => {
  const { cycle, secondary } = await seedHalfSubmitted(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/status`)

  await page.getByRole('button', { name: '상세' }).click()
  await expect(page.locator('tbody tr')).toHaveCount(2)

  await page.getByLabel('상태', { exact: true }).selectOption('NOT_STARTED')

  await expect(page.locator('tbody tr')).toHaveCount(1)
  await expect(page.locator('tbody tr')).toContainText(secondary.name)
})

test('제출된 평가지를 열람할 수 있다', async ({ page, api, loginAs }) => {
  const { cycle, evaluator } = await seedHalfSubmitted(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/status`)

  await page.getByRole('button', { name: '상세' }).click()
  const row = page.locator('tbody tr').filter({ hasText: '제출완료' })
  await row.getByRole('button', { name: '보기' }).click()

  const modal = dialog(page, '평가지 열람')
  await expect(modal).toContainText(evaluator.name)
  await expect(modal).toContainText('4 / 5')
  await expect(modal).toContainText('3/3 응답')
})

test('반려하면 평가자가 다시 수정할 수 있게 된다', async ({ page, api, loginAs }) => {
  const { cycle, evaluator, target } = await seedHalfSubmitted(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/status`)

  await page.getByRole('button', { name: '상세' }).click()
  await page.locator('tbody tr').filter({ hasText: '제출완료' }).getByRole('button', { name: '반려' }).click()

  const modal = dialog(page, '평가지 반려')
  await modal.getByLabel('반려 사유 (선택)').fill('평가 기준 재안내')
  await modal.getByRole('button', { name: '반려' }).click()
  await expect(toast(page, '평가지를 반려했습니다.')).toBeVisible()

  // 평가자 화면에서 다시 작성 가능 상태가 된다
  await loginAs(evaluator, '/my/evaluations')
  const row = page.locator('tbody tr').filter({ hasText: target.name })
  await expect(row).toContainText('임시저장')
  await row.getByRole('button', { name: '이어서 작성' }).click()
  await expect(page.getByRole('button', { name: '제출하기' })).toBeEnabled()
})

test('상세 탭에서 응답상세 CSV를 내려받는다', async ({ page, api, loginAs }) => {
  const { cycle } = await seedHalfSubmitted(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/status`)
  await page.getByRole('button', { name: '상세' }).click()

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: '응답상세 CSV' }).click(),
  ])

  expect(download.suggestedFilename()).toMatch(/_응답상세_\d{8}\.csv$/)
})
