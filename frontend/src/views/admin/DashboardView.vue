<script setup>
import { computed, onMounted, ref } from 'vue'

import * as adminApi from '@/api/admin'
import { extractErrorMessage } from '@/api/client'
import { fetchCycles } from '@/api/evaluations'
import { fetchStatusSummary } from '@/api/reports'
import DonutChart from '@/components/DonutChart.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toasts = useToastStore()

const stats = ref({ users: null, activeUsers: null, admins: null, departments: null })
const cycles = ref([])
const activeCycle = ref(null)
const activeSummary = ref(null)
const loading = ref(true)

const daysLeft = computed(() => activeSummary.value?.cycle?.days_left ?? null)

const deadlineClass = computed(() => {
  if (daysLeft.value === null) return 'text-muted'
  if (daysLeft.value < 0) return 'text-danger fw-semibold'
  return daysLeft.value <= 3 ? 'text-danger fw-semibold' : 'text-muted'
})

const laggingDepartments = computed(() => (activeSummary.value?.by_department ?? []).slice(0, 5))

const pendingCount = computed(() => {
  const overall = activeSummary.value?.overall
  if (!overall) return 0
  return overall.draft + overall.not_started
})

onMounted(async () => {
  try {
    const [all, active, admins, departments, cycleList] = await Promise.all([
      adminApi.fetchUsers({ page_size: 1 }),
      adminApi.fetchUsers({ page_size: 1, is_active: true }),
      adminApi.fetchUsers({ page_size: 1, role: 'ADMIN' }),
      adminApi.fetchDepartments({ page_size: 1 }),
      fetchCycles({ page_size: 20 }),
    ])

    stats.value = {
      users: all.data.count,
      activeUsers: active.data.count,
      admins: admins.data.count,
      departments: departments.data.count,
    }
    cycles.value = cycleList.data.results

    // 진행 중 회차가 있으면 그 현황을, 없으면 가장 최근 회차를 보여준다
    const target =
      cycles.value.find((c) => c.status === 'OPEN') ??
      cycles.value.find((c) => c.status === 'CLOSED') ??
      null

    if (target) {
      activeCycle.value = target
      const { data } = await fetchStatusSummary(target.id)
      activeSummary.value = data
    }
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <p class="text-muted small mb-3">
      <strong>{{ auth.user?.name }}</strong> 관리자로 로그인했습니다.
    </p>

    <!-- 마스터 데이터 요약 -->
    <div class="row g-3 mb-4">
      <div class="col-6 col-lg-3">
        <div class="card shadow-sm h-100">
          <div class="card-body">
            <p class="text-muted small mb-1">전체 사용자</p>
            <p class="h3 mb-0">
              <span v-if="loading" class="placeholder col-4" />
              <template v-else>{{ stats.users }}</template>
            </p>
          </div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card shadow-sm h-100">
          <div class="card-body">
            <p class="text-muted small mb-1">재직 중</p>
            <p class="h3 mb-0 text-success">
              <span v-if="loading" class="placeholder col-4" />
              <template v-else>{{ stats.activeUsers }}</template>
            </p>
          </div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card shadow-sm h-100">
          <div class="card-body">
            <p class="text-muted small mb-1">관리자</p>
            <p class="h3 mb-0 text-warning">
              <span v-if="loading" class="placeholder col-4" />
              <template v-else>{{ stats.admins }}</template>
            </p>
          </div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card shadow-sm h-100">
          <div class="card-body">
            <p class="text-muted small mb-1">부서</p>
            <p class="h3 mb-0">
              <span v-if="loading" class="placeholder col-4" />
              <template v-else>{{ stats.departments }}</template>
            </p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="text-center py-5 text-muted">
      <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
      불러오는 중...
    </div>

    <!-- 회차가 하나도 없을 때 -->
    <div v-else-if="cycles.length === 0" class="card shadow-sm">
      <div class="card-body text-center py-5">
        <p class="h5 mb-2">등록된 평가 회차가 없습니다</p>
        <p class="text-muted mb-3">평가 회차를 만들고 항목·평가자를 설정하면 시작할 수 있습니다.</p>
        <RouterLink class="btn btn-primary" :to="{ name: 'admin-cycles' }">
          평가 회차 만들기
        </RouterLink>
      </div>
    </div>

    <template v-else>
      <!-- 현재 회차 현황 -->
      <div v-if="activeSummary" class="row g-3 mb-4">
        <div class="col-12 col-lg-4">
          <div class="card shadow-sm h-100">
            <div class="card-body text-center">
              <p class="small text-muted mb-1">{{ activeCycle.name }}</p>
              <StatusBadge :status="activeCycle.status" class="mb-3" />
              <DonutChart
                :value="Number(activeSummary.overall.submission_rate)"
                label="제출률"
              />
              <p class="small mb-1 mt-2">
                제출 {{ activeSummary.overall.submitted }} /
                기대 {{ activeSummary.overall.total_responses }}건
              </p>
              <p class="small mb-0" :class="deadlineClass">
                마감 {{ activeSummary.cycle.ends_on }}
                <template v-if="daysLeft !== null">
                  ·
                  <template v-if="daysLeft < 0">마감됨</template>
                  <template v-else-if="daysLeft === 0">오늘 마감</template>
                  <template v-else>D-{{ daysLeft }}</template>
                </template>
              </p>
            </div>
          </div>
        </div>

        <div class="col-12 col-lg-8">
          <div class="card shadow-sm h-100">
            <div class="card-header bg-white d-flex justify-content-between align-items-center">
              <h2 class="h6 mb-0">제출률이 낮은 부서</h2>
              <RouterLink
                class="small text-decoration-none"
                :to="{ name: 'admin-cycle-status', params: { id: activeCycle.id } }"
              >
                전체 현황 →
              </RouterLink>
            </div>
            <div class="card-body">
              <p v-if="laggingDepartments.length === 0" class="text-muted small mb-0">
                배정된 평가가 없습니다.
              </p>
              <div v-for="row in laggingDepartments" :key="row.department_id ?? 'none'" class="mb-3">
                <div class="d-flex justify-content-between small mb-1">
                  <span>{{ row.department_name }}</span>
                  <span class="text-muted">
                    {{ row.submitted }} / {{ row.total }}
                    <span v-if="row.not_started" class="ms-1">(미시작 {{ row.not_started }})</span>
                  </span>
                </div>
                <ProgressBar :value="Number(row.rate)" show-label />
              </div>
            </div>
            <div v-if="pendingCount > 0" class="card-footer bg-white">
              <RouterLink
                class="btn btn-outline-warning btn-sm"
                :to="{ name: 'admin-cycle-status', params: { id: activeCycle.id } }"
              >
                미응답 {{ pendingCount }}건 확인 →
              </RouterLink>
            </div>
          </div>
        </div>
      </div>

      <!-- 회차 목록 -->
      <div class="card shadow-sm">
        <div class="card-header bg-white d-flex justify-content-between align-items-center">
          <h2 class="h6 mb-0">평가 회차</h2>
          <RouterLink class="small text-decoration-none" :to="{ name: 'admin-cycles' }">
            관리 →
          </RouterLink>
        </div>
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th scope="col">회차</th>
                <th scope="col" class="text-center" style="width: 90px">상태</th>
                <th scope="col" style="width: 180px">응답 기간</th>
                <th scope="col" class="text-center" style="width: 80px">항목</th>
                <th scope="col" class="text-center" style="width: 80px">배정</th>
                <th scope="col" class="text-end" style="width: 200px">바로가기</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cycle in cycles" :key="cycle.id">
                <td>{{ cycle.name }}</td>
                <td class="text-center"><StatusBadge :status="cycle.status" /></td>
                <td class="small">{{ cycle.starts_on }} ~ {{ cycle.ends_on }}</td>
                <td class="text-center">{{ cycle.item_count }}</td>
                <td class="text-center">{{ cycle.assignment_count }}</td>
                <td class="text-end">
                  <RouterLink
                    v-if="cycle.status !== 'DRAFT'"
                    class="btn btn-outline-info btn-sm me-1"
                    :to="{ name: 'admin-cycle-status', params: { id: cycle.id } }"
                  >
                    현황
                  </RouterLink>
                  <RouterLink
                    v-if="cycle.status !== 'DRAFT'"
                    class="btn btn-outline-dark btn-sm"
                    :to="{ name: 'admin-cycle-scores', params: { id: cycle.id } }"
                  >
                    점수
                  </RouterLink>
                  <RouterLink
                    v-else
                    class="btn btn-outline-secondary btn-sm"
                    :to="{ name: 'admin-cycle-items', params: { id: cycle.id } }"
                  >
                    설정
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
