<script setup>
const navGroups = [
  {
    label: '현황',
    items: [{ name: 'admin-dashboard', label: '대시보드', icon: '📊', ready: true }],
  },
  {
    label: '마스터 데이터',
    items: [
      { name: 'admin-departments', label: '부서 관리', icon: '🏢', ready: true },
      { name: 'admin-users', label: '사용자 관리', icon: '👥', ready: true },
    ],
  },
  {
    label: '평가 운영',
    items: [
      { name: 'admin-cycles', label: '평가 회차', icon: '🗓️', ready: true },
    ],
  },
]
</script>

<template>
  <div class="row g-4">
    <aside class="col-12 col-lg-3 col-xl-2">
      <nav class="list-group shadow-sm sticky-lg-top" style="top: 1rem">
        <template v-for="group in navGroups" :key="group.label">
          <div class="list-group-item bg-light py-1 small text-muted fw-semibold">
            {{ group.label }}
          </div>

          <template v-for="item in group.items" :key="item.label">
            <RouterLink
              v-if="item.ready"
              class="list-group-item list-group-item-action d-flex align-items-center gap-2"
              :to="{ name: item.name }"
            >
              <span aria-hidden="true">{{ item.icon }}</span>
              {{ item.label }}
            </RouterLink>

            <span
              v-else
              class="list-group-item d-flex align-items-center gap-2 text-muted"
              :title="`${item.phase}에서 구현됩니다`"
            >
              <span aria-hidden="true">{{ item.icon }}</span>
              {{ item.label }}
              <span class="badge text-bg-light ms-auto">{{ item.phase }}</span>
            </span>
          </template>
        </template>
      </nav>
    </aside>

    <section class="col-12 col-lg-9 col-xl-10">
      <RouterView />
    </section>
  </div>
</template>
