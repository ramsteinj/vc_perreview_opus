<script setup>
import { onMounted, ref } from 'vue'

import * as adminApi from '@/api/admin'
import { extractErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toasts = useToastStore()

const stats = ref({ users: null, activeUsers: null, admins: null, departments: null })
const loading = ref(true)

const upcoming = [
  { phase: 'Phase 6', title: '부서 성과 점수 · 최종 점수 산출', spec: 'FR-A-08~09' },
  { phase: 'Phase 7', title: 'CSV 다운로드', spec: 'FR-A-07' },
]

onMounted(async () => {
  try {
    const [all, active, admins, departments] = await Promise.all([
      adminApi.fetchUsers({ page_size: 1 }),
      adminApi.fetchUsers({ page_size: 1, is_active: true }),
      adminApi.fetchUsers({ page_size: 1, role: 'ADMIN' }),
      adminApi.fetchDepartments({ page_size: 1 }),
    ])
    stats.value = {
      users: all.data.count,
      activeUsers: active.data.count,
      admins: admins.data.count,
      departments: departments.data.count,
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
    <div class="alert alert-success" role="alert">
      <strong>{{ auth.user?.name }}</strong> 관리자로 로그인했습니다.
    </div>

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

    <div class="row g-3">
      <div class="col-12 col-xl-6">
        <div class="card shadow-sm h-100">
          <div class="card-header bg-white"><h2 class="h6 mb-0">바로가기</h2></div>
          <div class="list-group list-group-flush">
            <RouterLink class="list-group-item list-group-item-action" :to="{ name: 'admin-departments' }">
              🏢 부서 관리 <span class="text-muted small">조직도 구성</span>
            </RouterLink>
            <RouterLink class="list-group-item list-group-item-action" :to="{ name: 'admin-users' }">
              👥 사용자 관리 <span class="text-muted small">계정 등록·수정</span>
            </RouterLink>
            <RouterLink class="list-group-item list-group-item-action" :to="{ name: 'admin-cycles' }">
              🗓️ 평가 회차 <span class="text-muted small">항목·가중치·평가자 배정</span>
            </RouterLink>
          </div>
        </div>
      </div>

      <div class="col-12 col-xl-6">
        <div class="card shadow-sm h-100">
          <div class="card-header bg-white"><h2 class="h6 mb-0">다음 구현 단계</h2></div>
          <ul class="list-group list-group-flush">
            <li
              v-for="item in upcoming"
              :key="item.phase"
              class="list-group-item d-flex justify-content-between align-items-center gap-2"
            >
              <div>
                <span class="badge text-bg-secondary me-2">{{ item.phase }}</span>
                <span class="small">{{ item.title }}</span>
              </div>
              <code class="small text-muted text-nowrap">{{ item.spec }}</code>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>
