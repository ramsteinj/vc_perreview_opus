<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppLayout from '@/components/AppLayout.vue'
import ToastHost from '@/components/ToastHost.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

const useBlankLayout = computed(() => route.meta.layout === 'blank' || !auth.isAuthenticated)
</script>

<template>
  <div class="app-shell">
    <div v-if="auth.restoring" class="d-flex justify-content-center align-items-center vh-100">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">불러오는 중</span>
      </div>
    </div>

    <template v-else>
      <RouterView v-if="useBlankLayout" />
      <AppLayout v-else>
        <RouterView />
      </AppLayout>
    </template>

    <ToastHost />
  </div>
</template>
