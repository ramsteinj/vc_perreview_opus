import client from './client'

// ── 부서 ─────────────────────────────────────────────────────
export function fetchDepartments(params = {}) {
  return client.get('/admin/departments/', { params })
}

export function fetchDepartmentTree() {
  return client.get('/admin/departments/', { params: { tree: 'true' } })
}

export function createDepartment(payload) {
  return client.post('/admin/departments/', payload)
}

export function updateDepartment(id, payload) {
  return client.patch(`/admin/departments/${id}/`, payload)
}

export function deleteDepartment(id, { hard = false } = {}) {
  return client.delete(`/admin/departments/${id}/`, { params: hard ? { hard: 'true' } : {} })
}

// ── 사용자 ───────────────────────────────────────────────────
export function fetchUsers(params = {}) {
  return client.get('/admin/users/', { params })
}

export function fetchUserOptions(search) {
  return client.get('/admin/users/options/', { params: search ? { search } : {} })
}

export function createUser(payload) {
  return client.post('/admin/users/', payload)
}

export function updateUser(id, payload) {
  return client.patch(`/admin/users/${id}/`, payload)
}

export function deleteUser(id, { hard = false } = {}) {
  return client.delete(`/admin/users/${id}/`, { params: hard ? { hard: 'true' } : {} })
}

export function activateUser(id) {
  return client.post(`/admin/users/${id}/activate/`)
}

export function resetUserPassword(id, password) {
  return client.post(`/admin/users/${id}/reset-password/`, password ? { password } : {})
}

export function fetchRoles() {
  return client.get('/admin/roles/')
}
