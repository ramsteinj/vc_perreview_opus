<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { extractErrorMessage } from '@/api/client'
import * as api from '@/api/evaluations'
import BaseModal from '@/components/BaseModal.vue'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toasts = useToastStore()

const cycleId = Number(route.params.id)
const cycle = ref(null)
const targetType = ref('EMPLOYEE')
const items = ref([])
const loading = ref(false)
const dragIndex = ref(null)

const editModal = reactive({ open: false, busy: false, error: '', mode: 'create', id: null })
const form = reactive({
  code: '',
  title: '',
  description: '',
  weight: '',
  max_score: 5,
  is_active: true,
})

const deleteModal = reactive({ open: false, busy: false, target: null })
const cloneModal = reactive({ open: false, busy: false, error: '', sourceCycle: '', replace: false })
const otherCycles = ref([])

const readOnly = computed(() => cycle.value?.status === 'CLOSED')

/** 활성 항목의 가중치 합계. 100이어야 회차를 OPEN할 수 있다. */
const weightSum = computed(() =>
  items.value
    .filter((item) => item.is_active)
    .reduce((sum, item) => sum + Number(item.weight ?? 0), 0)
)

const weightValid = computed(() => Math.abs(weightSum.value - 100) < 0.005)
const activeCount = computed(() => items.value.filter((i) => i.is_active).length)

async function loadCycle() {
  const { data } = await api.fetchCycle(cycleId)
  cycle.value = data
}

async function loadItems() {
  loading.value = true
  try {
    const { data } = await api.fetchItems({ cycle: cycleId, target_type: targetType.value })
    items.value = data
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadOtherCycles() {
  const { data } = await api.fetchCycles({ page_size: 100 })
  otherCycles.value = data.results.filter((c) => c.id !== cycleId)
}

watch(targetType, loadItems)

function openCreate() {
  editModal.mode = 'create'
  editModal.id = null
  editModal.error = ''
  Object.assign(form, {
    code: '',
    title: '',
    description: '',
    weight: '',
    max_score: 5,
    is_active: true,
  })
  editModal.open = true
}

function openEdit(item) {
  editModal.mode = 'edit'
  editModal.id = item.id
  editModal.error = ''
  Object.assign(form, {
    code: item.code,
    title: item.title,
    description: item.description ?? '',
    weight: item.weight,
    max_score: item.max_score,
    is_active: item.is_active,
  })
  editModal.open = true
}

async function submitEdit() {
  editModal.error = ''
  if (!form.code.trim() || !form.title.trim() || form.weight === '') {
    editModal.error = '코드, 문항, 가중치를 입력하세요.'
    return
  }

  editModal.busy = true
  try {
    const payload = {
      cycle: cycleId,
      target_type: targetType.value,
      code: form.code.trim(),
      title: form.title.trim(),
      description: form.description,
      weight: form.weight,
      max_score: form.max_score,
      is_active: form.is_active,
    }
    if (editModal.mode === 'create') {
      await api.createItem(payload)
      toasts.success('항목을 추가했습니다.')
    } else {
      await api.updateItem(editModal.id, payload)
      toasts.success('항목을 수정했습니다.')
    }
    editModal.open = false
    await loadItems()
  } catch (error) {
    editModal.error = extractErrorMessage(error)
  } finally {
    editModal.busy = false
  }
}

function askDelete(item) {
  deleteModal.target = item
  deleteModal.open = true
}

async function submitDelete() {
  deleteModal.busy = true
  try {
    await api.deleteItem(deleteModal.target.id)
    deleteModal.open = false
    toasts.success('항목을 삭제했습니다.')
    await loadItems()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    deleteModal.busy = false
  }
}

async function toggleActive(item) {
  try {
    await api.updateItem(item.id, { is_active: !item.is_active })
    await loadItems()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  }
}

// ── 드래그 정렬 ─────────────────────────────────────────────
function onDragStart(index) {
  if (readOnly.value) return
  dragIndex.value = index
}

function onDrop(index) {
  if (readOnly.value || dragIndex.value === null || dragIndex.value === index) return
  const next = [...items.value]
  const [moved] = next.splice(dragIndex.value, 1)
  next.splice(index, 0, moved)
  items.value = next
  dragIndex.value = null
  persistOrder()
}

async function persistOrder() {
  try {
    await api.reorderItems(
      cycleId,
      items.value.map((item) => item.id)
    )
    toasts.success('순서를 저장했습니다.')
    await loadItems()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
    await loadItems()
  }
}

// ── 복제 ────────────────────────────────────────────────────
function openClone() {
  cloneModal.error = ''
  cloneModal.sourceCycle = ''
  cloneModal.replace = false
  cloneModal.open = true
}

async function submitClone() {
  if (!cloneModal.sourceCycle) {
    cloneModal.error = '복제할 회차를 선택하세요.'
    return
  }
  cloneModal.busy = true
  cloneModal.error = ''
  try {
    const { data } = await api.cloneItems(cycleId, {
      source_cycle: cloneModal.sourceCycle,
      target_type: targetType.value,
      replace: cloneModal.replace,
    })
    cloneModal.open = false
    toasts.success(
      `${data.created}개 항목을 복제했습니다.` +
        (data.skipped.length ? ` (중복 ${data.skipped.length}개 제외)` : '')
    )
    await loadItems()
  } catch (error) {
    cloneModal.error = extractErrorMessage(error)
  } finally {
    cloneModal.busy = false
  }
}

onMounted(async () => {
  await Promise.all([loadCycle(), loadItems(), loadOtherCycles()])
})
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <div>
        <RouterLink :to="{ name: 'admin-cycles' }" class="small text-decoration-none">
          ← 회차 목록
        </RouterLink>
        <h2 class="h6 mb-0 mt-1">{{ cycle?.name }}</h2>
      </div>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-secondary btn-sm" type="button" :disabled="readOnly" @click="openClone">
          다른 회차에서 복제
        </button>
        <button class="btn btn-primary btn-sm" type="button" :disabled="readOnly" @click="openCreate">
          + 항목 추가
        </button>
      </div>
    </div>

    <div v-if="readOnly" class="alert alert-secondary py-2 small">
      마감된 회차입니다. 항목을 수정할 수 없습니다.
    </div>

    <ul class="nav nav-tabs mb-0">
      <li class="nav-item">
        <button
          class="nav-link"
          :class="{ active: targetType === 'EMPLOYEE' }"
          type="button"
          @click="targetType = 'EMPLOYEE'"
        >
          개인 평가 항목
        </button>
      </li>
      <li class="nav-item">
        <button
          class="nav-link"
          :class="{ active: targetType === 'DEPARTMENT' }"
          type="button"
          @click="targetType = 'DEPARTMENT'"
        >
          부서 평가 항목
        </button>
      </li>
    </ul>

    <div class="card shadow-sm border-top-0 rounded-top-0">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th scope="col" style="width: 40px" />
              <th scope="col" style="width: 60px">순서</th>
              <th scope="col" style="width: 110px">코드</th>
              <th scope="col">문항</th>
              <th scope="col" class="text-end" style="width: 100px">가중치</th>
              <th scope="col" class="text-center" style="width: 80px">척도</th>
              <th scope="col" class="text-center" style="width: 80px">활성</th>
              <th scope="col" class="text-end" style="width: 140px">작업</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="8" class="text-center py-5 text-muted">
                <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
                불러오는 중...
              </td>
            </tr>
            <tr v-else-if="items.length === 0">
              <td colspan="8" class="text-center py-5 text-muted">
                {{ targetType === 'EMPLOYEE' ? '개인' : '부서' }} 평가 항목이 없습니다.
              </td>
            </tr>
            <tr
              v-for="(item, index) in loading ? [] : items"
              :key="item.id"
              :draggable="!readOnly"
              :class="{ 'table-active': dragIndex === index, 'text-muted': !item.is_active }"
              @dragstart="onDragStart(index)"
              @dragover.prevent
              @drop="onDrop(index)"
            >
              <td class="text-center" :style="readOnly ? '' : 'cursor: grab'">⠿</td>
              <td>{{ item.order }}</td>
              <td><code class="small">{{ item.code }}</code></td>
              <td>
                {{ item.title }}
                <span v-if="item.in_use" class="badge text-bg-info ms-1" title="응답이 있어 가중치·척도를 변경할 수 없습니다">
                  사용중
                </span>
                <div v-if="item.description" class="small text-muted">{{ item.description }}</div>
              </td>
              <td class="text-end">{{ Number(item.weight).toFixed(2) }}%</td>
              <td class="text-center">{{ item.max_score }}점</td>
              <td class="text-center">
                <button
                  class="btn btn-sm p-0 border-0 bg-transparent"
                  type="button"
                  :disabled="readOnly"
                  @click="toggleActive(item)"
                >
                  <span class="badge" :class="item.is_active ? 'text-bg-success' : 'text-bg-secondary'">
                    {{ item.is_active ? '활성' : '비활성' }}
                  </span>
                </button>
              </td>
              <td class="text-end">
                <button
                  class="btn btn-outline-primary btn-sm me-1"
                  type="button"
                  :disabled="readOnly"
                  @click="openEdit(item)"
                >
                  수정
                </button>
                <button
                  class="btn btn-outline-danger btn-sm"
                  type="button"
                  :disabled="readOnly || item.in_use"
                  @click="askDelete(item)"
                >
                  삭제
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card-footer bg-white d-flex justify-content-between align-items-center">
        <span class="small text-muted">활성 항목 {{ activeCount }}개</span>
        <span class="d-flex align-items-center gap-2">
          <span class="small text-muted">가중치 합계</span>
          <span class="badge fs-6" :class="weightValid ? 'text-bg-success' : 'text-bg-warning'">
            {{ weightSum.toFixed(2) }}%
            {{ weightValid ? '✓' : '⚠' }}
          </span>
        </span>
      </div>
    </div>

    <p v-if="!weightValid && activeCount > 0" class="text-warning small mt-2 mb-0">
      ⚠ 합계가 100%가 아니면 이 회차를 열 수 없습니다.
    </p>
    <p v-if="targetType === 'DEPARTMENT' && activeCount === 0" class="text-muted small mt-2 mb-0">
      부서 평가는 선택 사항입니다. 항목이 없으면 부서 성과 가감이 적용되지 않습니다.
    </p>

    <!-- 생성 / 수정 -->
    <BaseModal
      v-model="editModal.open"
      :title="editModal.mode === 'create' ? '평가 항목 추가' : '평가 항목 수정'"
      size="modal-lg"
      :busy="editModal.busy"
      confirm-text="저장"
      @confirm="submitEdit"
    >
      <div v-if="editModal.error" class="alert alert-danger py-2 small">{{ editModal.error }}</div>

      <div class="row g-3">
        <div class="col-md-4">
          <label class="form-label" for="i-code">코드 <span class="text-danger">*</span></label>
          <input id="i-code" v-model="form.code" type="text" class="form-control" placeholder="PERF" />
        </div>
        <div class="col-md-8">
          <label class="form-label" for="i-title">문항 <span class="text-danger">*</span></label>
          <input id="i-title" v-model="form.title" type="text" class="form-control" placeholder="업무 성과" />
        </div>
        <div class="col-12">
          <label class="form-label" for="i-desc">평가 기준</label>
          <textarea id="i-desc" v-model="form.description" class="form-control" rows="2" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="i-weight">가중치 (%) <span class="text-danger">*</span></label>
          <input id="i-weight" v-model="form.weight" type="number" step="0.01" min="0.01" max="100" class="form-control" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="i-max">척도 상한</label>
          <input id="i-max" v-model.number="form.max_score" type="number" min="1" class="form-control" />
          <div class="form-text">5이면 1~5점 척도</div>
        </div>
        <div class="col-12">
          <div class="form-check">
            <input id="i-active" v-model="form.is_active" class="form-check-input" type="checkbox" />
            <label class="form-check-label" for="i-active">활성</label>
          </div>
        </div>
      </div>
    </BaseModal>

    <!-- 삭제 -->
    <BaseModal
      v-model="deleteModal.open"
      title="항목 삭제"
      :busy="deleteModal.busy"
      confirm-text="삭제"
      confirm-variant="danger"
      @confirm="submitDelete"
    >
      <p class="mb-0">
        <strong>{{ deleteModal.target?.title }}</strong> 항목을 삭제합니다.
      </p>
    </BaseModal>

    <!-- 복제 -->
    <BaseModal
      v-model="cloneModal.open"
      title="다른 회차에서 항목 복제"
      :busy="cloneModal.busy"
      confirm-text="복제"
      @confirm="submitClone"
    >
      <div v-if="cloneModal.error" class="alert alert-danger py-2 small">{{ cloneModal.error }}</div>

      <div class="mb-3">
        <label class="form-label" for="clone-src">복제할 회차</label>
        <select id="clone-src" v-model="cloneModal.sourceCycle" class="form-select">
          <option value="">선택하세요</option>
          <option v-for="c in otherCycles" :key="c.id" :value="c.id">
            {{ c.name }} ({{ c.year }})
          </option>
        </select>
      </div>

      <div class="form-check">
        <input id="clone-replace" v-model="cloneModal.replace" class="form-check-input" type="checkbox" />
        <label class="form-check-label" for="clone-replace">
          기존 {{ targetType === 'EMPLOYEE' ? '개인' : '부서' }} 항목을 모두 지우고 복제
        </label>
      </div>
    </BaseModal>
  </div>
</template>
