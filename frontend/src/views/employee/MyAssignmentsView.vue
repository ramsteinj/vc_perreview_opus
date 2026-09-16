<script setup>
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div>
    <div class="card shadow-sm mb-4">
      <div class="card-body">
        <h2 class="h6 text-muted mb-3">내 정보</h2>
        <dl class="row mb-0 small">
          <dt class="col-sm-3">성명</dt>
          <dd class="col-sm-9">{{ auth.user?.name }}</dd>
          <dt class="col-sm-3">사번</dt>
          <dd class="col-sm-9">{{ auth.user?.employee_no }}</dd>
          <dt class="col-sm-3">부서</dt>
          <dd class="col-sm-9">{{ auth.user?.department?.name ?? '미배정' }}</dd>
          <dt class="col-sm-3">직위</dt>
          <dd class="col-sm-9">{{ auth.user?.position || '-' }}</dd>
        </dl>
      </div>
    </div>

    <div class="phase-placeholder p-4 text-center text-muted">
      <p class="mb-1">평가 대상 목록은 <strong>Phase 4</strong>에서 구현됩니다.</p>
      <p class="small mb-0">specs/04-employee-features.md · FR-E-02 ~ FR-E-06</p>
    </div>
  </div>
</template>
