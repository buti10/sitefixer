<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">Mail Stats</h1>
      <div class="flex gap-2 text-sm">
        <input type="date" v-model="from" class="border rounded px-2 py-1" />
        <input type="date" v-model="to"   class="border rounded px-2 py-1" />
        <button class="px-3 py-1.5 border rounded" @click="load">Aktualisieren</button>
      </div>
    </div>

    <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <Kpi label="Ungelesen"  :value="fmt(stats.unread)" />
      <Kpi label="Eingänge"   :value="fmt(stats.received)" />
      <Kpi label="Beantwortet" :value="fmt(stats.replied)" />
      <Kpi label="Avg. First Response" :value="fmtTime(stats.avg_frt_sec)" />
    </div>

    <div class="grid lg:grid-cols-2 gap-4">
      <Card title="Top Absender">
        <table class="w-full text-sm">
          <thead class="bg-black/5 dark:bg-white/5"><tr>
            <th class="p-2 text-left">Absender</th><th class="p-2 text-left">E-Mails</th><th class="p-2 text-left">Avg. FRT</th>
          </tr></thead>
          <tbody>
            <tr v-for="(r,i) in stats.top_senders" :key="i" class="border-t">
              <td class="p-2 truncate">{{ r.from }}</td>
              <td class="p-2">{{ fmt(r.count) }}</td>
              <td class="p-2">{{ fmtTime(r.avg_frt_sec) }}</td>
            </tr>
            <tr v-if="!stats.top_senders?.length"><td class="p-4 text-center opacity-60" colspan="3">Keine Daten</td></tr>
          </tbody>
        </table>
      </Card>

      <Card title="Aktivität nach Stunde">
        <div class="grid grid-cols-12 gap-1 text-center text-xs">
          <div v-for="(c,i) in stats.by_hour" :key="i"
               class="h-8 rounded"
               :title="i+':00 → '+c"
               :style="{ background: `rgba(59,130,246,${c/maxHour || 0})` }">{{ i }}</div>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'

const from = ref(''); const to = ref('')
const stats = reactive<any>({ unread:0, received:0, replied:0, avg_frt_sec:0, top_senders:[], by_hour:Array(24).fill(0) })
const maxHour = computed(()=> Math.max(1, ...stats.by_hour))

function fmt(n:number){ return typeof n==='number' ? n.toLocaleString() : '—' }
function fmtTime(s:number){ if(!s) return '—'; const m=Math.floor(s/60), ss=s%60; return `${m}m ${ss}s` }

async function load(){
  const q = new URLSearchParams(); if(from.value) q.set('from', from.value); if(to.value) q.set('to', to.value)
  const r = await fetch(`/mock/stats/mail.json?${q.toString()}`)
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
