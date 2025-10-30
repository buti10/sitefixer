import { defineStore } from 'pinia'
import api from '../api'

type User = { id:number; email:string; name:string; role:string } | null

export const useAuth = defineStore('auth', {
  state: () => ({
    user: null as User,
    inited: false,
  }),
  actions: {
    async init() {
      if (this.inited) return
      await this.fetchMe().catch(() => { this.user = null })
      this.inited = true
    },
    async login(email: string, password: string) {
      await api.post('/auth/login', { email, password }, { withCredentials: true })
      await this.fetchMe()
    },
    async fetchMe() {
      const r = await api.get('/users/me', { withCredentials: true, validateStatus: () => true })
      const ct = (r.headers?.['content-type'] || '').toString()
      if (r.status !== 200 || !ct.includes('application/json')) {
        throw new Error('unauth')
      }
      this.user = r.data as any
      localStorage.setItem('sf_user', JSON.stringify(this.user))
    },
    restore() {
      const s = localStorage.getItem('sf_user')
      if (s && !this.user) this.user = JSON.parse(s)
    },
    async logout() {
      try { await api.post('/auth/logout', {}, { withCredentials: true }) } catch {}
      this.user = null
      localStorage.removeItem('sf_user')
      location.href = '/login'
    }
  }
})
