// 테스트 데이터를 준비하는 백엔드 API 클라이언트.
//
// 검증 대상이 아닌 준비 단계(부서·사용자·회차 생성 등)는 UI를 거치지 않고
// API로 빠르게 만든다. UI는 각 테스트가 실제로 검증하려는 흐름에만 쓴다.
import { expect, request as playwrightRequest } from '@playwright/test'

import { BACKEND_URL } from './env.js'
import { ADMIN, isoDate, password as makePassword, uid } from './data.js'

export class Api {
  constructor(context) {
    this.context = context
  }

  static async create() {
    const context = await playwrightRequest.newContext({ baseURL: `${BACKEND_URL}/api/` })
    return new Api(context)
  }

  async dispose() {
    await this.context.dispose()
  }

  // ── 인증 ────────────────────────────────────────────────────
  async login({ name, employeeNo, password }) {
    const res = await this.context.post('auth/login/', {
      data: { name, employee_no: employeeNo, password },
    })
    expect(res.status(), `로그인 실패: ${employeeNo}`).toBe(200)
    return res.json()
  }

  async adminToken() {
    if (!this._adminToken) {
      const { access } = await this.login(ADMIN)
      this._adminToken = access
    }
    return this._adminToken
  }

  async call(method, path, { token, data, expectStatus } = {}) {
    const res = await this.context.fetch(path, {
      method,
      data,
      headers: { Authorization: `Bearer ${token ?? (await this.adminToken())}` },
    })
    if (expectStatus !== undefined) {
      expect(res.status(), `${method} ${path}\n${await res.text()}`).toBe(expectStatus)
    }
    const text = await res.text()
    return { status: res.status(), body: text ? JSON.parse(text) : null }
  }

  // ── 마스터 데이터 ───────────────────────────────────────────
  async createDepartment({ code = `D${uid()}`, name = `부서${uid()}`, parent = null } = {}) {
    const { body } = await this.call('POST', 'admin/departments/', {
      data: { code, name, parent },
      expectStatus: 201,
    })
    return body
  }

  /** 사용자를 만들고 로그인에 필요한 정보까지 함께 돌려준다. */
  async createUser({
    employeeNo = `U${uid()}`,
    name = `사용자${uid().slice(-4)}`,
    department = null,
    role = 'EMPLOYEE',
    position = '',
  } = {}) {
    const pw = makePassword()
    const { body } = await this.call('POST', 'admin/users/', {
      data: { employee_no: employeeNo, name, department, role, position, password: pw },
      expectStatus: 201,
    })
    return { ...body, employeeNo, password: pw }
  }

  // ── 평가 설정 ───────────────────────────────────────────────
  async createCycle(overrides = {}) {
    const { body } = await this.call('POST', 'admin/cycles/', {
      data: {
        name: `E2E 회차 ${uid()}`,
        year: new Date().getFullYear(),
        starts_on: isoDate(-1),
        ends_on: isoDate(30),
        ...overrides,
      },
      expectStatus: 201,
    })
    return body
  }

  async createItem(cycleId, { targetType = 'EMPLOYEE', code, title, weight, maxScore = 5, order = 0 }) {
    const { body } = await this.call('POST', 'admin/items/', {
      data: {
        cycle: cycleId,
        target_type: targetType,
        code,
        title,
        weight: String(weight),
        max_score: maxScore,
        order,
      },
      expectStatus: 201,
    })
    return body
  }

  /** 스펙 06-scoring.md §2 예시와 같은 가중치 50/30/20 항목 3개 */
  async createStandardItems(cycleId, targetType = 'EMPLOYEE') {
    const prefix = targetType === 'EMPLOYEE' ? '' : 'D'
    return [
      await this.createItem(cycleId, { targetType, code: `${prefix}PERF`, title: `${prefix}업무 성과`, weight: 50, order: 1 }),
      await this.createItem(cycleId, { targetType, code: `${prefix}COLLAB`, title: `${prefix}협업`, weight: 30, order: 2 }),
      await this.createItem(cycleId, { targetType, code: `${prefix}ATT`, title: `${prefix}태도`, weight: 20, order: 3 }),
    ]
  }

  async assign(cycleId, { targetUser, targetDepartment, primary, secondary = null }) {
    const data = {
      cycle: cycleId,
      target_type: targetDepartment ? 'DEPARTMENT' : 'EMPLOYEE',
      primary_evaluator: primary,
      secondary_evaluator: secondary,
    }
    if (targetDepartment) data.target_department = targetDepartment
    else data.target_user = targetUser

    const { body } = await this.call('POST', 'admin/assignments/', { data, expectStatus: 201 })
    return body
  }

  async openCycle(cycleId) {
    // 다른 테스트가 만든 사용자는 항상 미배정 상태이므로 confirm이 필요하다
    await this.call('POST', `admin/cycles/${cycleId}/open/?confirm=true`, { expectStatus: 200 })
  }

  async calculate(cycleId) {
    const { body } = await this.call('POST', `admin/cycles/${cycleId}/calculate/`, {
      expectStatus: 200,
    })
    return body
  }

  // ── 평가자 행동 ─────────────────────────────────────────────
  async submitSheet(user, assignmentId, scores) {
    const { access } = await this.login(user)
    const { body: response } = await this.call('POST', 'my/responses/', {
      token: access,
      data: { assignment: assignmentId },
    })
    const answers = response.items.map((item, index) => ({ item: item.id, score: scores[index] }))
    await this.call('PUT', `my/responses/${response.id}/`, {
      token: access,
      data: { answers },
      expectStatus: 200,
    })
    await this.call('POST', `my/responses/${response.id}/submit/`, {
      token: access,
      expectStatus: 200,
    })
    return response.id
  }

  /**
   * 평가 한 건이 진행 가능한 최소 구성을 만든다.
   * 부서 1개, 평가자 1명, 피평가자 1명, 항목 3개(50/30/20), 배정 1건, 회차 OPEN.
   */
  async seedOpenEvaluation({ secondary = false } = {}) {
    const department = await this.createDepartment()
    const evaluator = await this.createUser({ name: `평가자${uid().slice(-4)}`, department: department.id })
    const target = await this.createUser({ name: `피평가자${uid().slice(-4)}`, department: department.id })
    const second = secondary
      ? await this.createUser({ name: `이차평가자${uid().slice(-4)}`, department: department.id })
      : null

    const cycle = await this.createCycle()
    const items = await this.createStandardItems(cycle.id)
    const assignment = await this.assign(cycle.id, {
      targetUser: target.id,
      primary: evaluator.id,
      secondary: second?.id ?? null,
    })
    await this.openCycle(cycle.id)

    return { department, evaluator, target, secondary: second, cycle, items, assignment }
  }
}
