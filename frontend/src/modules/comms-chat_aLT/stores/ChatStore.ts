// modules/comms-chat/stores/ChatStore.ts
import { defineStore } from 'pinia'

export type ChatItem = {
  id: number
  visitor?: string
  page?: string
  status: 'waiting' | 'active' | 'open' | 'closed'
  message_count?: number
  waiting_since?: string
  assignee?: string | null
}

type Msg = {
  id: string
  author: 'agent' | 'visitor'
  text: string
  sentAt: string | null
  deliveredAt?: string | null
  readAt?: string | null
  attachments?: { name: string; url?: string; size?: number }[]
}

type LoadState = 'idle' | 'loading' | 'ok' | 'error'

async function j<T = any>(r: Response) {
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<T>
}

// LHC: 0=pending, 1=active, 2=closed; pending-Flag (waiting queue) separat
function mapStatus(s: any, pending?: number): ChatItem['status'] {
  if (pending === 1) return 'waiting'
  if (s === 0) return 'waiting'
  if (s === 1) return 'active'
  if (s === 2) return 'closed'
  return 'open'
}

const THREAD_POLL_MS = 3000

export const useChatStore = defineStore('chat', {
  state: () => ({
    inbox: [] as ChatItem[],
    windows: [] as number[],
    loadState: 'idle' as LoadState,
    error: null as string | null,
    lastSync: null as number | null,

    // Nachrichten je Chat
    thread: new Map<number, Msg[]>(),

    // Polling
    _inboxTimer: null as number | null,
    _threadTimer: new Map<number, number>(),

    // zuletzt gesehene Besucher-Nachricht je Chat
    _seenTop: new Map<number, string>(),

    // letzte geladene Message-ID je Chat (für inkrementelles Laden)
    _lastMsgId: new Map<number, number>(),
  }),
  getters: {
    byId: (s) => (id: number) => s.inbox.find(x => x.id === id),
    msgs: (s) => (id: number) => s.thread.get(id) ?? [],
    totalUnread: s => s.inbox.reduce((n, x) => n + (x.message_count ?? 0), 0),
  },
  actions: {
    // ---------- Inbox ----------
    setInbox(items: any[]) {
      const map = new Map<number, ChatItem>()
      for (const it of items) {
        const epoch = (it.waiting_since ?? it.time) ? Number(it.waiting_since ?? it.time) : null
        const norm: ChatItem = {
          id: Number(it.id),
          visitor: it.visitor ?? it.nick ?? 'Visitor',
          page: it.page ?? it.referrer ?? '',
          status: mapStatus(it.status, it.pending),
          message_count: Number(it.message_count ?? it.has_unread_op_messages ?? 0) || 0,
          waiting_since: epoch ? new Date(epoch * 1000).toISOString() : undefined,
          assignee: it.operator ?? it.assignee ?? null,
        }
        map.set(norm.id, norm)
      }
      const order = { waiting: 0, active: 1, open: 2, closed: 3 } as const
      this.inbox = Array.from(map.values()).sort((a, b) => order[a.status] - order[b.status])
      this.lastSync = Date.now()
    },

    async fetchInbox(url?: string) {
      // Kein hartes Leeren bei Fehler → kein Flicker
      if (this.loadState === 'idle') this.loadState = 'loading'
      this.error = null
      try {
        const endpoint = url ?? '/api/comms/chat/inbox'
        const data = await fetch(endpoint, { cache: 'no-store' }).then(j<{ items: any[] }>)
        this.setInbox(data.items ?? [])
        this.loadState = 'ok'
      } catch (e: any) {
        // Zustand behalten
        if (this.loadState === 'loading') this.loadState = 'error'
        this.error = e?.message ?? 'load failed'
      }
    },

    startInboxPolling(ms = 5000) {
      this.stopInboxPolling()
      // sofort laden
      this.fetchInbox()
      this._inboxTimer = window.setInterval(() => this.fetchInbox(), ms)
    },

    stopInboxPolling() {
      if (this._inboxTimer) {
        window.clearInterval(this._inboxTimer)
        this._inboxTimer = null
      }
    },

    async accept(id: number) {
      await fetch('/api/comms/chat/accept', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: id }),
      }).catch(() => {})
      const it = this.inbox.find(x => x.id === id)
      if (it) { it.status = 'active'; it.message_count = 0 }
    },

    // ---------- Nachrichten ----------
    async loadMessages(id: number) {
      const last = this._lastMsgId.get(id) ?? 0
      const url = last > 0
        ? `/api/comms/chat/${id}/messages?last=${last}`
        : `/api/comms/chat/${id}/messages`

      const data = await fetch(url, { cache: 'no-store' }).then(j<{ items: Msg[] }>)
      const items = data.items ?? []
      if (!items.length) return

      // anhängen
      const existing = this.thread.get(id) ?? []
      const merged = existing.concat(items)
      this.thread.set(id, merged)

      // höchste ID merken
      const lastId = Number(items[items.length - 1].id)
      this._lastMsgId.set(id, lastId)

      // Inbox-Counter zurücksetzen
      const it = this.inbox.find(x => x.id === id)
      if (it) it.message_count = 0
    },

    startThreadPolling(id: number) {
      if (this._threadTimer.has(id)) return
      this.openMini(id)             // optional: Mini-Fenster öffnen
      this.loadMessages(id)         // sofort einmal laden
      const t = window.setInterval(() => this.loadMessages(id), THREAD_POLL_MS)
      this._threadTimer.set(id, t)
    },

    stopThreadPolling(id: number) {
      const t = this._threadTimer.get(id)
      if (t) {
        window.clearInterval(t)
        this._threadTimer.delete(id)
      }
    },

    markVisible(id: number) {
      // höchste Besucher-Nachricht als „gesehen“ markieren
      const msgs = this.thread.get(id) ?? []
      const lastVisitor = [...msgs].reverse().find(m => m.author === 'visitor')
      if (lastVisitor) this._seenTop.set(id, lastVisitor.id)
    },

    // Anzeige-Helfer: ein Häkchen = gesendet, zwei = geliefert, blau = gelesen
    ticksFor(id: number, msgId: string) {
      const msgs = this.thread.get(id) ?? []
      const m = msgs.find(x => x.id === msgId)
      if (!m) return '✓'
      const delivered = !!m.deliveredAt || !!m.sentAt
      const seenTop = this._seenTop.get(id)
      const read = !!seenTop && Number(seenTop) >= Number(msgId)
      return read ? '✓✓ (read)' : (delivered ? '✓✓' : '✓')
    },

    async sendMessage(id: number, text: string) {
      if (!text.trim()) return
      await fetch('/api/comms/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: id, text }),
      }).then(j)
      await this.loadMessages(id)
    },

    // ---------- UI-Minifenster ----------
    openMini(id: number) {
      if (!this.windows.includes(id)) this.windows.push(id)
    },
    closeMini(id: number) {
      this.windows = this.windows.filter(x => x !== id)
    },

    // ---------- Reset ----------
    reset() {
      this.stopInboxPolling()
      for (const id of Array.from(this._threadTimer.keys())) this.stopThreadPolling(id)
      this.inbox = []
      this.windows = []
      this.thread.clear()
      this._seenTop.clear()
      this._lastMsgId.clear()
      this.loadState = 'idle'
      this.error = null
      this.lastSync = null
    },
  },
  persist: { storage: window.localStorage, paths: ['windows'] },
})
