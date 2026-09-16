<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { extractErrorCode, extractErrorMessage } from '@/api/client'
import { homeRouteFor } from '@/router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = reactive({ name: '', employeeNo: '', password: '' })
const submitting = ref(false)
const errorMessage = ref('')
const showPassword = ref(false)
const touched = ref(false)

const fieldErrors = computed(() => ({
  name: touched.value && !form.name.trim() ? '성명을 입력하세요.' : '',
  employeeNo: touched.value && !form.employeeNo.trim() ? '사번을 입력하세요.' : '',
  password: touched.value && !form.password ? '비밀번호를 입력하세요.' : '',
}))

const hasFieldError = computed(() => Object.values(fieldErrors.value).some(Boolean))

async function handleSubmit() {
  touched.value = true
  errorMessage.value = ''
  if (hasFieldError.value) return

  submitting.value = true
  try {
    const user = await auth.login({
      name: form.name.trim(),
      employeeNo: form.employeeNo.trim(),
      password: form.password,
    })
    const next = route.query.next
    router.push(next ? String(next) : homeRouteFor(user))
  } catch (error) {
    const code = extractErrorCode(error)
    errorMessage.value =
      code === 'TOO_MANY_ATTEMPTS'
        ? extractErrorMessage(error)
        : extractErrorMessage(error, '성명, 사번 또는 비밀번호가 올바르지 않습니다.')
    form.password = ''
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="d-flex justify-content-center align-items-center min-vh-100 px-3">
    <div class="card shadow-sm auth-card">
      <div class="card-body p-4 p-sm-5">
        <div class="text-center mb-4">
          <h1 class="h4 mb-1">인사평가 시스템</h1>
          <p class="text-muted small mb-0">성명 · 사번 · 비밀번호로 로그인하세요</p>
        </div>

        <div v-if="errorMessage" class="alert alert-danger py-2 small" role="alert">
          {{ errorMessage }}
        </div>

        <form novalidate @submit.prevent="handleSubmit">
          <div class="mb-3">
            <label for="login-name" class="form-label">성명</label>
            <input
              id="login-name"
              v-model="form.name"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': fieldErrors.name }"
              autocomplete="name"
              :disabled="submitting"
            />
            <div v-if="fieldErrors.name" class="invalid-feedback">{{ fieldErrors.name }}</div>
          </div>

          <div class="mb-3">
            <label for="login-employee-no" class="form-label">사번</label>
            <input
              id="login-employee-no"
              v-model="form.employeeNo"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': fieldErrors.employeeNo }"
              autocomplete="username"
              :disabled="submitting"
            />
            <div v-if="fieldErrors.employeeNo" class="invalid-feedback">
              {{ fieldErrors.employeeNo }}
            </div>
          </div>

          <div class="mb-4">
            <label for="login-password" class="form-label">비밀번호</label>
            <div class="input-group">
              <input
                id="login-password"
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                class="form-control"
                :class="{ 'is-invalid': fieldErrors.password }"
                autocomplete="current-password"
                :disabled="submitting"
              />
              <button
                class="btn btn-outline-secondary"
                type="button"
                :aria-label="showPassword ? '비밀번호 숨기기' : '비밀번호 표시'"
                :disabled="submitting"
                @click="showPassword = !showPassword"
              >
                {{ showPassword ? '숨기기' : '표시' }}
              </button>
              <div v-if="fieldErrors.password" class="invalid-feedback">
                {{ fieldErrors.password }}
              </div>
            </div>
          </div>

          <button class="btn btn-primary w-100" type="submit" :disabled="submitting">
            <span
              v-if="submitting"
              class="spinner-border spinner-border-sm me-2"
              aria-hidden="true"
            />
            {{ submitting ? '로그인 중...' : '로그인' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
