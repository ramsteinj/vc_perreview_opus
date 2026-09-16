<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { changePassword } from '@/api/auth'
import { extractErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toasts = useToastStore()
const router = useRouter()

const form = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
const submitting = ref(false)
const errorMessage = ref('')

async function handleSubmit() {
  errorMessage.value = ''

  if (form.newPassword !== form.confirmPassword) {
    errorMessage.value = '새 비밀번호가 서로 일치하지 않습니다.'
    return
  }

  submitting.value = true
  try {
    await changePassword({
      currentPassword: form.currentPassword,
      newPassword: form.newPassword,
    })
    await auth.loadProfile()
    toasts.success('비밀번호가 변경되었습니다.')
    router.back()
  } catch (error) {
    errorMessage.value = extractErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="card shadow-sm" style="max-width: 480px">
    <div class="card-body p-4">
      <div v-if="errorMessage" class="alert alert-danger py-2 small" role="alert">
        {{ errorMessage }}
      </div>

      <form novalidate @submit.prevent="handleSubmit">
        <div class="mb-3">
          <label for="current-password" class="form-label">현재 비밀번호</label>
          <input
            id="current-password"
            v-model="form.currentPassword"
            type="password"
            class="form-control"
            autocomplete="current-password"
            required
          />
        </div>

        <div class="mb-3">
          <label for="new-password" class="form-label">새 비밀번호</label>
          <input
            id="new-password"
            v-model="form.newPassword"
            type="password"
            class="form-control"
            autocomplete="new-password"
            required
          />
          <div class="form-text">최소 10자 이상이어야 합니다.</div>
        </div>

        <div class="mb-4">
          <label for="confirm-password" class="form-label">새 비밀번호 확인</label>
          <input
            id="confirm-password"
            v-model="form.confirmPassword"
            type="password"
            class="form-control"
            autocomplete="new-password"
            required
          />
        </div>

        <button class="btn btn-primary" type="submit" :disabled="submitting">
          {{ submitting ? '변경 중...' : '변경하기' }}
        </button>
      </form>
    </div>
  </div>
</template>
