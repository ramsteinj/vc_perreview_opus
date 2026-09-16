<script setup>
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const upcoming = [
  { phase: 'Phase 2', title: '부서 · 사용자 관리', spec: 'specs/05-admin-features.md · FR-A-02~03' },
  { phase: 'Phase 3', title: '평가 항목 · 가중치 · 평가자 배정', spec: 'FR-A-04~05' },
  { phase: 'Phase 5', title: '응답 현황 모니터링', spec: 'FR-A-06' },
  { phase: 'Phase 6', title: '부서 성과 점수 · 최종 점수 산출', spec: 'FR-A-08~09' },
  { phase: 'Phase 7', title: 'CSV 다운로드', spec: 'FR-A-07' },
]
</script>

<template>
  <div>
    <div class="alert alert-success" role="alert">
      <strong>{{ auth.user?.name }}</strong> 관리자로 로그인했습니다. Phase 1(인증 기반)이
      동작 중입니다.
    </div>

    <div class="card shadow-sm">
      <div class="card-header bg-white">
        <h2 class="h6 mb-0">다음 구현 단계</h2>
      </div>
      <ul class="list-group list-group-flush">
        <li
          v-for="item in upcoming"
          :key="item.phase"
          class="list-group-item d-flex justify-content-between align-items-center"
        >
          <div>
            <span class="badge text-bg-secondary me-2">{{ item.phase }}</span>
            {{ item.title }}
          </div>
          <code class="small text-muted">{{ item.spec }}</code>
        </li>
      </ul>
    </div>
  </div>
</template>
