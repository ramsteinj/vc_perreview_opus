<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { extractErrorMessage } from '@/api/client'
import * as api from '@/api/my'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toasts = useToastStore()
const router = useRouter()

const cycle = ref(null)
const summary = ref({ total: 0, submitted: 0, draft: 0, not_started: 0 })
const rows = ref([])
const loading = ref(true)
const opening = ref(null)

const daysLeft = computed(() => {
  if (!cycle.value?.ends_on) return null
  const end = new Date(`${cycle.value.ends_on}T23:59:59`)
  return Math.ceil((end - new Date()) / (1000 * 60 * 60 * 24))
})

const deadlineClass = computed(() => {
  if (daysLeft.value === null) return 'text-muted'
  if (daysLeft.value < 0) return 'text-danger fw-semibold'
  if (daysLeft.value <= 3) return 'text-danger fw-semibold'
  return 'text-muted'
})

const overallProgress = computed(() => {
  if (!summary.value.total) return 0
  return Math.floor((summary.value.submitted / summary.value.total) * 100)
})

async function load() {
  loading.value = true
  try {
    const { data } = await api.fetchMyAssignments()
    cycle.value = data.cycle
    summary.value = data.summary
    rows.value = data.results
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

/** 평가지가 없으면 먼저 만든 뒤 작성 화면으로 이동한다. */
async function openForm(row) {
  if (row.response_id) {
    router.push({ name: 'my-evaluation-form', params: { id: row.response_id } })
    return
  }

  opening.value = row.assignment_id
  try {
    const { data } = await api.createResponse(row.assignment_id)
    router.push({ name: 'my-evaluation-form', params: { id: data.id } })
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    opening.value = null
  }
}

function actionLabel(row) {
  if (!row.editable) return '보기'
  return row.status === 'NOT_STARTED' ? '평가하기' : '이어서 작성'
}

onMounted(load)
</script>

<template>
  <div>
    <div v-if="loading" class="text-center py-5 text-muted">
      <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
      불러오는 중...
    </div>

    <template v-else>
      <!-- 진행 중 회차가 없을 때 -->
      <div v-if="!cycle" class="card shadow-sm">
        <div class="card-body text-center py-5">
          <p class="h5 mb-2">진행 중인 평가가 없습니다</p>
          <p class="text-muted mb-0">
            배정된 평가가 있으면 이곳에 표시됩니다.
            <br />
            <span class="small">{{ auth.user?.name }}님 · 사번 {{ auth.user?.employee_no }}</span>
          </p>
        </div>
      </div>

      <template v-else>
        <!-- 회차 헤더 -->
        <div class="card shadow-sm mb-3">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
              <div>
                <h2 class="h6 mb-1">{{ cycle.name }}</h2>
                <p class="small mb-0" :class="deadlineClass">
                  마감 {{ cycle.ends_on }}
                  <template v-if="daysLeft !== null">
                    ·
                    <template v-if="daysLeft < 0">마감됨</template>
                    <template v-else-if="daysLeft === 0">오늘 마감</template>
                    <template v-else>D-{{ daysLeft }}</template>
                  </template>
                </p>
              </div>
              <div class="text-end">
                <p class="mb-1 small text-muted">
                  제출 완료 <strong class="text-success">{{ summary.submitted }}</strong> /
                  전체 {{ summary.total }}
                </p>
                <ProgressBar :value="overallProgress" style="min-width: 180px" />
              </div>
            </div>
          </div>
        </div>

        <!-- 요약 카드 -->
        <div class="row g-2 mb-3">
          <div class="col-4">
            <div class="card shadow-sm h-100">
              <div class="card-body py-2 text-center">
                <p class="small text-muted mb-0">미시작</p>
                <p class="h5 mb-0">{{ summary.not_started }}</p>
              </div>
            </div>
          </div>
          <div class="col-4">
            <div class="card shadow-sm h-100">
              <div class="card-body py-2 text-center">
                <p class="small text-muted mb-0">임시저장</p>
                <p class="h5 mb-0 text-warning">{{ summary.draft }}</p>
              </div>
            </div>
          </div>
          <div class="col-4">
            <div class="card shadow-sm h-100">
              <div class="card-body py-2 text-center">
                <p class="small text-muted mb-0">제출완료</p>
                <p class="h5 mb-0 text-success">{{ summary.submitted }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 목록 -->
        <div class="card shadow-sm">
          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th scope="col">평가 대상</th>
                  <th scope="col" class="text-center" style="width: 90px">유형</th>
                  <th scope="col" class="text-center" style="width: 70px">차수</th>
                  <th scope="col" style="width: 180px">진행률</th>
                  <th scope="col" class="text-center" style="width: 100px">상태</th>
                  <th scope="col" class="text-end" style="width: 130px">작업</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="rows.length === 0">
                  <td colspan="6" class="text-center py-5 text-muted">
                    배정된 평가 대상이 없습니다.
                  </td>
                </tr>
                <tr v-for="row in rows" :key="`${row.assignment_id}-${row.round}`">
                  <td>
                    {{ row.target.name }}
                    <span class="text-muted small">
                      {{ row.target.employee_no ?? row.target.code }}
                      <template v-if="row.target.department_name">
                        · {{ row.target.department_name }}
                      </template>
                    </span>
                  </td>
                  <td class="text-center small">
                    {{ row.target_type === 'EMPLOYEE' ? '개인' : '부서' }}
                  </td>
                  <td class="text-center small">{{ row.round === 'PRIMARY' ? '1차' : '2차' }}</td>
                  <td>
                    <ProgressBar
                      :value="row.progress"
                      :answered="row.answered_count"
                      :total="row.total_items"
                      show-label
                      show-count
                    />
                  </td>
                  <td class="text-center">
                    <StatusBadge :status="row.status" />
                  </td>
                  <td class="text-end">
                    <button
                      class="btn btn-sm"
                      :class="row.editable ? 'btn-primary' : 'btn-outline-secondary'"
                      type="button"
                      :disabled="opening === row.assignment_id"
                      @click="openForm(row)"
                    >
                      <span
                        v-if="opening === row.assignment_id"
                        class="spinner-border spinner-border-sm"
                        aria-hidden="true"
                      />
                      <template v-else>{{ actionLabel(row) }}</template>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>
