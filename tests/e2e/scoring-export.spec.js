// 점수 산출 · CSV 내보내기 (specs/06-scoring.md, specs/05-admin-features.md FR-A-07~09)
import { readFile } from 'node:fs/promises'

import { dialog, expect, test } from './support/fixtures.js'

/**
 * specs/06-scoring.md §6 예시를 그대로 재현하는 회차.
 *   개인 1차 [4,5,3] → 82.00, 2차 [4,5,5] → 90.00, 70:30 결합 → 84.40
 *   부서 1차 [4,5,5] → 90.00, 가감 (90-70)×0.2 → +4.00
 *   최종 84.40 + 4.00 → 88.40
 */
async function seedSpecExample(api) {
  const department = await api.createDepartment()
  const first = await api.createUser({ name: '일차평가자', department: department.id })
  const second = await api.createUser({ name: '이차평가자', department: department.id })
  const target = await api.createUser({ name: '피평가자', department: department.id })

  const cycle = await api.createCycle()
  await api.createStandardItems(cycle.id, 'EMPLOYEE')
  await api.createStandardItems(cycle.id, 'DEPARTMENT')

  const personal = await api.assign(cycle.id, {
    targetUser: target.id,
    primary: first.id,
    secondary: second.id,
  })
  const departmental = await api.assign(cycle.id, {
    targetDepartment: department.id,
    primary: first.id,
  })
  await api.openCycle(cycle.id)

  await api.submitSheet(first, personal.id, [4, 5, 3])
  await api.submitSheet(second, personal.id, [4, 5, 5])
  await api.submitSheet(first, departmental.id, [4, 5, 5])

  return { cycle, department, target }
}

function rowByFirstCell(page, text) {
  return page.locator('tbody tr').filter({ has: page.locator('td:first-child', { hasText: text }) })
}

test('재계산하면 스펙 예시와 같은 최종 점수 88.40이 나온다', async ({ page, api, loginAs }) => {
  const { cycle, target } = await seedSpecExample(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/scores`)

  await page.getByRole('button', { name: '재계산' }).click()
  const result = dialog(page, '산출 결과')
  await expect(result).toContainText('모든 대상의 점수가 산출되었습니다.')
  await result.getByRole('button', { name: '확인' }).click()

  const row = rowByFirstCell(page, target.employeeNo)
  const cells = row.locator('td')
  await expect(cells.nth(3)).toHaveText('82.00') // 1차
  await expect(cells.nth(4)).toHaveText('90.00') // 2차
  await expect(cells.nth(5)).toHaveText('84.40') // 개인
  await expect(cells.nth(6)).toHaveText('+4.00') // 부서 가감
  await expect(cells.nth(7)).toHaveText('88.40') // 최종
})

test('회차가 마감되지 않았으면 잠정 결과로 표시된다', async ({ page, api, loginAs }) => {
  const { cycle } = await seedSpecExample(api)
  await api.calculate(cycle.id)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/scores`)

  // 제목 옆 배지와 상단 경고문 두 곳에 모두 표시된다
  await expect(page.getByRole('heading', { level: 2 }).getByText('잠정 결과')).toBeVisible()
  await expect(page.getByText('회차가 마감되지 않았습니다.')).toBeVisible()
})

test('부서 성과 점수 화면에 부서 점수와 가감이 나온다', async ({ page, api, loginAs }) => {
  const { cycle, department } = await seedSpecExample(api)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/department-scores`)

  const row = page.locator('tbody tr').filter({ hasText: department.name })
  await expect(row.locator('td').nth(3)).toHaveText('90.00')
  await expect(row.locator('td').nth(4)).toHaveText('+4.00')
  await expect(page.locator('.card-footer')).toContainText('기준점 70.00')
})

test('1차 평가가 없는 대상은 미산출 사유와 함께 보고된다', async ({ page, api, loginAs }) => {
  const seed = await api.seedOpenEvaluation()
  await loginAs(undefined, `/admin/cycles/${seed.cycle.id}/scores`)

  await page.getByRole('button', { name: '재계산' }).click()

  const result = dialog(page, '산출 결과')
  await expect(result.locator('tbody tr').filter({ hasText: seed.target.employeeNo })).toContainText(
    '1차 평가 미제출'
  )
})

test('점수 CSV는 UTF-8 BOM으로 시작하고 한글 파일명과 최종 점수를 담는다', async ({ page, api, loginAs }, testInfo) => {
  const { cycle, target } = await seedSpecExample(api)
  await api.calculate(cycle.id)
  await loginAs(undefined, `/admin/cycles/${cycle.id}/scores`)

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'CSV 다운로드' }).click(),
  ])

  expect(download.suggestedFilename()).toMatch(/_점수_\d{8}\.csv$/)

  // download.path()는 원격 브라우저에 연결해 실행하면 쓸 수 없다. saveAs()는 어디서나 동작한다
  const saved = testInfo.outputPath(download.suggestedFilename())
  await download.saveAs(saved)
  const bytes = await readFile(saved)
  // BOM(EF BB BF)이 없으면 Excel에서 한글이 깨진다
  expect([...bytes.subarray(0, 3)]).toEqual([0xef, 0xbb, 0xbf])

  const text = bytes.toString('utf-8').replace(/^﻿/, '')
  const [header, ...rows] = text.trim().split('\r\n')
  expect(header.split(',')).toContain('최종 점수')

  const line = rows.find((r) => r.includes(target.employeeNo))
  expect(line).toContain('88.40')
})
