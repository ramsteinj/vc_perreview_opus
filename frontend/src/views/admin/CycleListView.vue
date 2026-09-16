<script setup>
import { onMounted, reactive, ref } from 'vue'

import { extractErrorMessage } from '@/api/client'
import * as api from '@/api/evaluations'
import BaseModal from '@/components/BaseModal.vue'
import { useToastStore } from '@/stores/toast'

const toasts = useToastStore()

const cycles = ref([])
const loading = ref(false)

const editModal = reactive({ open: false, busy: false, error: '', mode: 'create', id: null })
const form = reactive({
  name: '',
  year: new Date().getFullYear(),
  starts_on: '',
  ends_on: '',
  primary_weight: '70.00',
  secondary_weight: '30.00',
  dept_baseline_score: '70.00',
  dept_adjust_factor: '0.20',
  dept_adjust_limit: '10.00',
})

const confirmModal = reactive({
  open: false,
  busy: false,
  title: '',
  message: '',
  detail: null,
  action: null,
})

const statusMeta = {
  DRAFT: { label: '준비중', variant: 'secondary' },
  OPEN: { label: '진행중', variant: 'success' },
  CLOSED: { label: '마감', variant: 'dark' },
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.fetchCycles({ page_size: 100 })
    cycles.value = data.results
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editModal.mode = 'create'
  editModal.id = null
  editModal.error = ''
  Object.assign(form, {
    name: '',
    year: new Date().getFullYear(),
    starts_on: '',
    ends_on: '',
    primary_weight: '70.00',
    secondary_weight: '30.00',
    dept_baseline_score: '70.00',
    dept_adjust_factor: '0.20',
    dept_adjust_limit: '10.00',
  })
  editModal.open = true
}

function openEdit(cycle) {
  editModal.mode = 'edit'
  editModal.id = cycle.id
  editModal.error = ''
  Object.assign(form, {
    name: cycle.name,
    year: cycle.year,
    starts_on: cycle.starts_on,
    ends_on: cycle.ends_on,
    primary_weight: cycle.primary_weight,
    secondary_weight: cycle.secondary_weight,
    dept_baseline_score: cycle.dept_baseline_score,
    dept_adjust_factor: cycle.dept_adjust_factor,
    dept_adjust_limit: cycle.dept_adjust_limit,
  })
  editModal.open = true
}

async function submitEdit() {
  editModal.error = ''
  if (!form.name.trim() || !form.starts_on || !form.ends_on) {
    editModal.error = '회차명, 시작일, 마감일을 모두 입력하세요.'
    return
  }

  editModal.busy = true
  try {
    if (editModal.mode === 'create') {
      await api.createCycle({ ...form, name: form.name.trim() })
      toasts.success('회차를 생성했습니다.')
    } else {
      await api.updateCycle(editModal.id, { ...form, name: form.name.trim() })
      toasts.success('회차를 수정했습니다.')
    }
    editModal.open = false
    await load()
  } catch (error) {
    editModal.error = extractErrorMessage(error)
  } finally {
    editModal.busy = false
  }
}

/** OPEN 전이. 검증 실패는 원인을 그대로 보여주고, 경고는 확인을 받는다. */
async function requestOpen(cycle, confirm = false) {
  try {
    await api.openCycle(cycle.id, { confirm })
    confirmModal.open = false
    toasts.success(`'${cycle.name}' 회차를 열었습니다.`)
    await load()
  } catch (error) {
    const data = error?.response?.data
    if (data?.code === 'UNASSIGNED_TARGETS') {
      const employees = data.unassigned?.employees ?? []
      const departments = data.unassigned?.departments ?? []
      Object.assign(confirmModal, {
        open: true,
        busy: false,
        title: '미배정 대상이 있습니다',
        message: data.detail,
        detail: {
          employees: employees.map((e) => `${e.name} (${e.employee_no})`),
          departments: departments.map((d) => `${d.name} (${d.code})`),
        },
        action: () => requestOpen(cycle, true),
      })
      return
    }
    if (data?.code === 'WEIGHT_SUM_INVALID') {
      const parts = Object.entries(data.invalid ?? {}).map(
        ([type, info]) =>
          `${type === 'EMPLOYEE' ? '개인' : '부서'} 항목 합계 ${info.sum}% (${info.item_count}개)`
      )
      toasts.error(`가중치 합계가 100이 아닙니다 — ${parts.join(', ')}`)
      return
    }
    toasts.error(extractErrorMessage(error))
  }
}

async function requestClose(cycle, confirm = false) {
  try {
    await api.closeCycle(cycle.id, { confirm })
    confirmModal.open = false
    toasts.success(`'${cycle.name}' 회차를 마감했습니다.`)
    await load()
  } catch (error) {
    const data = error?.response?.data
    if (data?.code === 'PENDING_RESPONSES') {
      Object.assign(confirmModal, {
        open: true,
        busy: false,
        title: '미제출 평가지가 있습니다',
        message: data.detail,
        detail: null,
        action: () => requestClose(cycle, true),
      })
      return
    }
    toasts.error(extractErrorMessage(error))
  }
}

function askClose(cycle) {
  Object.assign(confirmModal, {
    open: true,
    busy: false,
    title: '회차 마감',
    message: `'${cycle.name}' 회차를 마감합니다. 마감 후에는 항목·배정·응답이 읽기 전용이 됩니다.`,
    detail: null,
    action: () => requestClose(cycle, false),
  })
}

function askReopen(cycle) {
  Object.assign(confirmModal, {
    open: true,
    busy: false,
    title: '마감 취소',
    message: `'${cycle.name}' 회차를 다시 진행 중 상태로 되돌립니다.`,
    detail: null,
    action: async () => {
      await api.reopenCycle(cycle.id)
      confirmModal.open = false
      toasts.success('회차를 다시 열었습니다.')
      await load()
    },
  })
}

function askDelete(cycle) {
  Object.assign(confirmModal, {
    open: true,
    busy: false,
    title: '회차 삭제',
    message: `'${cycle.name}' 회차를 삭제합니다. 되돌릴 수 없습니다.`,
    detail: null,
    action: async () => {
      await api.deleteCycle(cycle.id)
      confirmModal.open = false
      toasts.success('회차를 삭제했습니다.')
      await load()
    },
  })
}

async function runConfirm() {
  confirmModal.busy = true
  try {
    await confirmModal.action()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
    confirmModal.open = false
  } finally {
    confirmModal.busy = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex justify-content-end mb-3">
      <button class="btn btn-primary btn-sm" type="button" @click="openCreate">
        + 회차 추가
      </button>
    </div>

    <div class="card shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th scope="col">회차명</th>
              <th scope="col" style="width: 80px">연도</th>
              <th scope="col" style="width: 200px">응답 기간</th>
              <th scope="col" class="text-center" style="width: 90px">항목</th>
              <th scope="col" class="text-center" style="width: 90px">배정</th>
              <th scope="col" class="text-center" style="width: 90px">상태</th>
              <th scope="col" class="text-end" style="width: 330px">작업</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="text-center py-5 text-muted">
                <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
                불러오는 중...
              </td>
            </tr>
            <tr v-else-if="cycles.length === 0">
              <td colspan="7" class="text-center py-5 text-muted">
                등록된 평가 회차가 없습니다. [회차 추가]로 시작하세요.
              </td>
            </tr>
            <tr v-for="cycle in loading ? [] : cycles" :key="cycle.id">
              <td>{{ cycle.name }}</td>
              <td>{{ cycle.year }}</td>
              <td class="small">{{ cycle.starts_on }} ~ {{ cycle.ends_on }}</td>
              <td class="text-center">{{ cycle.item_count }}</td>
              <td class="text-center">{{ cycle.assignment_count }}</td>
              <td class="text-center">
                <span class="badge" :class="`text-bg-${statusMeta[cycle.status].variant}`">
                  {{ statusMeta[cycle.status].label }}
                </span>
              </td>
              <td class="text-end">
                <RouterLink
                  class="btn btn-outline-secondary btn-sm me-1"
                  :to="{ name: 'admin-cycle-items', params: { id: cycle.id } }"
                >
                  항목
                </RouterLink>
                <RouterLink
                  class="btn btn-outline-secondary btn-sm me-1"
                  :to="{ name: 'admin-cycle-assignments', params: { id: cycle.id } }"
                >
                  배정
                </RouterLink>
                <button
                  v-if="cycle.status === 'DRAFT'"
                  class="btn btn-success btn-sm me-1"
                  type="button"
                  @click="requestOpen(cycle)"
                >
                  열기
                </button>
                <button
                  v-if="cycle.status === 'OPEN'"
                  class="btn btn-dark btn-sm me-1"
                  type="button"
                  @click="askClose(cycle)"
                >
                  마감
                </button>
                <button
                  v-if="cycle.status === 'CLOSED'"
                  class="btn btn-outline-warning btn-sm me-1"
                  type="button"
                  @click="askReopen(cycle)"
                >
                  마감취소
                </button>
                <button
                  class="btn btn-outline-primary btn-sm me-1"
                  type="button"
                  :disabled="cycle.status === 'CLOSED'"
                  @click="openEdit(cycle)"
                >
                  수정
                </button>
                <button
                  v-if="cycle.item_count === 0 && cycle.assignment_count === 0"
                  class="btn btn-outline-danger btn-sm"
                  type="button"
                  @click="askDelete(cycle)"
                >
                  삭제
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 생성 / 수정 -->
    <BaseModal
      v-model="editModal.open"
      :title="editModal.mode === 'create' ? '평가 회차 추가' : '평가 회차 수정'"
      size="modal-lg"
      :busy="editModal.busy"
      confirm-text="저장"
      @confirm="submitEdit"
    >
      <div v-if="editModal.error" class="alert alert-danger py-2 small">{{ editModal.error }}</div>

      <div class="row g-3">
        <div class="col-md-8">
          <label class="form-label" for="c-name">회차명 <span class="text-danger">*</span></label>
          <input
            id="c-name"
            v-model="form.name"
            type="text"
            class="form-control"
            placeholder="2026년 상반기 평가"
          />
        </div>
        <div class="col-md-4">
          <label class="form-label" for="c-year">평가연도</label>
          <input id="c-year" v-model.number="form.year" type="number" class="form-control" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="c-start">응답 시작일 <span class="text-danger">*</span></label>
          <input id="c-start" v-model="form.starts_on" type="date" class="form-control" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="c-end">응답 마감일 <span class="text-danger">*</span></label>
          <input id="c-end" v-model="form.ends_on" type="date" class="form-control" />
        </div>
      </div>

      <hr class="my-4" />

      <h6 class="mb-3">평가자 반영 비율 <span class="text-muted small">(합계 100)</span></h6>
      <div class="row g-3">
        <div class="col-md-6">
          <label class="form-label" for="c-pw">1차 평가자 (%)</label>
          <input id="c-pw" v-model="form.primary_weight" type="number" step="0.01" class="form-control" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="c-sw">2차 평가자 (%)</label>
          <input id="c-sw" v-model="form.secondary_weight" type="number" step="0.01" class="form-control" />
        </div>
      </div>

      <hr class="my-4" />

      <h6 class="mb-1">부서 성과 가감 파라미터</h6>
      <p class="text-muted small mb-3">
        가감 = clamp((부서점수 − 기준점) × 계수, −한도, +한도)
      </p>
      <div class="row g-3">
        <div class="col-md-4">
          <label class="form-label" for="c-base">기준점</label>
          <input id="c-base" v-model="form.dept_baseline_score" type="number" step="0.01" class="form-control" />
        </div>
        <div class="col-md-4">
          <label class="form-label" for="c-factor">계수</label>
          <input id="c-factor" v-model="form.dept_adjust_factor" type="number" step="0.01" class="form-control" />
        </div>
        <div class="col-md-4">
          <label class="form-label" for="c-limit">한도 (±)</label>
          <input id="c-limit" v-model="form.dept_adjust_limit" type="number" step="0.01" class="form-control" />
        </div>
      </div>
    </BaseModal>

    <!-- 확인 -->
    <BaseModal
      v-model="confirmModal.open"
      :title="confirmModal.title"
      :busy="confirmModal.busy"
      confirm-text="진행"
      confirm-variant="warning"
      @confirm="runConfirm"
    >
      <p class="mb-3">{{ confirmModal.message }}</p>

      <div v-if="confirmModal.detail" class="small">
        <div v-if="confirmModal.detail.employees.length" class="mb-2">
          <strong>미배정 직원 {{ confirmModal.detail.employees.length }}명</strong>
          <ul class="mb-0 mt-1 ps-3" style="max-height: 150px; overflow-y: auto">
            <li v-for="name in confirmModal.detail.employees" :key="name">{{ name }}</li>
          </ul>
        </div>
        <div v-if="confirmModal.detail.departments.length">
          <strong>미배정 부서 {{ confirmModal.detail.departments.length }}개</strong>
          <ul class="mb-0 mt-1 ps-3" style="max-height: 150px; overflow-y: auto">
            <li v-for="name in confirmModal.detail.departments" :key="name">{{ name }}</li>
          </ul>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
