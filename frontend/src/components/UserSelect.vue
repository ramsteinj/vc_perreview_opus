<script>
import { ref } from 'vue'

import { fetchUserOptions } from '@/api/admin'

// 사용자 목록은 모든 UserSelect 인스턴스가 공유한다.
// 배정 화면은 행마다 셀렉트가 2개씩 생기므로 인스턴스마다 요청하면
// 한 페이지에서 수십 번 같은 목록을 받아 화면이 멈춘다.
const sharedOptions = ref(null)
let pending = null

function loadUserOptions() {
  if (sharedOptions.value) return Promise.resolve(sharedOptions.value)
  if (!pending) {
    pending = fetchUserOptions()
      .then(({ data }) => {
        sharedOptions.value = data
        return data
      })
      .finally(() => {
        pending = null
      })
  }
  return pending
}

/** 사용자를 추가·수정한 뒤 다음 조회에서 새 목록을 받게 한다. */
export function invalidateUserOptions() {
  sharedOptions.value = null
}
</script>

<script setup>
import { computed, onMounted } from 'vue'

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

const options = ref(sharedOptions.value ?? [])
const loading = ref(sharedOptions.value === null)

const selected = computed({
  get: () => (props.modelValue === null ? '' : props.modelValue),
  set: (value) => emit('update:modelValue', value === '' ? null : Number(value)),
})

const visibleOptions = computed(() =>
  options.value.filter((option) => String(option.id) !== String(props.excludeId))
)

onMounted(async () => {
  try {
    options.value = await loadUserOptions()
  } finally {
    loading.value = false
  }
})
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
