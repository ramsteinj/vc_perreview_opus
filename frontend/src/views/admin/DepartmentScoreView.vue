<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { extractErrorMessage } from '@/api/client'
import { downloadCycleCsv } from '@/api/download'
import { fetchCycle, updateCycle } from '@/api/evaluations'
import * as api from '@/api/reports'
import BaseModal from '@/components/BaseModal.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toasts = useToastStore()

const cycleId = Number(route.params.id)
const cycle = ref(null)
const rows = ref([])
const parameters = ref(null)
const loading = ref(true)
const recalculating = ref(false)
const downloading = ref(false)

const paramModal = reactive({
  open: false,
  busy: false,
  error: '',
  baseline: '',
  factor: '',
  limit: '',
})

const readOnly = computed(() => cycle.value?.status === 'CLOSED')
const unevaluated = computed(() => rows.value.filter((r) => !r.evaluated).length)

function fmt(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toFixed(2)
}

function signed(value) {
  const number = Number(value ?? 0)
  const sign = number > 0 ? '+' : ''
  return `${sign}${number.toFixed(2)}`
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
    const [cycleRes, scoresRes] = await Promise.all([
      fetchCycle(cycleId),
      api.fetchDepartmentScores(cycleId),
    ])
    cycle.value = cycleRes.data
    rows.value = scoresRes.data.results
    parameters.value = scoresRes.data.parameters
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function openParams() {
  paramModal.error = ''
  paramModal.baseline = parameters.value.baseline
  paramModal.factor = parameters.value.factor
  paramModal.limit = parameters.value.limit
  paramModal.open = true
}

async function submitParams() {
  paramModal.busy = true
  paramModal.error = ''
  try {
    await updateCycle(cycleId, {
      dept_baseline_score: paramModal.baseline,
      dept_adjust_factor: paramModal.factor,
      dept_adjust_limit: paramModal.limit,
    })
    paramModal.open = false
    toasts.success('가감 파라미터를 저장했습니다. 재계산하면 최종 점수에 반영됩니다.')
    await load()
  } catch (error) {
    paramModal.error = extractErrorMessage(error)
  } finally {
    paramModal.busy = false
  }
}

async function downloadCsv() {
  downloading.value = true
  try {
    const filename = await downloadCycleCsv(cycleId, 'scores')
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
    toasts.success(`재계산 완료 — 산출 ${data.calculated}명 / 전체 ${data.total_targets}명`)
    await load()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    recalculating.value = false
  }
}

onMounted(load)
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
      <div class="d-flex gap-2">
        <RouterLink
          class="btn btn-outline-secondary btn-sm"
          :to="{ name: 'admin-cycle-scores', params: { id: cycleId } }"
        >
          최종 점수 →
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

    <div v-if="loading" class="text-center py-5 text-muted">
      <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
      불러오는 중...
    </div>

    <template v-else>
      <div class="card shadow-sm">
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th scope="col">부서</th>
                <th scope="col" class="text-end" style="width: 100px">1차</th>
                <th scope="col" class="text-end" style="width: 100px">2차</th>
                <th scope="col" class="text-end" style="width: 110px">부서 점수</th>
                <th scope="col" class="text-end" style="width: 100px">가감</th>
                <th scope="col" class="text-center" style="width: 90px">인원</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="rows.length === 0">
                <td colspan="6" class="text-center py-5 text-muted">
                  부서 평가 배정이 없습니다. 부서 성과 가감이 적용되지 않습니다.
                </td>
              </tr>
              <tr v-for="row in rows" :key="row.department_id">
                <td>
                  {{ row.department_name }}
                  <code class="small text-muted">{{ row.department_code }}</code>
                  <span v-if="!row.evaluated" class="badge text-bg-warning ms-1">미평가 ⚠</span>
                </td>
                <td class="text-end">{{ fmt(row.primary_score) }}</td>
                <td class="text-end">{{ fmt(row.secondary_score) }}</td>
                <td class="text-end">
                  <template v-if="row.evaluated">
                    <strong>{{ fmt(row.department_score) }}</strong>
                  </template>
                  <template v-else-if="row.inherited_score !== null">
                    <span class="text-muted">{{ fmt(row.inherited_score) }}</span>
                    <span class="badge text-bg-light ms-1" title="상위 부서 점수를 상속">상속</span>
                  </template>
                  <template v-else>—</template>
                </td>
                <td class="text-end" :class="adjustClass(row.department_adjustment)">
                  {{ signed(row.department_adjustment) }}
                </td>
                <td class="text-center">{{ row.member_count }}명</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card-footer bg-white d-flex justify-content-between align-items-center flex-wrap gap-2">
          <span class="small text-muted">
            기준점 <strong>{{ fmt(parameters.baseline) }}</strong>
            · 계수 <strong>{{ fmt(parameters.factor) }}</strong>
            · 한도 <strong>±{{ fmt(parameters.limit) }}</strong>
          </span>
          <button
            class="btn btn-outline-secondary btn-sm"
            type="button"
            :disabled="readOnly"
            @click="openParams"
          >
            파라미터 수정
          </button>
        </div>
      </div>

      <div class="alert alert-light border mt-3 small mb-0">
        <p class="mb-1">
          <strong>가감</strong> = clamp((부서 점수 − 기준점) × 계수, −한도, +한도)
        </p>
        <p class="mb-0 text-muted">
          부서 평가지가 미제출인 부서는 가장 가까운 상위 부서 점수를 상속합니다.
          상속할 점수도 없으면 소속 직원의 가감은 0이 됩니다.
          <template v-if="unevaluated > 0">
            현재 미평가 부서 {{ unevaluated }}개.
          </template>
        </p>
      </div>
    </template>

    <BaseModal
      v-model="paramModal.open"
      title="부서 가감 파라미터 수정"
      :busy="paramModal.busy"
      confirm-text="저장"
      @confirm="submitParams"
    >
      <div v-if="paramModal.error" class="alert alert-danger py-2 small">
        {{ paramModal.error }}
      </div>

      <div class="row g-3">
        <div class="col-4">
          <label class="form-label" for="p-base">기준점</label>
          <input id="p-base" v-model="paramModal.baseline" type="number" step="0.01" class="form-control" />
        </div>
        <div class="col-4">
          <label class="form-label" for="p-factor">계수</label>
          <input id="p-factor" v-model="paramModal.factor" type="number" step="0.01" class="form-control" />
        </div>
        <div class="col-4">
          <label class="form-label" for="p-limit">한도 (±)</label>
          <input id="p-limit" v-model="paramModal.limit" type="number" step="0.01" class="form-control" />
        </div>
      </div>

      <p class="text-muted small mt-3 mb-0">
        저장 후 [재계산]을 눌러야 최종 점수에 반영됩니다.
      </p>
    </BaseModal>
  </div>
</template>
