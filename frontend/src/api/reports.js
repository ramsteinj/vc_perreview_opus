import client from './client'

export function fetchStatusSummary(cycleId) {
  return client.get(`/admin/cycles/${cycleId}/status/summary/`)
}

export function fetchStatusDetail(cycleId, params = {}) {
  return client.get(`/admin/cycles/${cycleId}/status/detail/`, { params })
}

export function fetchStatusPending(cycleId, params = {}) {
  return client.get(`/admin/cycles/${cycleId}/status/pending/`, { params })
}

export function fetchAdminResponse(id) {
  return client.get(`/admin/responses/${id}/`)
}

export function reopenResponse(id, reason) {
  return client.post(`/admin/responses/${id}/reopen/`, reason ? { reason } : {})
}

// ── 점수 산출 ────────────────────────────────────────────────
export function calculateScores(cycleId) {
  return client.post(`/admin/cycles/${cycleId}/calculate/`)
}

export function fetchScores(cycleId, params = {}) {
  return client.get(`/admin/cycles/${cycleId}/scores/`, { params })
}

export function fetchDepartmentScores(cycleId) {
  return client.get(`/admin/cycles/${cycleId}/department-scores/`)
}
