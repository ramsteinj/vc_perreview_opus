<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import * as adminApi from '@/api/admin'
import { extractErrorMessage } from '@/api/client'
import BaseModal from '@/components/BaseModal.vue'
import { useToastStore } from '@/stores/toast'

const toasts = useToastStore()

const tree = ref([])
const flat = ref([])
const loading = ref(false)
const showInactive = ref(true)

const editModal = reactive({ open: false, busy: false, error: '', mode: 'create', id: null })
const form = reactive({ code: '', name: '', parent: '', is_active: true })

const deleteModal = reactive({ open: false, busy: false, error: '', target: null, hard: false })

/** 상위 부서 선택지. 편집 중인 부서와 그 자손은 제외한다 (순환 방지). */
const parentOptions = computed(() => {
  if (editModal.mode === 'create') return flat.value
  const excluded = new Set()
  const collect = (id) => {
    excluded.add(id)
    flat.value.filter((d) => d.parent === id).forEach((d) => collect(d.id))
  }
  collect(editModal.id)
  return flat.value.filter((d) => !excluded.has(d.id))
})

/** 트리를 들여쓰기 깊이가 붙은 평면 목록으로 변환한다. */
const visibleRows = computed(() => {
  const rows = []
  const walk = (nodes, depth) => {
    nodes.forEach((node) => {
      if (showInactive.value || node.is_active) {
        rows.push({ ...node, depth })
      }
      walk(node.children ?? [], depth + 1)
    })
  }
  walk(tree.value, 0)
  return rows
})

async function load() {
  loading.value = true
  try {
    const [treeRes, flatRes] = await Promise.all([
      adminApi.fetchDepartmentTree(),
      adminApi.fetchDepartments({ page_size: 200 }),
    ])
    tree.value = treeRes.data.results
    flat.value = flatRes.data.results
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function openCreate(parentId = '') {
  editModal.mode = 'create'
  editModal.id = null
  editModal.error = ''
  Object.assign(form, { code: '', name: '', parent: parentId, is_active: true })
  editModal.open = true
}

function openEdit(row) {
  const source = flat.value.find((d) => d.id === row.id)
  editModal.mode = 'edit'
  editModal.id = row.id
  editModal.error = ''
  Object.assign(form, {
    code: source?.code ?? row.code,
    name: source?.name ?? row.name,
    parent: source?.parent ?? '',
    is_active: source?.is_active ?? row.is_active,
  })
  editModal.open = true
}

async function submitEdit() {
  editModal.error = ''
  if (!form.code.trim() || !form.name.trim()) {
    editModal.error = '부서코드와 부서명을 입력하세요.'
    return
  }

  editModal.busy = true
  try {
    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      parent: form.parent === '' ? null : form.parent,
      is_active: form.is_active,
    }
    if (editModal.mode === 'create') {
      await adminApi.createDepartment(payload)
      toasts.success('부서를 생성했습니다.')
    } else {
      await adminApi.updateDepartment(editModal.id, payload)
      toasts.success('부서를 수정했습니다.')
    }
    editModal.open = false
    await load()
  } catch (error) {
    editModal.error = extractErrorMessage(error)
  } finally {
    editModal.busy = false
  }
}

function openDelete(row) {
  const source = flat.value.find((d) => d.id === row.id) ?? row
  deleteModal.target = source
  deleteModal.hard = false
  deleteModal.error = ''
  deleteModal.open = true
}

const canHardDelete = computed(() => {
  const t = deleteModal.target
  if (!t) return false
  return (t.member_count ?? 0) === 0 && (t.child_count ?? 0) === 0
})

async function submitDelete() {
  deleteModal.busy = true
  deleteModal.error = ''
  try {
    await adminApi.deleteDepartment(deleteModal.target.id, { hard: deleteModal.hard })
    toasts.success(deleteModal.hard ? '부서를 삭제했습니다.' : '부서를 비활성화했습니다.')
    deleteModal.open = false
    await load()
  } catch (error) {
    deleteModal.error = extractErrorMessage(error)
  } finally {
    deleteModal.busy = false
  }
}

async function reactivate(row) {
  try {
    await adminApi.updateDepartment(row.id, { is_active: true })
    toasts.success('부서를 활성화했습니다.')
    await load()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <div class="form-check mb-0">
        <input
          id="show-inactive-dept"
          v-model="showInactive"
          class="form-check-input"
          type="checkbox"
        />
        <label class="form-check-label small" for="show-inactive-dept">비활성 부서 포함</label>
      </div>
      <button class="btn btn-primary btn-sm" type="button" @click="openCreate()">
        + 부서 추가
      </button>
    </div>

    <div class="card shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th scope="col">부서</th>
              <th scope="col" style="width: 120px">코드</th>
              <th scope="col" class="text-center" style="width: 90px">인원</th>
              <th scope="col" class="text-center" style="width: 90px">상태</th>
              <th scope="col" class="text-end" style="width: 230px">작업</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="5" class="text-center py-5 text-muted">
                <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
                불러오는 중...
              </td>
            </tr>
            <tr v-else-if="visibleRows.length === 0">
              <td colspan="5" class="text-center py-5 text-muted">
                등록된 부서가 없습니다. [부서 추가]로 조직도를 만드세요.
              </td>
            </tr>
            <tr v-for="row in loading ? [] : visibleRows" :key="row.id">
              <td>
                <span :style="{ paddingLeft: `${row.depth * 1.5}rem` }">
                  <span v-if="row.depth > 0" class="text-muted me-1">└</span>
                  <span :class="{ 'text-muted': !row.is_active }">{{ row.name }}</span>
                </span>
              </td>
              <td><code class="small">{{ row.code }}</code></td>
              <td class="text-center">{{ row.member_count }}</td>
              <td class="text-center">
                <span class="badge" :class="row.is_active ? 'text-bg-success' : 'text-bg-secondary'">
                  {{ row.is_active ? '활성' : '비활성' }}
                </span>
              </td>
              <td class="text-end">
                <button
                  class="btn btn-outline-secondary btn-sm me-1"
                  type="button"
                  @click="openCreate(row.id)"
                >
                  하위 추가
                </button>
                <button
                  class="btn btn-outline-primary btn-sm me-1"
                  type="button"
                  @click="openEdit(row)"
                >
                  수정
                </button>
                <button
                  v-if="row.is_active"
                  class="btn btn-outline-danger btn-sm"
                  type="button"
                  @click="openDelete(row)"
                >
                  삭제
                </button>
                <button
                  v-else
                  class="btn btn-outline-success btn-sm"
                  type="button"
                  @click="reactivate(row)"
                >
                  활성화
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 생성 / 수정 -->
    <BaseModal
      v-model="editModal.open"
      :title="editModal.mode === 'create' ? '부서 추가' : '부서 수정'"
      :busy="editModal.busy"
      confirm-text="저장"
      @confirm="submitEdit"
    >
      <div v-if="editModal.error" class="alert alert-danger py-2 small">{{ editModal.error }}</div>

      <div class="mb-3">
        <label class="form-label" for="dept-code">부서코드</label>
        <input id="dept-code" v-model="form.code" type="text" class="form-control" />
      </div>
      <div class="mb-3">
        <label class="form-label" for="dept-name">부서명</label>
        <input id="dept-name" v-model="form.name" type="text" class="form-control" />
      </div>
      <div class="mb-3">
        <label class="form-label" for="dept-parent">상위 부서</label>
        <select id="dept-parent" v-model="form.parent" class="form-select">
          <option value="">(최상위)</option>
          <option v-for="option in parentOptions" :key="option.id" :value="option.id">
            {{ option.name }} ({{ option.code }})
          </option>
        </select>
      </div>
      <div class="form-check">
        <input id="dept-active" v-model="form.is_active" class="form-check-input" type="checkbox" />
        <label class="form-check-label" for="dept-active">활성</label>
      </div>
    </BaseModal>

    <!-- 삭제 -->
    <BaseModal
      v-model="deleteModal.open"
      title="부서 삭제"
      :busy="deleteModal.busy"
      confirm-text="진행"
      confirm-variant="danger"
      @confirm="submitDelete"
    >
      <div v-if="deleteModal.error" class="alert alert-danger py-2 small">
        {{ deleteModal.error }}
      </div>

      <p class="mb-3">
        <strong>{{ deleteModal.target?.name }}</strong> 부서를 처리합니다.
      </p>

      <div class="form-check mb-2">
        <input
          id="delete-soft"
          v-model="deleteModal.hard"
          class="form-check-input"
          type="radio"
          :value="false"
        />
        <label class="form-check-label" for="delete-soft">
          비활성화 <span class="text-muted small">(데이터 보존, 권장)</span>
        </label>
      </div>
      <div class="form-check">
        <input
          id="delete-hard"
          v-model="deleteModal.hard"
          class="form-check-input"
          type="radio"
          :value="true"
          :disabled="!canHardDelete"
        />
        <label class="form-check-label" for="delete-hard">
          완전 삭제
          <span class="text-muted small">
            <template v-if="canHardDelete">(되돌릴 수 없습니다)</template>
            <template v-else>(하위 부서나 소속 직원이 있어 불가)</template>
          </span>
        </label>
      </div>
    </BaseModal>
  </div>
</template>
