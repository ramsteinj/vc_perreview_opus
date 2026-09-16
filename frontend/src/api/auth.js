import client from './client'

export function login({ name, employeeNo, password }) {
  return client.post('/auth/login/', {
    name,
    employee_no: employeeNo,
    password,
  })
}

export function refreshToken(refresh) {
  return client.post('/auth/refresh/', { refresh })
}

export function logout(refresh) {
  return client.post('/auth/logout/', { refresh })
}

export function fetchMe() {
  return client.get('/auth/me/')
}

export function changePassword({ currentPassword, newPassword }) {
  return client.post('/auth/change-password/', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
