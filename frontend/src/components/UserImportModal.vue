<script setup>
import { computed, reactive, ref, watch } from 'vue'

import { bulkImportUsers } from '@/api/admin'
import { extractErrorCode, extractErrorMessage } from '@/api/client'
import BaseModal from '@/components/BaseModal.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'imported'])

const COLUMNS = ['employee_no', 'name', 'department_code', 'position', 'role', 'hired_on']
const COLUMN_HELP = [
  ['employee_no', '사번', '필수 · 중복 불가'],
  ['name', '성명', '필수'],
  ['department_code', '부서코드', '선택 · 활성 부서만'],
  ['position', '직위', '선택'],
  ['role', '권한', '선택 · EMPLOYEE 또는 ADMIN (기본 EMPLOYEE)'],
  ['hired_on', '입사일', '선택 · YYYY-MM-DD'],
]

const file = ref(null)
const busy = ref(false)
const state = reactive({ error: '', errors: [], result: null })

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const hasResult = computed(() => state.result !== null)

watch(open, (value) => {
  if (!value) return
  file.value = null
  state.error = ''
  state.errors = []
  state.result = null
})

function onFileChange(event) {
  file.value = event.target.files?.[0] ?? null
  state.error = ''
  state.errors = []
}

/** 헤더만 담긴 템플릿을 클라이언트에서 만들어 내려준다. */
function downloadTemplate() {
  const sample = [
    COLUMNS.join(','),
    '20260001,김철수,DEV1,선임,EMPLOYEE,2026-01-01',
    '20260002,이영희,HR,,,',
  ].join('\r\n')

  // BOM을 붙여야 Excel에서 한글이 깨지지 않는다
  const blob = new Blob([`\uFEFF${sample}\r\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '사용자_일괄등록_양식.csv'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function submit() {
  if (!file.value) {
    state.error = 'CSV 파일을 선택하세요.'
    return
  }

  busy.value = true
  state.error = ''
  state.errors = []
  try {
    const { data } = await bulkImportUsers(file.value)
    state.result = data
    emit('imported', data)
  } catch (error) {
    const code = extractErrorCode(error)
    state.error = extractErrorMessage(error)
    if (code === 'IMPORT_VALIDATION_FAILED') {
      state.errors = error.response.data.errors ?? []
    }
  } finally {
    busy.value = false
  }
}

function downloadCredentials() {
  const rows = [
    ['사번', '성명', '부서', '권한', '임시 비밀번호'].join(','),
    ...state.result.created.map((row) =>
      [
        row.employee_no,
        `"${row.name.replace(/"/g, '""')}"`,
        row.department_name ?? '',
        row.role,
        row.generated_password,
      ].join(',')
    ),
  ].join('\r\n')

  const blob = new Blob([`\uFEFF${rows}\r\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '등록결과_임시비밀번호.csv'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>

<template>
  <BaseModal
    v-model="open"
    title="사용자 CSV 일괄 등록"
    size="modal-lg"
    :busy="busy"
    :hide-footer="hasResult"
    confirm-text="등록"
    @confirm="submit"
  >
    <!-- 결과 -->
    <template v-if="hasResult">
      <div class="alert alert-success py-2">
        <strong>{{ state.result.created_count }}명</strong>을 등록했습니다.
      </div>

      <div class="alert alert-warning py-2 small">
        임시 비밀번호는 <strong>지금만</strong> 확인할 수 있습니다.
        창을 닫기 전에 내려받아 각 사용자에게 안전하게 전달하세요.
      </div>

      <div class="table-responsive" style="max-height: 320px">
        <table class="table table-sm mb-0">
          <thead class="table-light">
            <tr>
              <th scope="col">사번</th>
              <th scope="col">성명</th>
              <th scope="col">부서</th>
              <th scope="col">임시 비밀번호</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in state.result.created" :key="row.id">
              <td><code class="small">{{ row.employee_no }}</code></td>
              <td>{{ row.name }}</td>
              <td class="small">{{ row.department_name ?? '미배정' }}</td>
              <td><code class="small">{{ row.generated_password }}</code></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="d-flex justify-content-between mt-4">
        <button class="btn btn-outline-primary btn-sm" type="button" @click="downloadCredentials">
          비밀번호 목록 CSV 내려받기
        </button>
        <button class="btn btn-primary btn-sm" type="button" @click="open = false">
          확인했습니다
        </button>
      </div>
    </template>

    <!-- 업로드 -->
    <template v-else>
      <div v-if="state.error" class="alert alert-danger py-2 small mb-3">
        {{ state.error }}
      </div>

      <div v-if="state.errors.length" class="mb-3">
        <p class="small text-muted mb-2">
          아래 오류를 수정한 뒤 다시 올려주세요. <strong>등록된 사용자는 없습니다.</strong>
        </p>
        <div class="table-responsive border rounded" style="max-height: 240px">
          <table class="table table-sm mb-0">
            <thead class="table-light">
              <tr>
                <th scope="col" style="width: 70px">행</th>
                <th scope="col" style="width: 140px">컬럼</th>
                <th scope="col">사유</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(error, index) in state.errors" :key="index">
                <td>{{ error.line }}</td>
                <td><code class="small">{{ error.field }}</code></td>
                <td class="small">{{ error.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="mb-3">
        <label class="form-label" for="import-file">CSV 파일</label>
        <input
          id="import-file"
          class="form-control"
          type="file"
          accept=".csv,text/csv"
          :disabled="busy"
          @change="onFileChange"
        />
        <div class="form-text">
          UTF-8 또는 CP949(Excel 기본)로 저장된 CSV를 올리세요. 최대 2000행.
        </div>
      </div>

      <div class="border rounded p-3 bg-light">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <strong class="small">컬럼 형식</strong>
          <button class="btn btn-outline-secondary btn-sm" type="button" @click="downloadTemplate">
            양식 내려받기
          </button>
        </div>
        <table class="table table-sm mb-0 bg-white">
          <tbody>
            <tr v-for="[key, label, help] in COLUMN_HELP" :key="key">
              <td style="width: 150px"><code class="small">{{ key }}</code></td>
              <td style="width: 90px" class="small">{{ label }}</td>
              <td class="small text-muted">{{ help }}</td>
            </tr>
          </tbody>
        </table>
        <p class="small text-muted mb-0 mt-2">
          비밀번호는 시스템이 자동 생성합니다. 한 행이라도 오류가 있으면 전체가 등록되지 않습니다.
        </p>
      </div>
    </template>
  </BaseModal>
</template>
