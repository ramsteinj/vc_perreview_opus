import { defineStore } from 'pinia'
import { ref } from 'vue'

let nextId = 1

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])

  function push(message, variant = 'success', timeout = 3000) {
    const id = nextId++
    toasts.value.push({ id, message, variant })
    if (timeout > 0) {
      setTimeout(() => dismiss(id), timeout)
    }
    return id
  }

  function dismiss(id) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  const success = (message) => push(message, 'success')
  const error = (message) => push(message, 'danger', 5000)

  return { toasts, push, dismiss, success, error }
})
