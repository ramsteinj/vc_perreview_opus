<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { fetchUserOptions } from '@/api/admin'

const props = defineProps({
  modelValue: { type: [Number, String, null], default: null },
  placeholder: { type: String, default: '선택하세요' },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: '' }, // '', 'form-select-sm'
  excludeId: { type: [Number, String, null], default: null },
  allowEmpty: { type: Boolean, default: true },
  invalid: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

// 옵션 목록은 여러 인스턴스가 공유한다 (배정 화면에서 행마다 셀렉트가 생긴다)
const cache = ref(null)
const options = ref([])
const loading = ref(false)

const selected = computed({
  get: () => (props.modelValue === null ? '' : props.modelValue),
  set: (value) => emit('update:modelValue', value === '' ? null : Number(value)),
})

const visibleOptions = computed(() =>
  options.value.filter((option) => String(option.id) !== String(props.excludeId))
)

async function load() {
  if (cache.value) {
    options.value = cache.value
    return
  }
  loading.value = true
  try {
    const { data } = await fetchUserOptions()
    cache.value = data
    options.value = data
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, () => {}, { immediate: true })
onMounted(load)
</script>

<template>
  <select
    v-model="selected"
    class="form-select"
    :class="[size, { 'is-invalid': invalid }]"
    :disabled="disabled || loading"
  >
    <option v-if="allowEmpty" value="">{{ placeholder }}</option>
    <option v-for="option in visibleOptions" :key="option.id" :value="option.id">
      {{ option.name }} ({{ option.employee_no }}{{
        option.department_name ? ` · ${option.department_name}` : ''
      }})
    </option>
  </select>
</template>
