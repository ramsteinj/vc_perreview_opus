<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { fetchDepartments } from '@/api/admin'
import { extractErrorMessage } from '@/api/client'
import { downloadCycleCsv } from '@/api/download'
import { fetchCycle } from '@/api/evaluations'
import * as api from '@/api/reports'
import BaseModal from '@/components/BaseModal.vue'
import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toasts = useToastStore()

const cycleId = Number(route.params.id)
const cycle = ref(null)

const rows = ref([])
const total = ref(0)
const totalTargets = ref(0)
const notCalculated = ref(0)
const isProvisional = ref(true)
const loading = ref(false)
const recalculating = ref(false)

const page = ref(1)
const PAGE_SIZE = 25
const ordering = ref('-final_score')
const filters = reactive({ department: '', search: '' })
const departments = ref([])
let searchTimer = null

const resultModal = reactive({ open: false, data: null })
const downloading = ref(false)

const REASON_LABELS = {
  PRIMARY_NOT_SUBMITTED: '1차 평가 미제출',
  NO_ASSIGNMENT: '평가자 미배정',
  NO_ACTIVE_ITEMS: '활성 평가 항목 없음',
  ZERO_WEIGHT_SUM: '환산 가능한 응답 없음',
}

const columns = [
  { key: 'employee_no', label: '사번', sortable: true, width: '110px' },
  { key: 'name', label: '성명', sortable: true, width: '110px' },
  { key: 'department', label: '부서', width: '120px' },
  { key: 'primary_score', label: '1차', align: 'end', width: '85px' },
  { key: 'secondary_score', label: '2차', align: 'end', width: '85px' },
  { key: 'individual_score', label: '개인', sortable: true, align: 'end', width: '90px' },
  { key: 'department_adjustment', label: '부서가감', align: 'end', width: '100px' },
  { key: 'final_score', label: '최종', sortable: true, align: 'end', width: '100px' },
]

const orderingForServer = computed(() => {
  const map = {
    employee_no: 'user__employee_no',
    name: 'user__name',
    individual_score: 'individual_score',
    final_score: 'final_score',
  }
  const desc = ordering.value.startsWith('-')
  const field = ordering.value.replace('-', '')
  const mapped = map[field] ?? 'final_score'
  return `${desc ? '-' : ''}${mapped}`
})

function fmt(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toFixed(2)
}

function signed(value) {
  const number = Number(value ?? 0)
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}`
}

function adjustClass(value) {
  const number = Number(value ?? 0)
  if (number > 0) return 'text-success'
  if (number < 0) return 'text-danger'
  return 'text-muted'
}

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: PAGE_SIZE, ordering: orderingForServer.value }
    if (filters.department) params.department = filters.department
    if (filters.search) params.search = filters.search

    const { data } = await api.fetchScores(cycleId, params)
    rows.value = data.results.map((r) => ({
      ...r,
      employee_no: r.user.employee_no,
      name: r.user.name,
      department: r.user.department_name,
    }))
    total.value = data.count
    totalTargets.value = data.total_targets
    notCalculated.value = data.not_calculated
    isProvisional.value = data.is_provisional
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

watch([page, ordering], load)
watch(
  () => filters.department,
  () => {
    page.value = 1
    load()
  }
)
watch(
  () => filters.search,
  () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      page.value = 1
      load()
    }, 300)
  }
)

/** 화면에 적용된 필터 그대로 내려받는다. */
async function downloadCsv() {
  downloading.value = true
  try {
    const params = {}
    if (filters.department) params.department = filters.department
    if (filters.search) params.search = filters.search

    const filename = await downloadCycleCsv(cycleId, 'scores', params)
    toasts.success(`${filename} 다운로드를 시작했습니다.`)
  } catch (error) {
    toasts.error(extractErrorMessage(error, 'CSV 다운로드에 실패했습니다.'))
  } finally {
    downloading.value = false
  }
}

async function recalculate() {
  recalculating.value = true
  try {
    const { data } = await api.calculateScores(cycleId)
    resultModal.data = data
    resultModal.open = true
    await load()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    recalculating.value = false
  }
}

onMounted(async () => {
  const [cycleRes, deptRes] = await Promise.all([
    fetchCycle(cycleId),
    fetchDepartments({ page_size: 200 }),
  ])
  cycle.value = cycleRes.data
  departments.value = deptRes.data.results
  await load()
})
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
      <div>
        <RouterLink :to="{ name: 'admin-cycles' }" class="small text-decoration-none">
          ← 회차 목록
        </RouterLink>
        <h2 class="h6 mb-0 mt-1">
          {{ cycle?.name }}
          <StatusBadge v-if="cycle" :status="cycle.status" class="ms-1" />
          <span v-if="isProvisional" class="badge text-bg-warning ms-1">잠정 결과</span>
        </h2>
      </div>
      <div class="d-flex gap-2">
        <RouterLink
          class="btn btn-outline-secondary btn-sm"
          :to="{ name: 'admin-cycle-department-scores', params: { id: cycleId } }"
        >
          ← 부서 성과 점수
        </RouterLink>
        <button
          class="btn btn-outline-success btn-sm"
          type="button"
          :disabled="downloading"
          @click="downloadCsv"
        >
          <span v-if="downloading" class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
          CSV 다운로드
        </button>
        <button
          class="btn btn-primary btn-sm"
          type="button"
          :disabled="recalculating"
          @click="recalculate"
        >
          <span v-if="recalculating" class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
          재계산
        </button>
      </div>
    </div>

    <div v-if="isProvisional" class="alert alert-warning py-2 small">
      회차가 마감되지 않았습니다. 아래는 현재 제출분만 반영한 <strong>잠정 결과</strong>입니다.
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-body py-3">
        <div class="row g-2 align-items-end">
          <div class="col-6 col-md-3">
            <label class="form-label small mb-1" for="s-dept">부서</label>
            <select id="s-dept" v-model="filters.department" class="form-select form-select-sm">
              <option value="">전체</option>
              <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
          <div class="col-6 col-md-4">
            <label class="form-label small mb-1" for="s-search">검색</label>
            <input
              id="s-search"
              v-model="filters.search"
              type="search"
              class="form-control form-control-sm"
              placeholder="성명 · 사번"
            />
          </div>
          <div class="col-12 col-md-5 text-md-end">
            <span class="badge text-bg-success me-1">산출 {{ totalTargets - notCalculated }}</span>
            <span class="badge" :class="notCalculated ? 'text-bg-warning' : 'text-bg-light'">
              미산출 {{ notCalculated }}
            </span>
            <span class="text-muted small ms-2">전체 {{ totalTargets }}명</span>
          </div>
        </div>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-body p-3">
        <DataTable
          v-model:page="page"
          v-model:ordering="ordering"
          :columns="columns"
          :rows="rows"
          :loading="loading"
          :page-size="PAGE_SIZE"
          :total="total"
          empty-text="산출된 점수가 없습니다. [재계산]을 눌러 산출하세요."
        >
          <template #cell-department="{ row }">
            <span class="small">{{ row.department ?? '미배정' }}</span>
          </template>
          <template #cell-primary_score="{ row }">{{ fmt(row.primary_score) }}</template>
          <template #cell-secondary_score="{ row }">{{ fmt(row.secondary_score) }}</template>
          <template #cell-individual_score="{ row }">
            {{ fmt(row.individual_score) }}
          </template>
          <template #cell-department_adjustment="{ row }">
            <span :class="adjustClass(row.department_adjustment)">
              {{ signed(row.department_adjustment) }}
            </span>
          </template>
          <template #cell-final_score="{ row }">
            <strong>{{ fmt(row.final_score) }}</strong>
          </template>
        </DataTable>
      </div>
    </div>

    <p class="text-muted small mt-2 mb-0">
      최종 = clamp(개인 평가 점수 + 부서 가감, 0, 100) ·
      2차 평가자가 없거나 미제출이면 1차 점수가 100% 반영됩니다.
    </p>

    <!-- 산출 결과 요약 -->
    <BaseModal v-model="resultModal.open" title="산출 결과" size="modal-lg" hide-footer>
      <template v-if="resultModal.data">
        <div class="row g-2 mb-3">
          <div class="col-4">
            <div class="border rounded p-3 text-center">
              <p class="small text-muted mb-1">대상</p>
              <p class="h4 mb-0">{{ resultModal.data.total_targets }}</p>
            </div>
          </div>
          <div class="col-4">
            <div class="border rounded p-3 text-center">
              <p class="small text-muted mb-1">산출</p>
              <p class="h4 mb-0 text-success">{{ resultModal.data.calculated }}</p>
            </div>
          </div>
          <div class="col-4">
            <div class="border rounded p-3 text-center">
              <p class="small text-muted mb-1">미산출</p>
              <p class="h4 mb-0" :class="resultModal.data.skipped ? 'text-warning' : ''">
                {{ resultModal.data.skipped }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="resultModal.data.skipped_reasons.length">
          <p class="small text-muted mb-2">미산출 대상과 사유</p>
          <div class="table-responsive" style="max-height: 300px">
            <table class="table table-sm mb-0">
              <thead class="table-light">
                <tr>
                  <th scope="col">사번</th>
                  <th scope="col">성명</th>
                  <th scope="col">사유</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in resultModal.data.skipped_reasons" :key="item.user_id">
                  <td><code class="small">{{ item.employee_no }}</code></td>
                  <td>{{ item.name }}</td>
                  <td class="small">
                    {{ REASON_LABELS[item.reason] ?? item.reason }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <p v-else class="text-success small mb-0">모든 대상의 점수가 산출되었습니다.</p>

        <div class="d-flex justify-content-end mt-4">
          <button class="btn btn-primary btn-sm" type="button" @click="resultModal.open = false">
            확인
          </button>
        </div>
      </template>
    </BaseModal>
  </div>
</template>
