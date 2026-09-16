<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },
})

// 색상만으로 구분하지 않고 텍스트를 병기한다 (specs/08-frontend.md §7)
const meta = {
  NOT_STARTED: { label: '미시작', variant: 'secondary' },
  DRAFT: { label: '임시저장', variant: 'warning' },
  SUBMITTED: { label: '제출완료', variant: 'success' },
  OPEN: { label: '진행중', variant: 'success' },
  CLOSED: { label: '마감', variant: 'dark' },
}

const current = computed(() => meta[props.status] ?? { label: props.status, variant: 'light' })
</script>

<template>
  <span class="badge" :class="`text-bg-${current.variant}`">{{ current.label }}</span>
</template>
