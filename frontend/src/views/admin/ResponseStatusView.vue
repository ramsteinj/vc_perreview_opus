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
import DonutChart from '@/components/DonutChart.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toasts = useToastStore()

const cycleId = Number(route.params.id)
const cycle = ref(null)
const tab = ref('summary')

const summary = ref(null)
const summaryLoading = ref(true)

const detailRows = ref([])
const detailTotal = ref(0)
const detailLoading = ref(false)
const detailPage = ref(1)
const detailOrdering = ref('status')
const DETAIL_PAGE_SIZE = 25

const pendingRows = ref([])
const pendingTotal = ref(0)
const pendingLoading = ref(false)
const expanded = ref(new Set())

const filters = reactive({ department: '', status: '', round: '', target_type: '', search: '' })
const departments = ref([])
let searchTimer = null

const downloading = ref(false)
const viewModal = reactive({ open: false, loading: false, data: null })
const reopenModal = reactive({ open: false, busy: false, error: '', target: null, reason: '' })

const detailColumns = [
  { key: 'evaluator', label: '평가자', sortable: true, width: '150px' },
  { key: 'evaluator_dept', label: '평가자 부서', width: '120px' },
  { key: 'target', label: '평가 대상', sortable: true },
  { key: 'target_type', label: '유형', align: 'center', width: '70px' },
  { key: 'round', label: '차수', align: 'center', width: '70px' },
  { key: 'progress', label: '진행률', sortable: true, width: '150px' },
  { key: 'status', label: '상태', align: 'center', width: '100px' },
  { key: 'submitted_at', label: '제출 시각', sortable: true, width: '140px' },
  { key: 'actions', label: '작업', align: 'end', width: '130px' },
]

const daysLeftLabel = computed(() => {
  const days = summary.value?.cycle?.days_left
  if (days === undefined || days === null) return ''
  if (days < 0) return `마감 ${Math.abs(days)}일 경과`
  if (days === 0) return '오늘 마감'
  return `D-${days}`
})

const daysLeftClass = computed(() => {
  const days = summary.value?.cycle?.days_left
  if (days === undefined || days === null) return 'text-muted'
  return days <= 3 ? 'text-danger fw-semibold' : 'text-muted'
})

const overall = computed(() => summary.value?.overall)

function rate(bucket) {
  return Number(bucket?.rate ?? 0)
}

async function loadCycle() {
  const { data } = await fetchCycle(cycleId)
  cycle.value = data
}

async function loadDepartments() {
  const { data } = await fetchDepartments({ page_size: 200 })
  departments.value = data.results
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    const { data } = await api.fetchStatusSummary(cycleId)
    summary.value = data
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    summaryLoading.value = false
  }
}

function activeFilterParams() {
  const params = {}
  if (filters.department) params.department = filters.department
  if (filters.status) params.status = filters.status
  if (filters.round) params.round = filters.round
  if (filters.target_type) params.target_type = filters.target_type
  if (filters.search) params.search = filters.search
  return params
}

async function loadDetail() {
  detailLoading.value = true
  try {
    const { data } = await api.fetchStatusDetail(cycleId, {
      ...activeFilterParams(),
      page: detailPage.value,
      page_size: DETAIL_PAGE_SIZE,
      ordering: detailOrdering.value,
    })
    detailRows.value = data.results.map((row, index) => ({ ...row, _key: `${row.assignment_id}-${row.round}-${index}` }))
    detailTotal.value = data.count
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

async function loadPending() {
  pendingLoading.value = true
  try {
    const params = {}
    if (filters.department) params.department = filters.department
    if (filters.search) params.search = filters.search
    const { data } = await api.fetchStatusPending(cycleId, params)
    pendingRows.value = data.results
    pendingTotal.value = data.pending_total
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    pendingLoading.value = false
  }
}

function reloadCurrentTab() {
  if (tab.value === 'summary') loadSummary()
  else if (tab.value === 'detail') loadDetail()
  else loadPending()
}

watch(tab, reloadCurrentTab)
watch([detailPage, detailOrdering], () => {
  if (tab.value === 'detail') loadDetail()
})
watch(
  [() => filters.department, () => filters.status, () => filters.round, () => filters.target_type],
  () => {
    detailPage.value = 1
    reloadCurrentTab()
  }
)
watch(
  () => filters.search,
  () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      detailPage.value = 1
      reloadCurrentTab()
    }, 300)
  }
)

function resetFilters() {
  Object.assign(filters, { department: '', status: '', round: '', target_type: '', search: '' })
}

function togglePending(evaluatorId) {
  const next = new Set(expanded.value)
  if (next.has(evaluatorId)) next.delete(evaluatorId)
  else next.add(evaluatorId)
  expanded.value = next
}

/** 현재 탭과 필터에 맞는 CSV를 내려받는다. */
async function downloadCsv() {
  downloading.value = true
  try {
    const kind = tab.value === 'pending' ? 'pending' : 'responses'
    const params = kind === 'pending'
      ? Object.fromEntries(
          Object.entries({ department: filters.department, search: filters.search }).filter(
            ([, value]) => value
          )
        )
      : activeFilterParams()

    const filename = await downloadCycleCsv(cycleId, kind, params)
    toasts.success(`${filename} 다운로드를 시작했습니다.`)
  } catch (error) {
    toasts.error(extractErrorMessage(error, 'CSV 다운로드에 실패했습니다.'))
  } finally {
    downloading.value = false
  }
}

// ── 평가지 열람 / 반려 ──────────────────────────────────────
async function openView(responseId) {
  if (!responseId) return
  viewModal.open = true
  viewModal.loading = true
  viewModal.data = null
  try {
    const { data } = await api.fetchAdminResponse(responseId)
    viewModal.data = data
  } catch (error) {
    toasts.error(extractErrorMessage(error))
    viewModal.open = false
  } finally {
    viewModal.loading = false
  }
}

function askReopen(row) {
  reopenModal.target = row
  reopenModal.reason = ''
  reopenModal.error = ''
  reopenModal.open = true
}

async function submitReopen() {
  reopenModal.busy = true
  reopenModal.error = ''
  try {
    const { data } = await api.reopenResponse(reopenModal.target.response_id, reopenModal.reason)
    reopenModal.open = false
    toasts.success('평가지를 반려했습니다. 평가자가 다시 수정할 수 있습니다.')
    if (data.recalculation_required) {
      toasts.push('이미 산출된 점수가 있어 재산출이 필요합니다.', 'warning', 6000)
    }
    await Promise.all([loadSummary(), tab.value === 'detail' ? loadDetail() : loadPending()])
  } catch (error) {
    reopenModal.error = extractErrorMessage(error)
  } finally {
    reopenModal.busy = false
  }
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(async () => {
  await Promise.all([loadCycle(), loadDepartments(), loadSummary()])
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
        </h2>
      </div>
      <div class="d-flex align-items-center gap-3">
        <p v-if="summary" class="small mb-0" :class="daysLeftClass">
          마감 {{ summary.cycle.ends_on }} · {{ daysLeftLabel }}
        </p>
        <button
          v-if="tab !== 'summary'"
          class="btn btn-outline-success btn-sm"
          type="button"
          :disabled="downloading"
          @click="downloadCsv"
        >
          <span v-if="downloading" class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
          {{ tab === 'pending' ? '미응답자' : '응답상세' }} CSV
        </button>
      </div>
    </div>

    <ul class="nav nav-tabs">
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'summary' }" type="button" @click="tab = 'summary'">
          요약
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'detail' }" type="button" @click="tab = 'detail'">
          상세
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'pending' }" type="button" @click="tab = 'pending'">
          미응답자
          <span v-if="summary" class="badge text-bg-warning ms-1">
            {{ summary.overall.draft + summary.overall.not_started }}
          </span>
        </button>
      </li>
    </ul>

    <!-- ══ 요약 ══ -->
    <div v-if="tab === 'summary'" class="pt-3">
      <div v-if="summaryLoading" class="text-center py-5 text-muted">
        <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
        불러오는 중...
      </div>

      <template v-else-if="overall">
        <div class="row g-3 mb-3">
          <div class="col-12 col-lg-4">
            <div class="card shadow-sm h-100">
              <div class="card-body text-center">
                <DonutChart :value="Number(overall.submission_rate)" label="전체 제출률" />
                <p class="small text-muted mb-0 mt-2">
                  제출 {{ overall.submitted }} / 기대 {{ overall.total_responses }}건
                </p>
              </div>
            </div>
          </div>

          <div class="col-12 col-lg-8">
            <div class="row g-2 h-100">
              <div class="col-4">
                <div class="card shadow-sm h-100">
                  <div class="card-body py-3 text-center">
                    <p class="small text-muted mb-1">미시작</p>
                    <p class="h4 mb-0">{{ overall.not_started }}</p>
                  </div>
                </div>
              </div>
              <div class="col-4">
                <div class="card shadow-sm h-100">
                  <div class="card-body py-3 text-center">
                    <p class="small text-muted mb-1">임시저장</p>
                    <p class="h4 mb-0 text-warning">{{ overall.draft }}</p>
                  </div>
                </div>
              </div>
              <div class="col-4">
                <div class="card shadow-sm h-100">
                  <div class="card-body py-3 text-center">
                    <p class="small text-muted mb-1">제출완료</p>
                    <p class="h4 mb-0 text-success">{{ overall.submitted }}</p>
                  </div>
                </div>
              </div>

              <div class="col-12">
                <div class="card shadow-sm h-100">
                  <div class="card-body">
                    <h3 class="h6 mb-3">차수별 · 유형별 제출률</h3>
                    <div v-for="(bucket, key) in summary.by_round" :key="`r-${key}`" class="mb-2">
                      <div class="d-flex justify-content-between small mb-1">
                        <span>{{ key === 'PRIMARY' ? '1차 평가' : '2차 평가' }}</span>
                        <span class="text-muted">{{ bucket.submitted }} / {{ bucket.total }}</span>
                      </div>
                      <ProgressBar :value="rate(bucket)" show-label />
                    </div>
                    <div
                      v-for="(bucket, key) in summary.by_target_type"
                      :key="`t-${key}`"
                      class="mb-2"
                    >
                      <div class="d-flex justify-content-between small mb-1">
                        <span>{{ key === 'EMPLOYEE' ? '개인 평가' : '부서 평가' }}</span>
                        <span class="text-muted">{{ bucket.submitted }} / {{ bucket.total }}</span>
                      </div>
                      <ProgressBar :value="rate(bucket)" show-label />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card shadow-sm">
          <div class="card-header bg-white d-flex justify-content-between align-items-center">
            <h3 class="h6 mb-0">부서별 제출률</h3>
            <span class="small text-muted">평가자 소속 부서 기준 · 낮은 순</span>
          </div>
          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th scope="col">부서</th>
                  <th scope="col" class="text-center" style="width: 80px">기대</th>
                  <th scope="col" class="text-center" style="width: 80px">미시작</th>
                  <th scope="col" class="text-center" style="width: 80px">임시</th>
                  <th scope="col" class="text-center" style="width: 80px">제출</th>
                  <th scope="col" style="width: 200px">제출률</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="summary.by_department.length === 0">
                  <td colspan="6" class="text-center py-4 text-muted">배정된 평가가 없습니다.</td>
                </tr>
                <tr v-for="row in summary.by_department" :key="row.department_id ?? 'none'">
                  <td>{{ row.department_name }}</td>
                  <td class="text-center">{{ row.total }}</td>
                  <td class="text-center">{{ row.not_started }}</td>
                  <td class="text-center text-warning">{{ row.draft }}</td>
                  <td class="text-center text-success">{{ row.submitted }}</td>
                  <td><ProgressBar :value="rate(row)" show-label /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>

    <!-- ══ 상세 / 미응답자 공통 필터 ══ -->
    <template v-if="tab !== 'summary'">
      <div class="card shadow-sm border-top-0 rounded-top-0">
        <div class="card-body py-3 border-bottom">
          <div class="row g-2 align-items-end">
            <div class="col-6 col-md-3">
              <label class="form-label small mb-1" for="f-dept">평가자 부서</label>
              <select id="f-dept" v-model="filters.department" class="form-select form-select-sm">
                <option value="">전체</option>
                <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
              </select>
            </div>

            <template v-if="tab === 'detail'">
              <div class="col-6 col-md-2">
                <label class="form-label small mb-1" for="f-status">상태</label>
                <select id="f-status" v-model="filters.status" class="form-select form-select-sm">
                  <option value="">전체</option>
                  <option value="NOT_STARTED">미시작</option>
                  <option value="DRAFT">임시저장</option>
                  <option value="SUBMITTED">제출완료</option>
                  <option value="NOT_STARTED,DRAFT">미제출(미시작+임시)</option>
                </select>
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label small mb-1" for="f-round">차수</label>
                <select id="f-round" v-model="filters.round" class="form-select form-select-sm">
                  <option value="">전체</option>
                  <option value="PRIMARY">1차</option>
                  <option value="SECONDARY">2차</option>
                </select>
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label small mb-1" for="f-type">대상 유형</label>
                <select id="f-type" v-model="filters.target_type" class="form-select form-select-sm">
                  <option value="">전체</option>
                  <option value="EMPLOYEE">개인</option>
                  <option value="DEPARTMENT">부서</option>
                </select>
              </div>
            </template>

            <div :class="tab === 'detail' ? 'col-10 col-md-2' : 'col-10 col-md-6'">
              <label class="form-label small mb-1" for="f-search">검색</label>
              <input
                id="f-search"
                v-model="filters.search"
                type="search"
                class="form-control form-control-sm"
                placeholder="평가자명 · 사번"
              />
            </div>
            <div class="col-2 col-md-1 d-grid">
              <button class="btn btn-light btn-sm" type="button" @click="resetFilters">초기화</button>
            </div>
          </div>
        </div>

        <!-- ══ 상세 ══ -->
        <div v-if="tab === 'detail'" class="card-body p-3">
          <DataTable
            v-model:page="detailPage"
            v-model:ordering="detailOrdering"
            :columns="detailColumns"
            :rows="detailRows"
            :loading="detailLoading"
            :page-size="DETAIL_PAGE_SIZE"
            :total="detailTotal"
            row-key="_key"
            empty-text="조건에 해당하는 응답이 없습니다."
          >
            <template #cell-evaluator="{ row }">
              {{ row.evaluator.name }}
              <span class="text-muted small">{{ row.evaluator.employee_no }}</span>
            </template>
            <template #cell-evaluator_dept="{ row }">
              <span class="small">{{ row.evaluator.department_name ?? '미배정' }}</span>
            </template>
            <template #cell-target="{ row }">
              {{ row.target.name }}
              <span class="text-muted small">{{ row.target.employee_no ?? row.target.code }}</span>
            </template>
            <template #cell-target_type="{ row }">
              <span class="small">{{ row.target_type === 'EMPLOYEE' ? '개인' : '부서' }}</span>
            </template>
            <template #cell-round="{ row }">
              <span class="small">{{ row.round === 'PRIMARY' ? '1차' : '2차' }}</span>
            </template>
            <template #cell-progress="{ row }">
              <ProgressBar
                :value="row.progress"
                :answered="row.answered_count"
                :total="row.total_items"
                show-label
                show-count
              />
            </template>
            <template #cell-status="{ row }">
              <StatusBadge :status="row.status" />
            </template>
            <template #cell-submitted_at="{ row }">
              <span class="small">{{ formatDateTime(row.submitted_at) }}</span>
            </template>
            <template #cell-actions="{ row }">
              <button
                class="btn btn-outline-secondary btn-sm me-1"
                type="button"
                :disabled="!row.response_id"
                @click="openView(row.response_id)"
              >
                보기
              </button>
              <button
                v-if="row.status === 'SUBMITTED'"
                class="btn btn-outline-warning btn-sm"
                type="button"
                @click="askReopen(row)"
              >
                반려
              </button>
            </template>
          </DataTable>
        </div>

        <!-- ══ 미응답자 ══ -->
        <div v-else class="card-body p-0">
          <div v-if="pendingLoading" class="text-center py-5 text-muted">
            <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
            불러오는 중...
          </div>

          <template v-else>
            <div class="px-3 py-2 border-bottom small text-muted">
              미응답 평가자 <strong>{{ pendingRows.length }}</strong>명 ·
              미응답 건수 <strong class="text-warning">{{ pendingTotal }}</strong>건
              <span class="ms-2">(미응답 건수 많은 순)</span>
            </div>

            <div v-if="pendingRows.length === 0" class="text-center py-5 text-muted">
              🎉 모든 평가가 제출되었습니다.
            </div>

            <ul v-else class="list-group list-group-flush">
              <li v-for="group in pendingRows" :key="group.evaluator.id" class="list-group-item">
                <div class="d-flex justify-content-between align-items-center gap-2">
                  <div>
                    <strong>{{ group.evaluator.name }}</strong>
                    <span class="text-muted small">
                      {{ group.evaluator.employee_no }}
                      · {{ group.evaluator.department_name ?? '부서 미배정' }}
                    </span>
                  </div>
                  <div class="d-flex align-items-center gap-2">
                    <span class="badge text-bg-secondary">미시작 {{ group.not_started }}</span>
                    <span class="badge text-bg-warning">임시 {{ group.draft }}</span>
                    <span class="badge text-bg-danger">총 {{ group.pending_count }}</span>
                    <button
                      class="btn btn-sm btn-outline-secondary"
                      type="button"
                      @click="togglePending(group.evaluator.id)"
                    >
                      {{ expanded.has(group.evaluator.id) ? '접기' : '대상 보기' }}
                    </button>
                  </div>
                </div>

                <table v-if="expanded.has(group.evaluator.id)" class="table table-sm mt-3 mb-0">
                  <thead class="table-light">
                    <tr>
                      <th scope="col">평가 대상</th>
                      <th scope="col" class="text-center" style="width: 70px">유형</th>
                      <th scope="col" class="text-center" style="width: 70px">차수</th>
                      <th scope="col" style="width: 150px">진행률</th>
                      <th scope="col" class="text-center" style="width: 100px">상태</th>
                      <th scope="col" class="text-end" style="width: 80px">작업</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(target, i) in group.pending_targets" :key="i">
                      <td>{{ target.target_name }}</td>
                      <td class="text-center small">
                        {{ target.target_type === 'EMPLOYEE' ? '개인' : '부서' }}
                      </td>
                      <td class="text-center small">
                        {{ target.round === 'PRIMARY' ? '1차' : '2차' }}
                      </td>
                      <td><ProgressBar :value="target.progress" show-label /></td>
                      <td class="text-center"><StatusBadge :status="target.status" /></td>
                      <td class="text-end">
                        <button
                          class="btn btn-outline-secondary btn-sm"
                          type="button"
                          :disabled="!target.response_id"
                          @click="openView(target.response_id)"
                        >
                          보기
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </li>
            </ul>
          </template>
        </div>
      </div>
    </template>

    <!-- 평가지 열람 -->
    <BaseModal v-model="viewModal.open" title="평가지 열람" size="modal-lg" hide-footer>
      <div v-if="viewModal.loading" class="text-center py-4 text-muted">
        <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
        불러오는 중...
      </div>

      <template v-else-if="viewModal.data">
        <dl class="row small mb-3">
          <dt class="col-3">평가자</dt>
          <dd class="col-9">
            {{ viewModal.data.evaluator.name }} ({{ viewModal.data.evaluator.employee_no }})
            <span class="text-muted">
              {{ viewModal.data.evaluator.department_name ?? '부서 미배정' }}
            </span>
          </dd>
          <dt class="col-3">평가 대상</dt>
          <dd class="col-9">{{ viewModal.data.target.name }}</dd>
          <dt class="col-3">차수 · 상태</dt>
          <dd class="col-9">
            {{ viewModal.data.round_display }}
            <StatusBadge :status="viewModal.data.status" class="ms-1" />
            <span class="text-muted ms-2">
              {{ viewModal.data.answered_count }}/{{ viewModal.data.total_items }} 응답
            </span>
          </dd>
          <dt v-if="viewModal.data.submitted_at" class="col-3">제출 시각</dt>
          <dd v-if="viewModal.data.submitted_at" class="col-9">
            {{ formatDateTime(viewModal.data.submitted_at) }}
          </dd>
        </dl>

        <table class="table table-sm">
          <thead class="table-light">
            <tr>
              <th scope="col">문항</th>
              <th scope="col" class="text-end" style="width: 80px">가중치</th>
              <th scope="col" class="text-center" style="width: 80px">점수</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in viewModal.data.items" :key="item.id">
              <td>
                {{ item.title }}
                <div v-if="item.answer.comment" class="small text-muted">
                  “{{ item.answer.comment }}”
                </div>
              </td>
              <td class="text-end">{{ Number(item.weight).toFixed(0) }}%</td>
              <td class="text-center">
                <span v-if="item.answer.score !== null" class="badge text-bg-primary">
                  {{ item.answer.score }} / {{ item.max_score }}
                </span>
                <span v-else class="text-muted small">미응답</span>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="viewModal.data.overall_comment" class="mt-3">
          <p class="small text-muted mb-1">종합 의견</p>
          <p class="mb-0 small">{{ viewModal.data.overall_comment }}</p>
        </div>

        <div class="d-flex justify-content-end mt-4">
          <button class="btn btn-light btn-sm" type="button" @click="viewModal.open = false">
            닫기
          </button>
        </div>
      </template>
    </BaseModal>

    <!-- 반려 -->
    <BaseModal
      v-model="reopenModal.open"
      title="평가지 반려"
      :busy="reopenModal.busy"
      confirm-text="반려"
      confirm-variant="warning"
      @confirm="submitReopen"
    >
      <div v-if="reopenModal.error" class="alert alert-danger py-2 small">
        {{ reopenModal.error }}
      </div>

      <p class="mb-3">
        <strong>{{ reopenModal.target?.evaluator.name }}</strong>님이 제출한
        <strong>{{ reopenModal.target?.target.name }}</strong> 평가를 반려합니다.
        <br />
        <span class="text-muted small">
          평가지가 임시저장 상태로 돌아가며, 평가자가 다시 수정·제출할 수 있습니다.
          입력한 답변은 보존됩니다.
        </span>
      </p>

      <label class="form-label" for="reopen-reason">반려 사유 (선택)</label>
      <textarea
        id="reopen-reason"
        v-model="reopenModal.reason"
        class="form-control"
        rows="3"
        placeholder="평가 기준 재안내에 따른 재작성 요청"
      />
    </BaseModal>
  </div>
</template>
