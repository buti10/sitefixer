import { defineStore } from 'pinia'

export const useMailStore = defineStore('mail', {
  state: () => ({
    unread: 0,
    lastSync: 0,
    error: null as string | null,
  }),
  actions: {
    async fetchUnread() {
      try {
        const r = await fetch('/api/comms/mail/unread', { cache: 'no-store' })
        if (!r.ok) throw new Error(String(r.status))
        const j = await r.json()            // { unread: number }
        this.unread = Number(j.unread ?? 0)
        this.lastSync = Date.now()
        this.error = null
      } catch (e:any) {
        // Demo-Fallback
        this.unread = this.unread || 2
        this.error = e?.message ?? 'fail'
      }
    },
    setUnread(n: number) { this.unread = Math.max(0, n) }
  },
  persist: { storage: window.localStorage, paths: ['unread'] }
})
