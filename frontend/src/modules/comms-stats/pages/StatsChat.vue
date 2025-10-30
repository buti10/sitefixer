<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">Chat Stats</h1>
      <div class="flex gap-2 text-sm">
        <input type="date" v-model="from" class="border rounded px-2 py-1" />
        <input type="date" v-model="to"   class="border rounded px-2 py-1" />
        <button class="px-3 py-1.5 border rounded" @click="load">Aktualisieren</button>
      </div>
    </div>

    <div class="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <Kpi label="Wartend"        :value="fmt(stats.waiting)" />
      <Kpi label="Offen"          :value="fmt(stats.open)" />
      <Kpi label="Abgeschlossen"  :value="fmt(stats.closed)" />
      <Kpi label="Avg. Wartezeit" :value="fmtTime(stats.avg_wait_sec)" />
      <Kpi label="Avg. Dauer"     :value="fmtTime(stats.avg_handle_sec)" />
    </div>

    <div class="grid lg:grid-cols-2 gap-4">
      <Card title="Top-Seiten (Chats)">
        <table class="w-full text-sm">
          <thead class="bg-black/5 dark:bg-white/5"><tr>
            <th class="p-2 text-left">URL</th><th class="p-2 text-left">Chats</th><th class="p-2 text-left">Avg. Wait</th>
          </tr></thead>
          <tbody>
            <tr v-for="(r,i) in stats.top_pages" :key="i" class="border-t">
              <td class="p-2 truncate max-w-[0]"><a :href="r.url" target="_blank" class="text-blue-600 underline">{{ r.url }}</a></td>
              <td class="p-2">{{ fmt(r.chats) }}</td>
              <td class="p-2">{{ fmtTime(r.avg_wait_sec) }}</td>
            </tr>
            <tr v-if="!stats.top_pages?.length"><td class="p-4 text-center opacity-60" colspan="3">Keine Daten</td></tr>
          </tbody>
        </table>
      </Card>

      <Card title="Agenten-Performance">
        <table class="w-full text-sm">
          <thead class="bg-black/5 dark:bg-white/5"><tr>
            <th class="p-2 text-left">Agent</th><th class="p-2 text-left">Chats</th><th class="p-2 text-left">Avg. FRT</th><th class="p-2 text-left">CSAT</th>
          </tr></thead>
          <tbody>
            <tr v-for="(a,i) in stats.agents" :key="i" class="border-t">
              <td class="p-2">{{ a.name }}</td>
              <td class="p-2">{{ fmt(a.chats) }}</td>
              <td class="p-2">{{ fmtTime(a.avg_frt_sec) }}</td>
              <td class="p-2">{{ a.csat != null ? a.csat.toFixed(2) : '—' }}</td>
            </tr>
            <tr v-if="!stats.agents?.length"><td class="p-4 text-center opacity-60" colspan="4">Keine Daten</td></tr>
          </tbody>
        </table>
      </Card>
    </div>

    <Card title="Aktivität nach Stunde">
      <div class="grid grid-cols-12 gap-1 text-center text-xs">
        <div v-for="(c,i) in stats.by_hour" :key="i"
             class="h-8 rounded"
             :title="i+':00 → '+c"
             :style="{ background: `rgba(34,197,94,${c/maxHour || 0})` }">{{ i }}</div>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'

const from = ref(''); const to = ref('')
const stats = reactive<any>({
  waiting:0, open:0, closed:0, avg_wait_sec:0, avg_handle_sec:0,
  top_pages:[], agents:[], by_hour:Array(24).fill(0)
})
const maxHour = computed(()=> Math.max(1, ...stats.by_hour))

function fmt(n:number){ return typeof n==='number' ? n.toLocaleString() : '—' }
function fmtTime(s:number){ if(!s) return '—'; const m=Math.floor(s/60), ss=s%60; return `${m}m ${ss}s` }

async function load(){
  const q = new URLSearchParams(); if(from.value) q.set('from', from.value); if(to.value) q.set('to', to.value)
  const r = await fetch(`/mock/stats/chat.json?${q.toString()}`)
  Object.assign(stats, await r.json())
}
onMounted(load)
</script>

<script lang="ts">
export default {
  components:{
    Kpi:{ props:{label:String,value:[String,Number]}, template:`<div class="border rounded-xl p-4"><div class="text-xs opacity-60">{{label}}</div><div class="text-2xl">{{value}}</div></div>`},
    Card:{ props:{title:String}, template:`<div class="rounded-xl border overflow-hidden"><div class="p-3 font-medium border-b">{{title}}</div><div class="p-3"><slot/></div></div>`}
  }
}
</script>
