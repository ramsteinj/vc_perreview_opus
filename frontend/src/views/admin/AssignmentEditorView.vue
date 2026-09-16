<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { fetchDepartments } from '@/api/admin'
import { extractErrorMessage } from '@/api/client'
import * as api from '@/api/evaluations'
import BaseModal from '@/components/BaseModal.vue'
import UserSelect from '@/components/UserSelect.vue'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toasts = useToastStore()

const cycleId = Number(route.params.id)
const cycle = ref(null)
const targetType = ref('EMPLOYEE')
const rows = ref([])
const summary = reactive({ count: 0, assigned: 0, unassigned: 0 })
const loading = ref(false)
const savingId = ref(null)

const filters = reactive({ department: '', search: '' })
const departments = ref([])
let searchTimer = null

const bulkModal = reactive({
  open: false,
  busy: false,
  error: '',
  department: '',
  primary: null,
  secondary: null,
  overwrite: false,
})

const readOnly = computed(() => cycle.value?.status === 'CLOSED')

async function loadCycle() {
  const { data } = await api.fetchCycle(cycleId)
  cycle.value = data
}

async function loadDepartments() {
  const { data } = await fetchDepartments({ page_size: 200, is_active: true })
  departments.value = data.results
}

async function load() {
  loading.value = true
  try {
    const params = { cycle: cycleId, target_type: targetType.value }
    if (filters.department) params.department = filters.department
    if (filters.search) params.search = filters.search

    const { data } = await api.fetchAssignmentOverview(params)
    rows.value = data.results.map((row) => ({
      ...row,
      primaryId: row.primary_evaluator?.id ?? null,
      secondaryId: row.secondary_evaluator?.id ?? null,
      dirty: false,
    }))
    Object.assign(summary, {
      count: data.count,
      assigned: data.assigned,
      unassigned: data.unassigned,
    })
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

watch(targetType, () => {
  filters.department = ''
  filters.search = ''
  load()
})

watch(
  () => filters.department,
  () => load()
)

watch(
  () => filters.search,
  () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(load, 300)
  }
)

function markDirty(row) {
  row.dirty = true
}

/** 행 단위로 저장한다. 1차가 비면 기존 배정을 삭제한다. */
async function saveRow(row) {
  savingId.value = rowKey(row)
  try {
    if (!row.primaryId) {
      if (row.assignment_id) {
        await api.deleteAssignment(row.assignment_id)
        toasts.success(`${row.target.name} 배정을 해제했습니다.`)
      } else {
        toasts.error('1차 평가자를 선택하세요.')
        return
      }
    } else {
      const payload = {
        cycle: cycleId,
        target_type: targetType.value,
        primary_evaluator: row.primaryId,
        secondary_evaluator: row.secondaryId,
      }
      if (targetType.value === 'EMPLOYEE') payload.target_user = row.target.id
      else payload.target_department = row.target.id

      if (row.assignment_id) {
        await api.updateAssignment(row.assignment_id, payload)
      } else {
        await api.createAssignment(payload)
      }
      toasts.success(`${row.target.name} 배정을 저장했습니다.`)
    }
    await load()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    savingId.value = null
  }
}

function rowKey(row) {
  return `${row.target_type}-${row.target.id}`
}

// ── 일괄 배정 ───────────────────────────────────────────────
function openBulk() {
  Object.assign(bulkModal, {
    open: true,
    busy: false,
    error: '',
    department: filters.department || '',
    primary: null,
    secondary: null,
    overwrite: false,
  })
}

async function submitBulk() {
  bulkModal.error = ''
  if (!bulkModal.primary) {
    bulkModal.error = '1차 평가자를 선택하세요.'
    return
  }
  if (targetType.value === 'EMPLOYEE' && !bulkModal.department) {
    bulkModal.error = '대상 부서를 선택하세요.'
    return
  }

  bulkModal.busy = true
  try {
    const payload = {
      cycle: cycleId,
      target_type: targetType.value,
      primary_evaluator: bulkModal.primary,
      secondary_evaluator: bulkModal.secondary,
      overwrite: bulkModal.overwrite,
    }
    if (targetType.value === 'EMPLOYEE') {
      payload.department = bulkModal.department
    } else {
      payload.target_ids = rows.value.map((r) => r.target.id)
    }

    const { data } = await api.bulkAssign(payload)
    bulkModal.open = false

    const parts = []
    if (data.created) parts.push(`신규 ${data.created}건`)
    if (data.updated) parts.push(`변경 ${data.updated}건`)
    if (data.skipped.length) parts.push(`건너뜀 ${data.skipped.length}건`)
    toasts.success(`일괄 배정 완료 — ${parts.join(', ') || '변경 없음'}`)

    const selfSkipped = data.skipped.filter((s) => s.reason === 'SELF_EVALUATION')
    if (selfSkipped.length) {
      toasts.push(
        `본인 평가가 되어 제외: ${selfSkipped.map((s) => s.name).join(', ')}`,
        'info',
        6000
      )
    }
    await load()
  } catch (error) {
    bulkModal.error = extractErrorMessage(error)
  } finally {
    bulkModal.busy = false
  }
}

onMounted(async () => {
  await Promise.all([loadCycle(), loadDepartments(), load()])
})
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <div>
        <RouterLink :to="{ name: 'admin-cycles' }" class="small text-decoration-none">
          ← 회차 목록
        </RouterLink>
        <h2 class="h6 mb-0 mt-1">{{ cycle?.name }}</h2>
      </div>
      <button class="btn btn-outline-primary btn-sm" type="button" :disabled="readOnly" @click="openBulk">
        일괄 배정
      </button>
    </div>

    <div v-if="readOnly" class="alert alert-secondary py-2 small">
      마감된 회차입니다. 배정을 수정할 수 없습니다.
    </div>

    <ul class="nav nav-tabs">
      <li class="nav-item">
        <button
          class="nav-link"
          :class="{ active: targetType === 'EMPLOYEE' }"
          type="button"
          @click="targetType = 'EMPLOYEE'"
        >
          개인 대상
        </button>
      </li>
      <li class="nav-item">
        <button
          class="nav-link"
          :class="{ active: targetType === 'DEPARTMENT' }"
          type="button"
          @click="targetType = 'DEPARTMENT'"
        >
          부서 대상
        </button>
      </li>
    </ul>

    <div class="card shadow-sm border-top-0 rounded-top-0">
      <div class="card-body py-3 border-bottom">
        <div class="row g-2 align-items-end">
          <div v-if="targetType === 'EMPLOYEE'" class="col-6 col-md-3">
            <label class="form-label small mb-1" for="a-dept">부서</label>
            <select id="a-dept" v-model="filters.department" class="form-select form-select-sm">
              <option value="">전체</option>
              <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
          <div class="col-6 col-md-4">
            <label class="form-label small mb-1" for="a-search">검색</label>
            <input
              id="a-search"
              v-model="filters.search"
              type="search"
              class="form-control form-control-sm"
              :placeholder="targetType === 'EMPLOYEE' ? '성명 또는 사번' : '부서명'"
            />
          </div>
          <div class="col-12 col-md-5 text-md-end">
            <span class="badge text-bg-success me-1">배정 {{ summary.assigned }}</span>
            <span class="badge" :class="summary.unassigned ? 'text-bg-warning' : 'text-bg-light'">
              미배정 {{ summary.unassigned }}
            </span>
            <span class="text-muted small ms-2">전체 {{ summary.count }}</span>
          </div>
        </div>
      </div>

      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th scope="col" style="width: 200px">평가 대상</th>
              <th v-if="targetType === 'EMPLOYEE'" scope="col" style="width: 130px">부서</th>
              <th scope="col">1차 평가자 <span class="text-danger">*</span></th>
              <th scope="col">2차 평가자 <span class="text-muted small">(선택)</span></th>
              <th scope="col" class="text-end" style="width: 100px">작업</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td :colspan="targetType === 'EMPLOYEE' ? 5 : 4" class="text-center py-5 text-muted">
                <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
                불러오는 중...
              </td>
            </tr>
            <tr v-else-if="rows.length === 0">
              <td :colspan="targetType === 'EMPLOYEE' ? 5 : 4" class="text-center py-5 text-muted">
                대상이 없습니다.
              </td>
            </tr>
            <tr v-for="row in loading ? [] : rows" :key="rowKey(row)">
              <td>
                {{ row.target.name }}
                <span class="text-muted small">
                  {{ row.target.employee_no ?? row.target.code }}
                </span>
                <span v-if="!row.assigned" class="badge text-bg-warning ms-1">미배정</span>
              </td>
              <td v-if="targetType === 'EMPLOYEE'" class="small">
                {{ row.target.department_name ?? '-' }}
              </td>
              <td>
                <UserSelect
                  v-model="row.primaryId"
                  size="form-select-sm"
                  placeholder="미지정"
                  :disabled="readOnly"
                  :exclude-id="targetType === 'EMPLOYEE' ? row.target.id : null"
                  :invalid="!row.primaryId && row.dirty"
                  @update:model-value="markDirty(row)"
                />
              </td>
              <td>
                <UserSelect
                  v-model="row.secondaryId"
                  size="form-select-sm"
                  placeholder="미지정 (선택)"
                  :disabled="readOnly || !row.primaryId"
                  :exclude-id="targetType === 'EMPLOYEE' ? row.target.id : null"
                  @update:model-value="markDirty(row)"
                />
              </td>
              <td class="text-end">
                <button
                  class="btn btn-primary btn-sm"
                  type="button"
                  :disabled="readOnly || !row.dirty || savingId === rowKey(row)"
                  @click="saveRow(row)"
                >
                  <span
                    v-if="savingId === rowKey(row)"
                    class="spinner-border spinner-border-sm"
                    aria-hidden="true"
                  />
                  <template v-else>저장</template>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <p class="text-muted small mt-2 mb-0">
      2차 평가자를 지정하지 않으면 1차 점수가 100% 반영됩니다.
    </p>

    <!-- 일괄 배정 -->
    <BaseModal
      v-model="bulkModal.open"
      title="일괄 배정"
      :busy="bulkModal.busy"
      confirm-text="배정"
      @confirm="submitBulk"
    >
      <div v-if="bulkModal.error" class="alert alert-danger py-2 small">{{ bulkModal.error }}</div>

      <div v-if="targetType === 'EMPLOYEE'" class="mb-3">
        <label class="form-label" for="b-dept">대상 부서 <span class="text-danger">*</span></label>
        <select id="b-dept" v-model="bulkModal.department" class="form-select">
          <option value="">선택하세요</option>
          <option v-for="d in departments" :key="d.id" :value="d.id">
            {{ d.name }} ({{ d.code }})
          </option>
        </select>
        <div class="form-text">해당 부서 전원에게 같은 평가자를 지정합니다.</div>
      </div>
      <div v-else class="alert alert-light py-2 small">
        현재 목록의 부서 {{ rows.length }}개에 같은 평가자를 지정합니다.
      </div>

      <div class="mb-3">
        <label class="form-label" for="b-primary">1차 평가자 <span class="text-danger">*</span></label>
        <UserSelect id="b-primary" v-model="bulkModal.primary" placeholder="선택하세요" />
      </div>

      <div class="mb-3">
        <label class="form-label" for="b-secondary">2차 평가자 <span class="text-muted small">(선택)</span></label>
        <UserSelect
          id="b-secondary"
          v-model="bulkModal.secondary"
          placeholder="미지정"
          :exclude-id="bulkModal.primary"
        />
      </div>

      <div class="form-check">
        <input id="b-overwrite" v-model="bulkModal.overwrite" class="form-check-input" type="checkbox" />
        <label class="form-check-label" for="b-overwrite">기존 배정 덮어쓰기</label>
      </div>
      <div class="form-text">
        체크하지 않으면 이미 배정된 대상은 건너뜁니다. 평가자 본인은 자동으로 제외됩니다.
      </div>
    </BaseModal>
  </div>
</template>
