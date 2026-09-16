<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'

import * as adminApi from '@/api/admin'
import { extractErrorMessage } from '@/api/client'
import BaseModal from '@/components/BaseModal.vue'
import DataTable from '@/components/DataTable.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toasts = useToastStore()

const columns = [
  { key: 'employee_no', label: '사번', sortable: true, width: '120px' },
  { key: 'name', label: '성명', sortable: true, width: '120px' },
  { key: 'department_name', label: '부서' },
  { key: 'position', label: '직위', width: '100px' },
  { key: 'role', label: '권한', width: '90px', align: 'center' },
  { key: 'is_active', label: '상태', width: '90px', align: 'center' },
  { key: 'actions', label: '작업', width: '230px', align: 'end' },
]

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 25
const ordering = ref('employee_no')

const filters = reactive({ search: '', department: '', role: '', is_active: '' })
const departments = ref([])
const roles = ref([])

let searchTimer = null

const editModal = reactive({ open: false, busy: false, error: '', mode: 'create', id: null })
const form = reactive({
  employee_no: '',
  name: '',
  department: '',
  position: '',
  role: 'EMPLOYEE',
  hired_on: '',
  is_active: true,
  password: '',
})

const resetModal = reactive({ open: false, busy: false, error: '', target: null, password: '' })
const deactivateModal = reactive({ open: false, busy: false, error: '', target: null })
const credentialModal = reactive({ open: false, title: '', employeeNo: '', password: '' })

const isSelf = (row) => row.id === auth.user?.id

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, ordering: ordering.value }
    if (filters.search) params.search = filters.search
    if (filters.department) params.department = filters.department
    if (filters.role) params.role = filters.role
    if (filters.is_active !== '') params.is_active = filters.is_active

    const { data } = await adminApi.fetchUsers(params)
    rows.value = data.results
    total.value = data.count
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadReferenceData() {
  try {
    const [deptRes, roleRes] = await Promise.all([
      adminApi.fetchDepartments({ page_size: 200, is_active: true }),
      adminApi.fetchRoles(),
    ])
    departments.value = deptRes.data.results
    roles.value = roleRes.data
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  }
}

watch([() => filters.department, () => filters.role, () => filters.is_active], () => {
  page.value = 1
  load()
})

watch(
  () => filters.search,
  () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      page.value = 1
      load()
    }, 300)
  }
)

watch([page, ordering], load)

function resetFilters() {
  Object.assign(filters, { search: '', department: '', role: '', is_active: '' })
}

// ── 생성 / 수정 ────────────────────────────────────────────
function openCreate() {
  editModal.mode = 'create'
  editModal.id = null
  editModal.error = ''
  Object.assign(form, {
    employee_no: '',
    name: '',
    department: '',
    position: '',
    role: 'EMPLOYEE',
    hired_on: '',
    is_active: true,
    password: '',
  })
  editModal.open = true
}

function openEdit(row) {
  editModal.mode = 'edit'
  editModal.id = row.id
  editModal.error = ''
  Object.assign(form, {
    employee_no: row.employee_no,
    name: row.name,
    department: row.department ?? '',
    position: row.position ?? '',
    role: row.role,
    hired_on: row.hired_on ?? '',
    is_active: row.is_active,
    password: '',
  })
  editModal.open = true
}

const selfDowngrade = computed(
  () => editModal.mode === 'edit' && editModal.id === auth.user?.id && form.role !== 'ADMIN'
)

async function submitEdit() {
  editModal.error = ''
  if (!form.employee_no.trim() || !form.name.trim()) {
    editModal.error = '사번과 성명을 입력하세요.'
    return
  }

  editModal.busy = true
  try {
    const payload = {
      employee_no: form.employee_no.trim(),
      name: form.name.trim(),
      department: form.department === '' ? null : form.department,
      position: form.position,
      role: form.role,
      hired_on: form.hired_on || null,
      is_active: form.is_active,
    }

    if (editModal.mode === 'create') {
      if (form.password) payload.password = form.password
      const { data } = await adminApi.createUser(payload)
      editModal.open = false
      if (data.generated_password) {
        Object.assign(credentialModal, {
          open: true,
          title: '임시 비밀번호가 발급되었습니다',
          employeeNo: data.employee_no,
          password: data.generated_password,
        })
      } else {
        toasts.success('사용자를 생성했습니다.')
      }
    } else {
      await adminApi.updateUser(editModal.id, payload)
      editModal.open = false
      toasts.success('사용자 정보를 수정했습니다.')
      if (editModal.id === auth.user?.id) await auth.loadProfile()
    }
    await load()
  } catch (error) {
    editModal.error = extractErrorMessage(error)
  } finally {
    editModal.busy = false
  }
}

// ── 비밀번호 초기화 ────────────────────────────────────────
function openReset(row) {
  resetModal.target = row
  resetModal.password = ''
  resetModal.error = ''
  resetModal.open = true
}

async function submitReset() {
  resetModal.busy = true
  resetModal.error = ''
  try {
    const { data } = await adminApi.resetUserPassword(
      resetModal.target.id,
      resetModal.password || undefined
    )
    resetModal.open = false
    if (data.generated_password) {
      Object.assign(credentialModal, {
        open: true,
        title: '비밀번호가 초기화되었습니다',
        employeeNo: data.employee_no,
        password: data.generated_password,
      })
    } else {
      toasts.success('비밀번호를 초기화했습니다.')
    }
  } catch (error) {
    resetModal.error = extractErrorMessage(error)
  } finally {
    resetModal.busy = false
  }
}

// ── 비활성화 / 활성화 ──────────────────────────────────────
function openDeactivate(row) {
  deactivateModal.target = row
  deactivateModal.error = ''
  deactivateModal.open = true
}

async function submitDeactivate() {
  deactivateModal.busy = true
  deactivateModal.error = ''
  try {
    await adminApi.deleteUser(deactivateModal.target.id)
    deactivateModal.open = false
    toasts.success('사용자를 비활성화했습니다.')
    await load()
  } catch (error) {
    deactivateModal.error = extractErrorMessage(error)
  } finally {
    deactivateModal.busy = false
  }
}

async function activate(row) {
  try {
    await adminApi.activateUser(row.id)
    toasts.success('사용자를 활성화했습니다.')
    await load()
  } catch (error) {
    toasts.error(extractErrorMessage(error))
  }
}

async function copyPassword() {
  try {
    await navigator.clipboard.writeText(credentialModal.password)
    toasts.success('비밀번호를 복사했습니다.')
  } catch {
    toasts.error('복사에 실패했습니다. 직접 선택해 복사하세요.')
  }
}

onMounted(() => {
  loadReferenceData()
  load()
})
</script>

<template>
  <div>
    <!-- 필터 -->
    <div class="card shadow-sm mb-3">
      <div class="card-body py-3">
        <div class="row g-2 align-items-end">
          <div class="col-12 col-md-4">
            <label class="form-label small mb-1" for="user-search">검색 (사번 · 성명)</label>
            <input
              id="user-search"
              v-model="filters.search"
              type="search"
              class="form-control form-control-sm"
              placeholder="사번 또는 성명"
            />
          </div>
          <div class="col-6 col-md-3">
            <label class="form-label small mb-1" for="user-dept">부서</label>
            <select id="user-dept" v-model="filters.department" class="form-select form-select-sm">
              <option value="">전체</option>
              <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small mb-1" for="user-role">권한</label>
            <select id="user-role" v-model="filters.role" class="form-select form-select-sm">
              <option value="">전체</option>
              <option v-for="r in roles" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small mb-1" for="user-status">상태</label>
            <select id="user-status" v-model="filters.is_active" class="form-select form-select-sm">
              <option value="">전체</option>
              <option value="true">재직</option>
              <option value="false">비활성</option>
            </select>
          </div>
          <div class="col-6 col-md-1 d-grid">
            <button class="btn btn-light btn-sm" type="button" @click="resetFilters">초기화</button>
          </div>
        </div>
      </div>
    </div>

    <div class="d-flex justify-content-end mb-3">
      <button class="btn btn-primary btn-sm" type="button" @click="openCreate">
        + 사용자 추가
      </button>
    </div>

    <div class="card shadow-sm">
      <div class="card-body p-0 pt-0">
        <DataTable
          v-model:page="page"
          v-model:ordering="ordering"
          :columns="columns"
          :rows="rows"
          :loading="loading"
          :page-size="pageSize"
          :total="total"
          empty-text="조건에 해당하는 사용자가 없습니다."
          class="p-3"
        >
          <template #cell-department_name="{ row }">
            {{ row.department_name ?? '미배정' }}
          </template>

          <template #cell-position="{ row }">
            {{ row.position || '-' }}
          </template>

          <template #cell-role="{ row }">
            <span class="badge" :class="row.role === 'ADMIN' ? 'text-bg-warning' : 'text-bg-light'">
              {{ row.role_display }}
            </span>
          </template>

          <template #cell-is_active="{ row }">
            <span class="badge" :class="row.is_active ? 'text-bg-success' : 'text-bg-secondary'">
              {{ row.is_active ? '재직' : '비활성' }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <button
              class="btn btn-outline-primary btn-sm me-1"
              type="button"
              @click="openEdit(row)"
            >
              수정
            </button>
            <button
              class="btn btn-outline-secondary btn-sm me-1"
              type="button"
              @click="openReset(row)"
            >
              비밀번호
            </button>
            <button
              v-if="row.is_active"
              class="btn btn-outline-danger btn-sm"
              type="button"
              :disabled="isSelf(row)"
              :title="isSelf(row) ? '본인 계정은 비활성화할 수 없습니다' : ''"
              @click="openDeactivate(row)"
            >
              비활성화
            </button>
            <button v-else class="btn btn-outline-success btn-sm" type="button" @click="activate(row)">
              활성화
            </button>
          </template>
        </DataTable>
      </div>
    </div>

    <!-- 생성 / 수정 -->
    <BaseModal
      v-model="editModal.open"
      :title="editModal.mode === 'create' ? '사용자 추가' : '사용자 수정'"
      size="modal-lg"
      :busy="editModal.busy"
      :confirm-disabled="selfDowngrade"
      confirm-text="저장"
      @confirm="submitEdit"
    >
      <div v-if="editModal.error" class="alert alert-danger py-2 small">{{ editModal.error }}</div>
      <div v-if="selfDowngrade" class="alert alert-warning py-2 small">
        본인의 관리자 권한은 스스로 낮출 수 없습니다.
      </div>

      <div class="row g-3">
        <div class="col-md-6">
          <label class="form-label" for="u-no">사번 <span class="text-danger">*</span></label>
          <input id="u-no" v-model="form.employee_no" type="text" class="form-control" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="u-name">성명 <span class="text-danger">*</span></label>
          <input id="u-name" v-model="form.name" type="text" class="form-control" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="u-dept">부서</label>
          <select id="u-dept" v-model="form.department" class="form-select">
            <option value="">미배정</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">
              {{ d.name }} ({{ d.code }})
            </option>
          </select>
        </div>
        <div class="col-md-6">
          <label class="form-label" for="u-position">직위</label>
          <input id="u-position" v-model="form.position" type="text" class="form-control" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="u-role">권한</label>
          <select id="u-role" v-model="form.role" class="form-select">
            <option v-for="r in roles" :key="r.value" :value="r.value">{{ r.label }}</option>
          </select>
        </div>
        <div class="col-md-6">
          <label class="form-label" for="u-hired">입사일</label>
          <input id="u-hired" v-model="form.hired_on" type="date" class="form-control" />
        </div>

        <div v-if="editModal.mode === 'create'" class="col-12">
          <label class="form-label" for="u-password">초기 비밀번호</label>
          <input
            id="u-password"
            v-model="form.password"
            type="text"
            class="form-control"
            placeholder="비워두면 임시 비밀번호가 자동 발급됩니다"
          />
          <div class="form-text">최소 10자 이상이어야 합니다.</div>
        </div>

        <div class="col-12">
          <div class="form-check">
            <input id="u-active" v-model="form.is_active" class="form-check-input" type="checkbox" />
            <label class="form-check-label" for="u-active">재직 (활성)</label>
          </div>
        </div>
      </div>
    </BaseModal>

    <!-- 비밀번호 초기화 -->
    <BaseModal
      v-model="resetModal.open"
      title="비밀번호 초기화"
      :busy="resetModal.busy"
      confirm-text="초기화"
      confirm-variant="warning"
      @confirm="submitReset"
    >
      <div v-if="resetModal.error" class="alert alert-danger py-2 small">{{ resetModal.error }}</div>

      <p class="mb-3">
        <strong>{{ resetModal.target?.name }}</strong>
        ({{ resetModal.target?.employee_no }})의 비밀번호를 초기화합니다.
      </p>

      <label class="form-label" for="reset-password">새 비밀번호</label>
      <input
        id="reset-password"
        v-model="resetModal.password"
        type="text"
        class="form-control"
        placeholder="비워두면 임시 비밀번호가 자동 발급됩니다"
      />
    </BaseModal>

    <!-- 비활성화 -->
    <BaseModal
      v-model="deactivateModal.open"
      title="사용자 비활성화"
      :busy="deactivateModal.busy"
      confirm-text="비활성화"
      confirm-variant="danger"
      @confirm="submitDeactivate"
    >
      <div v-if="deactivateModal.error" class="alert alert-danger py-2 small">
        {{ deactivateModal.error }}
      </div>
      <p class="mb-0">
        <strong>{{ deactivateModal.target?.name }}</strong>
        ({{ deactivateModal.target?.employee_no }}) 계정을 비활성화합니다.
        <br />
        <span class="text-muted small">
          비활성화된 계정은 로그인할 수 없습니다. 평가 이력은 보존됩니다.
        </span>
      </p>
    </BaseModal>

    <!-- 발급된 비밀번호 표시 -->
    <BaseModal
      v-model="credentialModal.open"
      :title="credentialModal.title"
      hide-footer
    >
      <div class="alert alert-warning py-2 small">
        이 비밀번호는 <strong>지금만</strong> 확인할 수 있습니다. 창을 닫으면 다시 볼 수 없습니다.
      </div>

      <dl class="row mb-3">
        <dt class="col-4">사번</dt>
        <dd class="col-8">{{ credentialModal.employeeNo }}</dd>
        <dt class="col-4">임시 비밀번호</dt>
        <dd class="col-8">
          <code class="fs-6">{{ credentialModal.password }}</code>
        </dd>
      </dl>

      <div class="d-flex gap-2">
        <button class="btn btn-outline-primary btn-sm" type="button" @click="copyPassword">
          복사
        </button>
        <button
          class="btn btn-primary btn-sm ms-auto"
          type="button"
          @click="credentialModal.open = false"
        >
          확인했습니다
        </button>
      </div>
    </BaseModal>
  </div>
</template>
