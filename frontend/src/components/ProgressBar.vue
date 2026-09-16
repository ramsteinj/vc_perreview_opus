<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  answered: { type: Number, default: null },
  total: { type: Number, default: null },
  height: { type: String, default: '0.5rem' },
  showLabel: { type: Boolean, default: false },
  showCount: { type: Boolean, default: false },
})

const clamped = computed(() => Math.min(100, Math.max(0, props.value)))

const variant = computed(() => {
  if (clamped.value >= 100) return 'bg-success'
  if (clamped.value > 0) return 'bg-primary'
  return 'bg-secondary'
})

const label = computed(() => {
  if (props.showCount && props.total !== null) {
    return `${clamped.value}% (${props.answered}/${props.total})`
  }
  return `${clamped.value}%`
})
</script>

<template>
  <div class="d-flex align-items-center gap-2">
    <div
      class="progress flex-grow-1"
      :style="{ height }"
      role="progressbar"
      :aria-valuenow="clamped"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="`진행률 ${clamped}퍼센트`"
    >
      <div class="progress-bar" :class="variant" :style="{ width: `${clamped}%` }" />
    </div>
    <span v-if="showLabel" class="small text-nowrap" :class="clamped >= 100 ? 'text-success' : 'text-muted'">
      {{ label }}
    </span>
  </div>
</template>
