<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  size: { type: Number, default: 120 },
  thickness: { type: Number, default: 12 },
  label: { type: String, default: '' },
})

const RADIUS = 50
const circumference = 2 * Math.PI * RADIUS

const clamped = computed(() => Math.min(100, Math.max(0, props.value)))
const dash = computed(() => (clamped.value / 100) * circumference)

const color = computed(() => {
  if (clamped.value >= 90) return 'var(--bs-success)'
  if (clamped.value >= 50) return 'var(--bs-primary)'
  if (clamped.value > 0) return 'var(--bs-warning)'
  return 'var(--bs-secondary)'
})
</script>

<template>
  <figure class="d-inline-flex flex-column align-items-center mb-0">
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 120 120"
      role="img"
      :aria-label="`${label} ${clamped}퍼센트`"
    >
      <circle
        cx="60"
        cy="60"
        :r="RADIUS"
        fill="none"
        stroke="var(--bs-border-color)"
        :stroke-width="thickness"
      />
      <circle
        cx="60"
        cy="60"
        :r="RADIUS"
        fill="none"
        :stroke="color"
        :stroke-width="thickness"
        stroke-linecap="round"
        :stroke-dasharray="`${dash} ${circumference}`"
        transform="rotate(-90 60 60)"
        style="transition: stroke-dasharray 0.4s ease"
      />
      <text
        x="60"
        y="60"
        text-anchor="middle"
        dominant-baseline="central"
        class="fw-semibold"
        style="font-size: 24px; fill: var(--bs-body-color)"
      >
        {{ clamped }}%
      </text>
    </svg>
    <figcaption v-if="label" class="small text-muted mt-1">{{ label }}</figcaption>
  </figure>
</template>
