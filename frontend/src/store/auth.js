import { defineStore } from 'pinia'
import api from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    role: localStorage.getItem('role') || '',
    realName: localStorage.getItem('realName') || '',
    username: localStorage.getItem('username') || '',
  }),
  getters: {
    isTeacher: (s) => s.role === 'teacher',
    isStudent: (s) => s.role === 'student',
  },
  actions: {
    async login(username, password) {
      const data = await api.post('/auth/login', { username, password })
      this.token = data.token
      this.role = data.role
      this.realName = data.real_name
      this.username = data.username
      localStorage.setItem('token', data.token)
      localStorage.setItem('role', data.role)
      localStorage.setItem('realName', data.real_name)
      localStorage.setItem('username', data.username)
    },
    logout() {
      localStorage.clear()
      this.$reset()
    },
  },
})
