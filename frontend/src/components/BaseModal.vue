<script setup>
import { onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  size: { type: String, default: '' }, // '', 'modal-lg', 'modal-sm'
  confirmText: { type: String, default: '확인' },
  cancelText: { type: String, default: '취소' },
  confirmVariant: { type: String, default: 'primary' },
  busy: { type: Boolean, default: false },
  hideFooter: { type: Boolean, default: false },
  confirmDisabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

function close() {
  if (props.busy) return
  emit('update:modelValue', false)
}

function onKeydown(event) {
  if (event.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (open) => {
    document.body.classList.toggle('modal-open', open)
    if (open) document.addEventListener('keydown', onKeydown)
    else document.removeEventListener('keydown', onKeydown)
  }
)

onBeforeUnmount(() => {
  document.body.classList.remove('modal-open')
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue">
      <div class="modal-backdrop fade show" @click="close" />
      <div class="modal fade show d-block" tabindex="-1" role="dialog">
        <div class="modal-dialog modal-dialog-centered" :class="size">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">{{ title }}</h5>
              <button type="button" class="btn-close" aria-label="닫기" @click="close" />
            </div>

            <div class="modal-body">
              <slot />
            </div>

            <div v-if="!hideFooter" class="modal-footer">
              <slot name="footer">
                <button type="button" class="btn btn-light" :disabled="busy" @click="close">
                  {{ cancelText }}
                </button>
                <button
                  type="button"
                  class="btn"
                  :class="`btn-${confirmVariant}`"
                  :disabled="busy || confirmDisabled"
                  @click="emit('confirm')"
                >
                  <span
                    v-if="busy"
                    class="spinner-border spinner-border-sm me-2"
                    aria-hidden="true"
                  />
                  {{ confirmText }}
                </button>
              </slot>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
