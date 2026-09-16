<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toasts = useToastStore()
const router = useRouter()
const route = useRoute()

const navItems = computed(() => {
  if (auth.isAdmin) {
    return [
      { name: 'admin-dashboard', label: '대시보드', icon: '📊' },
      { name: 'admin-departments', label: '부서', icon: '🏢' },
      { name: 'admin-users', label: '사용자', icon: '👥' },
      { name: 'admin-cycles', label: '평가 회차', icon: '🗓️' },
    ]
  }
  return [{ name: 'my-evaluations', label: '내 평가', icon: '📝' }]
})

const pageTitle = computed(() => route.meta.title ?? '인사평가 시스템')

async function handleLogout() {
  await auth.logout()
  toasts.success('로그아웃되었습니다.')
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="d-flex flex-column min-vh-100">
    <nav class="navbar navbar-expand navbar-dark bg-dark">
      <div class="container-fluid">
        <span class="navbar-brand mb-0 h1">인사평가 시스템</span>

        <ul class="navbar-nav me-auto">
          <li v-for="item in navItems" :key="item.name" class="nav-item">
            <RouterLink class="nav-link" :to="{ name: item.name }">
              {{ item.icon }} {{ item.label }}
            </RouterLink>
          </li>
        </ul>

        <div class="dropdown">
          <button
            class="btn btn-outline-light btn-sm dropdown-toggle"
            type="button"
            data-bs-toggle="dropdown"
            aria-expanded="false"
          >
            {{ auth.user?.name }}
            <span class="badge ms-1" :class="auth.isAdmin ? 'text-bg-warning' : 'text-bg-secondary'">
              {{ auth.isAdmin ? '관리자' : '직원' }}
            </span>
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li>
              <span class="dropdown-item-text small text-muted">
                사번 {{ auth.user?.employee_no }}
                <template v-if="auth.user?.department">
                  · {{ auth.user.department.name }}
                </template>
              </span>
            </li>
            <li><hr class="dropdown-divider" /></li>
            <li>
              <RouterLink class="dropdown-item" :to="{ name: 'change-password' }">
                비밀번호 변경
              </RouterLink>
            </li>
            <li>
              <button class="dropdown-item text-danger" type="button" @click="handleLogout">
                로그아웃
              </button>
            </li>
          </ul>
        </div>
      </div>
    </nav>

    <div
      v-if="auth.passwordIsDefault"
      class="alert alert-warning alert-dismissible rounded-0 mb-0 border-0"
      role="alert"
    >
      <strong>기본 비밀번호를 사용 중입니다.</strong>
      보안을 위해
      <RouterLink :to="{ name: 'change-password' }" class="alert-link">
        지금 비밀번호를 변경
      </RouterLink>
      하세요.
    </div>

    <main class="flex-grow-1 container-fluid py-4">
      <h1 class="h4 mb-4">{{ pageTitle }}</h1>
      <slot />
    </main>

    <footer class="border-top py-3 text-center text-muted small bg-white">
      인사평가 시스템
    </footer>
  </div>
</template>
