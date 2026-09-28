// 직원 평가 응답 (specs/04-employee-features.md FR-E-02 ~ FR-E-06)
import { dialog, expect, test, toast } from './support/fixtures.js'

/** 문항 카드의 점수 버튼 그룹 (role=group, aria-label="<문항> 점수") */
function scoreGroup(page, title) {
  return page.getByRole('group', { name: `${title} 점수` })
}

/** 점수 선택. btn-check 라디오는 시각적으로 숨겨져 있어 label을 누른다 */
async function pickScore(page, title, score) {
  await scoreGroup(page, title).locator('label').nth(score - 1).click()
}

async function expectScore(page, title, score) {
  await expect(scoreGroup(page, title).locator('input[type=radio]').nth(score - 1)).toBeChecked()
}

async function openForm(page, loginAs, evaluator) {
  await loginAs(evaluator, '/my/evaluations')
  await page.getByRole('button', { name: /평가하기|이어서 작성/ }).click()
  await expect(page).toHaveURL(/\/my\/evaluations\/\d+$/)
}

test.describe('내 평가 목록', () => {
  test('배정된 대상이 미시작 상태로 보인다', async ({ page, api, loginAs }) => {
    const { evaluator, target } = await api.seedOpenEvaluation()
    await loginAs(evaluator, '/my/evaluations')

    const row = page.locator('tbody tr').filter({ hasText: target.name })
    await expect(row).toContainText('미시작')
    await expect(row).toContainText('0% (0/3)')
    await expect(row.getByRole('button', { name: '평가하기' })).toBeVisible()
  })

  test('배정이 없으면 진행 중인 평가가 없다는 안내가 나온다', async ({ page, api, loginAs }) => {
    const user = await api.createUser()
    await loginAs(user, '/my/evaluations')

    await expect(page.getByText('진행 중인 평가가 없습니다')).toBeVisible()
  })
})

test.describe('평가지 작성', () => {
  test('문항마다 가중치가 표시된다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await expect(page.getByText('가중치 50%')).toBeVisible()
    await expect(page.getByText('가중치 30%')).toBeVisible()
    await expect(page.getByText('가중치 20%')).toBeVisible()
  })

  test('점수를 고르면 진행률이 즉시 바뀐다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await expect(page.getByText('0% (0/3)')).toBeVisible()
    await pickScore(page, '업무 성과', 4)
    await expect(page.getByText('33% (1/3)')).toBeVisible()
    await pickScore(page, '협업', 5)
    await expect(page.getByText('66% (2/3)')).toBeVisible()
  })

  test('임시 저장 후 새로고침하면 입력이 복원된다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await pickScore(page, '업무 성과', 4)
    await page.getByLabel('의견 (선택)').first().fill('목표 초과 달성')
    await page.getByLabel('종합 의견 (선택)').fill('전반적으로 우수')
    await page.getByRole('button', { name: '임시 저장' }).click()
    await expect(toast(page, '임시 저장되었습니다.')).toBeVisible()

    await page.reload()

    await expectScore(page, '업무 성과', 4)
    await expect(page.getByLabel('의견 (선택)').first()).toHaveValue('목표 초과 달성')
    await expect(page.getByLabel('종합 의견 (선택)')).toHaveValue('전반적으로 우수')
    await expect(page.getByText('33% (1/3)')).toBeVisible()
  })

  test('버튼을 누르지 않아도 입력 3초 뒤 자동 저장된다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await pickScore(page, '태도', 3)
    await expect(page.getByText('저장되지 않은 변경')).toBeVisible()
    await expect(page.getByText(/마지막 저장: /)).toBeVisible({ timeout: 8_000 })

    await page.reload()
    await expectScore(page, '태도', 3)
  })

  test('같은 점수를 다시 누르면 선택이 해제된다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await pickScore(page, '업무 성과', 4)
    await expect(page.getByText('33% (1/3)')).toBeVisible()
    await pickScore(page, '업무 성과', 4)
    await expect(page.getByText('0% (0/3)')).toBeVisible()
  })

  test('저장하지 않은 변경이 있으면 페이지를 떠날 때 확인을 받는다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await pickScore(page, '업무 성과', 2)

    let asked = ''
    page.once('dialog', async (message) => {
      asked = message.message()
      await message.dismiss()
    })
    await page.getByRole('link', { name: '← 내 평가 목록' }).click()

    expect(asked).toContain('저장되지 않은 변경이 있습니다')
    await expect(page).toHaveURL(/\/my\/evaluations\/\d+$/)
  })
})

test.describe('제출', () => {
  test('미입력 항목이 있으면 제출이 막히고 해당 문항이 표시된다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await pickScore(page, '업무 성과', 4)
    await page.getByRole('button', { name: '제출하기' }).click()

    await expect(toast(page, '응답하지 않은 항목이 있습니다.')).toBeVisible()
    await expect(page.getByText('점수를 선택하세요.')).toHaveCount(2)
    await expect(dialog(page, '평가 제출')).toHaveCount(0)
  })

  test('모두 입력하고 제출하면 목록에서 제출완료가 되고 읽기 전용으로 열린다', async ({ page, api, loginAs }) => {
    const { evaluator, target } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await pickScore(page, '업무 성과', 4)
    await pickScore(page, '협업', 5)
    await pickScore(page, '태도', 3)
    await page.getByRole('button', { name: '제출하기' }).click()

    const confirm = dialog(page, '평가 제출')
    await expect(confirm).toContainText('제출 후에는 수정할 수 없습니다.')
    await confirm.getByRole('button', { name: '제출' }).click()

    await expect(page).toHaveURL(/\/my\/evaluations$/)
    await expect(toast(page, '평가를 제출했습니다.')).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: target.name })
    await expect(row).toContainText('제출완료')
    await row.getByRole('button', { name: '보기' }).click()

    await expect(page.getByText('제출이 완료된 평가입니다.')).toBeVisible()
    await expect(scoreGroup(page, '업무 성과').locator('input[type=radio]').first()).toBeDisabled()
    await expect(page.getByRole('button', { name: '제출하기' })).toHaveCount(0)
  })

  test('제출 확인 버튼을 연달아 눌러도 한 번만 제출된다', async ({ page, api, loginAs }) => {
    const { evaluator } = await api.seedOpenEvaluation()
    await openForm(page, loginAs, evaluator)

    await pickScore(page, '업무 성과', 4)
    await pickScore(page, '협업', 4)
    await pickScore(page, '태도', 4)
    await page.getByRole('button', { name: '제출하기' }).click()

    const submitResponses = []
    page.on('response', (res) => {
      if (res.url().includes('/submit/')) submitResponses.push(res.status())
    })
    await dialog(page, '평가 제출').getByRole('button', { name: '제출' }).dblclick()

    await expect(toast(page, '평가를 제출했습니다.')).toBeVisible()
    await expect(toast(page, '이미 제출된 평가입니다')).toHaveCount(0)
    expect(submitResponses).toEqual([200])
  })
})

test.describe('권한 격리', () => {
  test('다른 사람의 평가지 주소로 들어가면 목록으로 돌려보낸다', async ({ page, api, loginAs }) => {
    const { evaluator, assignment } = await api.seedOpenEvaluation()
    const { access } = await api.login(evaluator)
    const { body } = await api.call('POST', 'my/responses/', {
      token: access,
      data: { assignment: assignment.id },
    })

    const stranger = await api.createUser()
    await loginAs(stranger, `/my/evaluations/${body.id}`)

    await expect(toast(page, '평가지를 찾을 수 없거나 접근 권한이 없습니다.')).toBeVisible()
    await expect(page).toHaveURL(/\/my\/evaluations$/)
  })
})
