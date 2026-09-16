<script setup>
import { computed } from 'vue'

import { homeRouteFor } from '@/router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const home = computed(() => (auth.isAuthenticated ? homeRouteFor(auth.user) : { name: 'login' }))
</script>

<template>
  <div class="d-flex flex-column justify-content-center align-items-center min-vh-100 text-center px-3">
    <p class="display-6 mb-2">404</p>
    <h1 class="h5 mb-3">페이지를 찾을 수 없습니다</h1>
    <RouterLink class="btn btn-primary" :to="home">돌아가기</RouterLink>
  </div>
</template>
