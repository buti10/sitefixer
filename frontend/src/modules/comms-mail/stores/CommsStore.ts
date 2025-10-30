import { defineStore } from 'pinia'

type Thread = { id:number; type:'mail'|'chat'; subject:string; from?:string; status:'open'|'waiting'|'closed'; ts:string }

export const useCommsStore = defineStore('comms', {
  state: () => ({ inbox: [] as Thread[], counters:{mail:0, chat:0}, loading:false }),
  actions: {
    async fetchInbox() {
      this.loading = true
      const r = await fetch('/mock/comms/inbox.json')   // <-- direkt aus /public
      const data = await r.json()
      this.inbox = data.items
      this.counters = data.counters
      this.loading = false
    }
  }
})
