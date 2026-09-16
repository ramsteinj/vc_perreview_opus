import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', redirect: () => ({ name: 'login' }) },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, layout: 'blank' },
  },
  {
    path: '/my/evaluations',
    name: 'my-evaluations',
    component: () => import('@/views/employee/MyAssignmentsView.vue'),
    meta: { title: '내 평가' },
  },
  {
    path: '/my/evaluations/:id',
    name: 'my-evaluation-form',
    component: () => import('@/views/employee/EvaluationFormView.vue'),
    meta: { title: '평가 작성' },
  },
  {
    path: '/admin',
    component: () => import('@/components/AdminLayout.vue'),
    meta: { role: 'ADMIN' },
    children: [
      { path: '', redirect: () => ({ name: 'admin-dashboard' }) },
      {
        path: 'dashboard',
        name: 'admin-dashboard',
        component: () => import('@/views/admin/DashboardView.vue'),
        meta: { role: 'ADMIN', title: '대시보드' },
      },
      {
        path: 'departments',
        name: 'admin-departments',
        component: () => import('@/views/admin/DepartmentListView.vue'),
        meta: { role: 'ADMIN', title: '부서 관리' },
      },
      {
        path: 'users',
        name: 'admin-users',
        component: () => import('@/views/admin/UserListView.vue'),
        meta: { role: 'ADMIN', title: '사용자 관리' },
      },
      {
        path: 'cycles',
        name: 'admin-cycles',
        component: () => import('@/views/admin/CycleListView.vue'),
        meta: { role: 'ADMIN', title: '평가 회차' },
      },
      {
        path: 'cycles/:id/items',
        name: 'admin-cycle-items',
        component: () => import('@/views/admin/ItemEditorView.vue'),
        meta: { role: 'ADMIN', title: '평가 항목 · 가중치' },
      },
      {
        path: 'cycles/:id/assignments',
        name: 'admin-cycle-assignments',
        component: () => import('@/views/admin/AssignmentEditorView.vue'),
        meta: { role: 'ADMIN', title: '평가자 배정' },
      },
      {
        path: 'cycles/:id/status',
        name: 'admin-cycle-status',
        component: () => import('@/views/admin/ResponseStatusView.vue'),
        meta: { role: 'ADMIN', title: '응답 현황' },
      },
    ],
  },
  {
    path: '/account/password',
    name: 'change-password',
    component: () => import('@/views/ChangePasswordView.vue'),
    meta: { title: '비밀번호 변경' },
  },
  {
    path: '/403',
    name: 'forbidden',
    component: () => import('@/views/ForbiddenView.vue'),
    meta: { public: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { public: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/** 로그인 직후 역할에 따라 이동할 기본 경로. */
export function homeRouteFor(user) {
  return user?.role === 'ADMIN' ? { name: 'admin-dashboard' } : { name: 'my-evaluations' }
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // 새로고침 직후에는 저장된 refresh 토큰으로 세션 복구를 먼저 끝낸다
  if (!auth.restored) {
    await auth.restore()
  }

  if (to.meta.public) {
    // 이미 로그인한 사용자가 로그인 화면으로 오면 홈으로 보낸다
    if (to.name === 'login' && auth.isAuthenticated) {
      return homeRouteFor(auth.user)
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } }
  }

  if (to.meta.role === 'ADMIN' && !auth.isAdmin) {
    return { name: 'forbidden' }
  }

  return true
})

export default router
