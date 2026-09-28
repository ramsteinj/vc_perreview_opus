<script setup>
import Pagination from './Pagination.vue'

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

    <Pagination
      class="mt-3"
      :page="page"
      :page-size="pageSize"
      :total="total"
      @update:page="emit('update:page', $event)"
    />
  </div>
</template>
