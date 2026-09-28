<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 25 },
  total: { type: Number, default: 0 },
})

const emit = defineEmits(['update:page'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pageNumbers = computed(() => {
  const last = totalPages.value
  const start = Math.max(1, Math.min(props.page - 2, last - 4))
  const end = Math.min(last, start + 4)
  const result = []
  for (let i = start; i <= end; i += 1) result.push(i)
  return result
})

const rangeLabel = computed(() => {
  if (props.total === 0) return '0건'
  const from = (props.page - 1) * props.pageSize + 1
  const to = Math.min(props.page * props.pageSize, props.total)
  return `${from}–${to} / 총 ${props.total}건`
})

function goToPage(value) {
  if (value < 1 || value > totalPages.value || value === props.page) return
  emit('update:page', value)
}
</script>

<template>
  <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
    <span class="text-muted small">{{ rangeLabel }}</span>

    <nav v-if="totalPages > 1" aria-label="페이지 이동">
      <ul class="pagination pagination-sm mb-0">
        <li class="page-item" :class="{ disabled: page <= 1 }">
          <button class="page-link" type="button" @click="goToPage(page - 1)">이전</button>
        </li>
        <li
          v-for="number in pageNumbers"
          :key="number"
          class="page-item"
          :class="{ active: number === page }"
        >
          <button class="page-link" type="button" @click="goToPage(number)">{{ number }}</button>
        </li>
        <li class="page-item" :class="{ disabled: page >= totalPages }">
          <button class="page-link" type="button" @click="goToPage(page + 1)">다음</button>
        </li>
      </ul>
    </nav>
  </div>
</template>
