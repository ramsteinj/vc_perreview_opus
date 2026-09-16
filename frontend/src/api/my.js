import client from './client'

export function fetchMyAssignments() {
  return client.get('/my/assignments/')
}

export function createResponse(assignmentId) {
  return client.post('/my/responses/', { assignment: assignmentId })
}

export function fetchResponse(id) {
  return client.get(`/my/responses/${id}/`)
}

/** 임시 저장. 전달한 항목만 upsert되며 score: null도 허용된다. */
export function saveDraft(id, { answers, overallComment }) {
  const payload = {}
  if (answers) payload.answers = answers
  if (overallComment !== undefined) payload.overall_comment = overallComment
  return client.put(`/my/responses/${id}/`, payload)
}

export function submitResponse(id) {
  return client.post(`/my/responses/${id}/submit/`)
}
