<script setup>
import { computed } from 'vue'

const props = defineProps({
  columns: { type: Array, required: true }, // [{ key, label, sortable, align, width }]
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 25 },
  total: { type: Number, default: 0 },
  ordering: { type: String, default: '' },
  rowKey: { type: String, default: 'id' },
  emptyText: { type: String, default: '표시할 항목이 없습니다.' },
})

const emit = defineEmits(['update:page', 'update:ordering'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pageNumbers = computed(() => {
  const last = totalPages.value
  const current = props.page
  const start = Math.max(1, Math.min(current - 2, last - 4))
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

function sortIcon(column) {
  if (!column.sortable) return ''
  if (props.ordering === column.key) return '▲'
  if (props.ordering === `-${column.key}`) return '▼'
  return '↕'
}

function toggleSort(column) {
  if (!column.sortable) return
  const next = props.ordering === column.key ? `-${column.key}` : column.key
  emit('update:ordering', next)
}

function goToPage(value) {
  if (value < 1 || value > totalPages.value || value === props.page) return
  emit('update:page', value)
}
</script>

<template>
  <div>
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0 bg-white">
        <thead class="table-light">
          <tr>
            <th
              v-for="column in columns"
              :key="column.key"
              scope="col"
              :style="column.width ? { width: column.width } : null"
              :class="[
                column.align ? `text-${column.align}` : '',
                column.sortable ? 'user-select-none' : '',
              ]"
            >
              <button
                v-if="column.sortable"
                type="button"
                class="btn btn-link btn-sm p-0 text-decoration-none text-reset fw-semibold"
                @click="toggleSort(column)"
              >
                {{ column.label }}
                <span class="text-muted small">{{ sortIcon(column) }}</span>
              </button>
              <template v-else>{{ column.label }}</template>
            </th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length" class="text-center py-5 text-muted">
              <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
              불러오는 중...
            </td>
          </tr>

          <tr v-else-if="rows.length === 0">
            <td :colspan="columns.length" class="text-center py-5 text-muted">
              {{ emptyText }}
            </td>
          </tr>

          <tr v-for="row in loading ? [] : rows" :key="row[rowKey]">
            <td
              v-for="column in columns"
              :key="column.key"
              :class="column.align ? `text-${column.align}` : ''"
            >
              <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                {{ row[column.key] ?? '-' }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mt-3">
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
  </div>
</template>
