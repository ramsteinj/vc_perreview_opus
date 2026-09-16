import client from './client'

// ── 평가 회차 ────────────────────────────────────────────────
export function fetchCycles(params = {}) {
  return client.get('/admin/cycles/', { params })
}

export function fetchCycle(id) {
  return client.get(`/admin/cycles/${id}/`)
}

export function createCycle(payload) {
  return client.post('/admin/cycles/', payload)
}

export function updateCycle(id, payload) {
  return client.patch(`/admin/cycles/${id}/`, payload)
}

export function deleteCycle(id) {
  return client.delete(`/admin/cycles/${id}/`)
}

export function openCycle(id, { confirm = false } = {}) {
  return client.post(`/admin/cycles/${id}/open/`, null, {
    params: confirm ? { confirm: 'true' } : {},
  })
}

export function closeCycle(id, { confirm = false } = {}) {
  return client.post(`/admin/cycles/${id}/close/`, null, {
    params: confirm ? { confirm: 'true' } : {},
  })
}

export function reopenCycle(id) {
  return client.post(`/admin/cycles/${id}/reopen/`)
}

export function checkWeights(id) {
  return client.get(`/admin/cycles/${id}/weight-check/`)
}

export function fetchUnassigned(id) {
  return client.get(`/admin/cycles/${id}/unassigned/`)
}

export function cloneItems(targetCycleId, payload) {
  return client.post(`/admin/cycles/${targetCycleId}/clone-items/`, payload)
}

// ── 평가 항목 ────────────────────────────────────────────────
export function fetchItems(params = {}) {
  return client.get('/admin/items/', { params })
}

export function createItem(payload) {
  return client.post('/admin/items/', payload)
}

export function updateItem(id, payload) {
  return client.patch(`/admin/items/${id}/`, payload)
}

export function deleteItem(id) {
  return client.delete(`/admin/items/${id}/`)
}

export function reorderItems(cycleId, itemIds) {
  return client.post('/admin/items/reorder/', { cycle: cycleId, item_ids: itemIds })
}

// ── 평가자 배정 ──────────────────────────────────────────────
export function fetchAssignmentOverview(params) {
  return client.get('/admin/assignments/overview/', { params })
}

export function createAssignment(payload) {
  return client.post('/admin/assignments/', payload)
}

export function updateAssignment(id, payload) {
  return client.patch(`/admin/assignments/${id}/`, payload)
}

export function deleteAssignment(id) {
  return client.delete(`/admin/assignments/${id}/`)
}

export function bulkAssign(payload) {
  return client.post('/admin/assignments/bulk/', payload)
}
