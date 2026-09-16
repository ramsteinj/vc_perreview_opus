<script setup>
import { useToastStore } from '@/stores/toast'

const toasts = useToastStore()
</script>

<template>
  <div class="toast-host">
    <div
      v-for="toast in toasts.toasts"
      :key="toast.id"
      class="toast show align-items-center border-0"
      :class="`text-bg-${toast.variant}`"
      role="alert"
      aria-live="assertive"
    >
      <div class="d-flex">
        <div class="toast-body">{{ toast.message }}</div>
        <button
          type="button"
          class="btn-close btn-close-white me-2 m-auto"
          aria-label="닫기"
          @click="toasts.dismiss(toast.id)"
        />
      </div>
    </div>
  </div>
</template>
