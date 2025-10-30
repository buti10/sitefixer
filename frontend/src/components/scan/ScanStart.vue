<template>
  <div class="space-y-4">
    <div>
      <label>SFTP Root</label>
      <input v-model="sftpRoot" class="input" />
    </div>
    <div>
      <button @click="start" :disabled="running" class="btn">Scan starten</button>
    </div>

    <div v-if="scanId">
      <p>Scan-ID: {{ scanId }}</p>
      <div>Progress: {{ status.progress }}% — {{ status.status }}</div>
      <ul>
        <li v-for="f in findings" :key="f.id">
          [{{ f.severity }}] {{ f.path }} — {{ f.type }} — {{ f.detail && f.detail.detail }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
export default {
  props: { ticketId: { type: Number, required: true }, sid: { type: String, required: true } },
  data(){ return { sftpRoot: '/', scanId: null, status: {}, findings: [], running:false, poll:null } },
  methods:{
    async start(){
      this.running = true
      const res = await axios.post('/api/scan/start', { ticket_id: this.ticketId, sid: this.sid, sftp_root: this.sftpRoot })
      this.scanId = res.data.scan_id
      this.pollStatus()
      this.poll = setInterval(this.pollStatus, 2000)
    },
    async pollStatus(){
      if(!this.scanId) return
      const s = await axios.get(`/api/scan/status/${this.scanId}`)
      this.status = s.data || {}
      if(this.status && this.status.progress>=0){
        // fetch findings small subset
        const f = await axios.get(`/api/scan/findings/${this.scanId}`)
        this.findings = f.data || []
      }
      if(this.status.status === 'DONE' || this.status.status === 'FAILED'){
        clearInterval(this.poll); this.running = false
      }
    }
  },
  unmounted(){ if(this.poll) clearInterval(this.poll) }
}
</script>
