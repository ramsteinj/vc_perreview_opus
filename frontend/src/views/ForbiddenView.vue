<script setup>
import { useAuthStore } from '@/stores/auth'
import { homeRouteFor } from '@/router'
import { computed } from 'vue'

const auth = useAuthStore()
const home = computed(() => (auth.isAuthenticated ? homeRouteFor(auth.user) : { name: 'login' }))
</script>

<template>
  <div class="d-flex flex-column justify-content-center align-items-center min-vh-100 text-center px-3">
    <p class="display-6 mb-2">403</p>
    <h1 class="h5 mb-3">접근 권한이 없습니다</h1>
    <p class="text-muted small mb-4">이 페이지를 볼 수 있는 권한이 계정에 없습니다.</p>
    <RouterLink class="btn btn-primary" :to="home">돌아가기</RouterLink>
  </div>
</template>
