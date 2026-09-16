<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { extractErrorCode, extractErrorMessage } from '@/api/client'
import * as api from '@/api/my'
import BaseModal from '@/components/BaseModal.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const router = useRouter()
const toasts = useToastStore()

const responseId = Number(route.params.id)

const loading = ref(true)
const response = ref(null)
const items = ref([])
const overallComment = ref('')
const dirty = ref(false)
const saving = ref(false)
const lastSavedAt = ref(null)
const missingItems = ref([])
const submitModal = reactive({ open: false, busy: false })

const AUTOSAVE_DELAY = 3000
let autosaveTimer = null

const editable = computed(() => response.value?.editable === true)

/** 진행률은 서버 응답을 기다리지 않고 입력 즉시 낙관적으로 재계산한다. */
const answeredCount = computed(
  () => items.value.filter((item) => item.answer.score !== null).length
)
const totalItems = computed(() => items.value.length)
const progress = computed(() =>
  totalItems.value === 0 ? 0 : Math.floor((answeredCount.value * 100) / totalItems.value)
)
const complete = computed(() => totalItems.value > 0 && answeredCount.value === totalItems.value)

const weightSum = computed(() =>
  items.value.reduce((sum, item) => sum + Number(item.weight ?? 0), 0)
)

const savedLabel = computed(() => {
  if (!lastSavedAt.value) return ''
  return lastSavedAt.value.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  })
})

function applyResponse(data) {
  response.value = data
  items.value = data.items.map((item) => ({
    ...item,
    answer: { score: item.answer.score, comment: item.answer.comment ?? '' },
  }))
  overallComment.value = data.overall_comment ?? ''
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.fetchResponse(responseId)
    applyResponse(data)
  } catch (error) {
    if (error?.response?.status === 404) {
      toasts.error('평가지를 찾을 수 없거나 접근 권한이 없습니다.')
      router.replace({ name: 'my-evaluations' })
      return
    }
    toasts.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

// ── 저장 ────────────────────────────────────────────────────
function buildPayload() {
  return {
    answers: items.value.map((item) => ({
      item: item.id,
      score: item.answer.score,
      comment: item.answer.comment ?? '',
    })),
    overallComment: overallComment.value,
  }
}

async function save({ silent = false } = {}) {
  if (!editable.value || saving.value) return
  saving.value = true
  try {
    const { data } = await api.saveDraft(responseId, buildPayload())
    dirty.value = false
    lastSavedAt.value = new Date()
    if (response.value) response.value.status = data.status
    if (!silent) toasts.success('임시 저장되었습니다.')
  } catch (error) {
    const code = extractErrorCode(error)
    if (code === 'ALREADY_SUBMITTED' || code === 'CYCLE_DEADLINE_PASSED' || code === 'CYCLE_NOT_OPEN') {
      toasts.error(extractErrorMessage(error))
      await load()
      return
    }
    toasts.error(extractErrorMessage(error, '저장에 실패했습니다. 다시 시도해 주세요.'))
  } finally {
    saving.value = false
  }
}

/** 입력이 바뀌면 3초 디바운스로 자동 저장한다. */
function scheduleAutosave() {
  if (!editable.value) return
  dirty.value = true
  missingItems.value = []
  clearTimeout(autosaveTimer)
  autosaveTimer = setTimeout(() => save({ silent: true }), AUTOSAVE_DELAY)
}

function setScore(item, score) {
  if (!editable.value) return
  // 같은 점수를 다시 누르면 선택을 해제한다
  item.answer.score = item.answer.score === score ? null : score
  scheduleAutosave()
}

// ── 제출 ────────────────────────────────────────────────────
function askSubmit() {
  missingItems.value = []
  if (!complete.value) {
    missingItems.value = items.value
      .filter((item) => item.answer.score === null)
      .map((item) => item.id)
    toasts.error('응답하지 않은 항목이 있습니다.')
    scrollToFirstMissing()
    return
  }
  submitModal.open = true
}

async function confirmSubmit() {
  submitModal.busy = true
  try {
    clearTimeout(autosaveTimer)
    await api.saveDraft(responseId, buildPayload())
    dirty.value = false

    await api.submitResponse(responseId)
    submitModal.open = false
    toasts.success('평가를 제출했습니다.')
    router.push({ name: 'my-evaluations' })
  } catch (error) {
    submitModal.open = false
    const code = extractErrorCode(error)
    if (code === 'INCOMPLETE_ANSWERS') {
      missingItems.value = error.response.data.missing_items ?? []
      toasts.error(extractErrorMessage(error))
      scrollToFirstMissing()
      return
    }
    toasts.error(extractErrorMessage(error))
    if (code === 'ALREADY_SUBMITTED') await load()
  } finally {
    submitModal.busy = false
  }
}

function scrollToFirstMissing() {
  requestAnimationFrame(() => {
    const first = missingItems.value[0]
    if (!first) return
    document.getElementById(`item-${first}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

// ── 이탈 방지 ───────────────────────────────────────────────
function onBeforeUnload(event) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return window.confirm('저장되지 않은 변경이 있습니다. 이 페이지를 떠나시겠습니까?')
})

watch([() => overallComment.value], scheduleAutosave)

onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
  load()
})

onBeforeUnmount(() => {
  clearTimeout(autosaveTimer)
  window.removeEventListener('beforeunload', onBeforeUnload)
})
</script>

<template>
  <div>
    <div v-if="loading" class="text-center py-5 text-muted">
      <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
      불러오는 중...
    </div>

    <template v-else-if="response">
      <RouterLink :to="{ name: 'my-evaluations' }" class="small text-decoration-none">
        ← 내 평가 목록
      </RouterLink>

      <!-- 헤더 + 진행률 (sticky) -->
      <div class="card shadow-sm mt-2 sticky-top" style="top: 0.5rem; z-index: 1020">
        <div class="card-body py-3">
          <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2">
            <div>
              <p class="small text-muted mb-1">
                {{ response.cycle.name }} · {{ response.round_display }}
                <StatusBadge :status="response.status" class="ms-1" />
              </p>
              <h2 class="h6 mb-0">
                평가 대상: {{ response.target.name }}
                <span class="text-muted small fw-normal">
                  {{ response.target.employee_no ?? response.target.code }}
                  <template v-if="response.target.department_name">
                    · {{ response.target.department_name }}
                  </template>
                </span>
              </h2>
            </div>
            <div class="text-end small text-muted">
              <div>마감 {{ response.cycle.ends_on }}</div>
              <div v-if="saving">저장 중...</div>
              <div v-else-if="savedLabel">마지막 저장: {{ savedLabel }}</div>
              <div v-else-if="dirty" class="text-warning">저장되지 않은 변경</div>
            </div>
          </div>

          <ProgressBar
            :value="progress"
            :answered="answeredCount"
            :total="totalItems"
            show-label
            show-count
            height="0.6rem"
          />
        </div>
      </div>

      <div v-if="!editable" class="alert alert-secondary py-2 small mt-3 mb-0">
        <template v-if="response.status === 'SUBMITTED'">
          제출이 완료된 평가입니다. 수정이 필요하면 관리자에게 문의하세요.
        </template>
        <template v-else>이 평가는 현재 수정할 수 없습니다 (회차 마감 또는 기간 종료).</template>
      </div>

      <!-- 문항 -->
      <div class="mt-3">
        <div
          v-for="(item, index) in items"
          :id="`item-${item.id}`"
          :key="item.id"
          class="card shadow-sm mb-3"
          :class="{ 'border-danger': missingItems.includes(item.id) }"
        >
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start gap-2 mb-1">
              <h3 class="h6 mb-0">{{ index + 1 }}. {{ item.title }}</h3>
              <span class="badge text-bg-light text-nowrap">
                가중치 {{ Number(item.weight).toFixed(0) }}%
              </span>
            </div>
            <p v-if="item.description" class="small text-muted mb-3">{{ item.description }}</p>

            <fieldset class="mb-3" :disabled="!editable">
              <legend class="visually-hidden">{{ item.title }} 점수</legend>
              <div class="btn-group flex-wrap" role="group" :aria-label="`${item.title} 점수`">
                <template v-for="score in item.max_score" :key="score">
                  <input
                    :id="`score-${item.id}-${score}`"
                    type="radio"
                    class="btn-check"
                    :name="`score-${item.id}`"
                    :checked="item.answer.score === score"
                    :disabled="!editable"
                    @click="setScore(item, score)"
                  />
                  <label
                    class="btn btn-outline-primary"
                    :for="`score-${item.id}-${score}`"
                    :aria-label="`${item.title} ${score}점`"
                  >
                    {{ score }}
                  </label>
                </template>
              </div>
              <div v-if="missingItems.includes(item.id)" class="text-danger small mt-1">
                점수를 선택하세요.
              </div>
            </fieldset>

            <label class="form-label small text-muted" :for="`comment-${item.id}`">
              의견 (선택)
            </label>
            <textarea
              :id="`comment-${item.id}`"
              v-model="item.answer.comment"
              class="form-control"
              rows="2"
              :disabled="!editable"
              @input="scheduleAutosave"
            />
          </div>
        </div>

        <!-- 종합 의견 -->
        <div class="card shadow-sm mb-3">
          <div class="card-body">
            <label class="form-label" for="overall-comment">종합 의견 (선택)</label>
            <textarea
              id="overall-comment"
              v-model="overallComment"
              class="form-control"
              rows="3"
              :disabled="!editable"
            />
          </div>
        </div>

        <p class="small text-muted">
          가중치 합계 {{ weightSum.toFixed(0) }}% · 항목 {{ totalItems }}개
        </p>

        <!-- 액션 -->
        <div v-if="editable" class="d-flex justify-content-end gap-2 pb-4">
          <button class="btn btn-light" type="button" :disabled="saving" @click="save()">
            <span v-if="saving" class="spinner-border spinner-border-sm me-2" aria-hidden="true" />
            임시 저장
          </button>
          <button class="btn btn-primary" type="button" :disabled="saving" @click="askSubmit">
            제출하기
          </button>
        </div>
        <div v-else class="d-flex justify-content-end pb-4">
          <RouterLink class="btn btn-light" :to="{ name: 'my-evaluations' }">목록으로</RouterLink>
        </div>
      </div>
    </template>

    <!-- 제출 확인 -->
    <BaseModal
      v-model="submitModal.open"
      title="평가 제출"
      :busy="submitModal.busy"
      confirm-text="제출"
      @confirm="confirmSubmit"
    >
      <p class="mb-2">
        <strong>{{ response?.target.name }}</strong>에 대한
        {{ response?.round_display }} 평가를 제출합니다.
      </p>
      <p class="text-danger small mb-0">
        제출 후에는 수정할 수 없습니다. 수정이 필요하면 관리자에게 반려를 요청해야 합니다.
      </p>
    </BaseModal>
  </div>
</template>
