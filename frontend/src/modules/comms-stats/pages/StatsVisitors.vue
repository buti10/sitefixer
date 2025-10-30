<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">Visitors Stats</h1>
      <div class="flex gap-2 text-sm">
        <input type="date" v-model="from" class="border rounded px-2 py-1"/>
        <input type="date" v-model="to"   class="border rounded px-2 py-1"/>
        <button class="px-3 py-1.5 border rounded" @click="load">Aktualisieren</button>
      </div>
    </div>

    <!-- KPI-Cards -->
    <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <KpiCard label="Besucher gesamt"   :value="fmt(stats.total_visitors)"/>
      <KpiCard label="Chats gestartet"   :value="fmt(stats.chats_started)"/>
      <KpiCard label="Avg. Wartezeit"    :value="stats.avg_wait_sec ? (stats.avg_wait_sec+'s') : '—'"/>
      <KpiCard label="Co-browse Sessions":value="fmt(stats.cobrowse)"/>
    </div>

    <!-- Tabellen: Top Pages / Referrer -->
    <div class="grid lg:grid-cols-2 gap-4">
      <StatTable title="Top-Seiten"    :rows="stats.top_pages"    :cols="['url','views','chats']"/>
      <StatTable title="Top-Referrer"  :rows="stats.top_referrers":cols="['ref','visitors','chats']"/>
    </div>

    <!-- Heatmap-Stub / Uhrzeiten -->
    <div class="rounded-xl border p-4">
      <div class="font-medium mb-2">Aktivität nach Stunde</div>
      <div class="grid grid-cols-12 gap-1 text-center text-xs">
        <div v-for="(c,i) in stats.by_hour" :key="i"
             class="h-8 rounded"
             :title="i+':00 → '+c"
             :style="{ background: `rgba(59,130,246,${c/maxHour || 0})` }">
          {{ i }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'

const from = ref<string>(''); const to = ref<string>('');
const stats = reactive<any>({ total_visitors:0, chats_started:0, avg_wait_sec:0, cobrowse:0, top_pages:[], top_referrers:[], by_hour:Array(24).fill(0) })
const maxHour = computed(()=> Math.max(1, ...stats.by_hour))

function fmt(n:number){ return typeof n==='number' ? n.toLocaleString() : '—' }

async function load(){
  const q = new URLSearchParams()
  if (from.value) q.set('from', from.value)
  if (to.value)   q.set('to',   to.value)
  const r = await fetch(`/mock/stats/visitors.json?${q.toString()}`)
  Object.assign(stats, await r.json())
}
onMounted(load)
</script>

<script lang="ts">
export default { components:{
  KpiCard: {
    props:{ label:String, value:[String,Number] },
    template:`<div class="border rounded-xl p-4"><div class="text-xs opacity-60">{{label}}</div><div class="text-2xl">{{value}}</div></div>`
  },
  StatTable: {
    props:{ title:String, rows:Array, cols:Array },
    template:`
      <div class="rounded-xl border overflow-hidden">
        <div class="p-3 font-medium border-b">{{ title }}</div>
        <table class="w-full text-sm">
          <thead class="bg-black/5 dark:bg-white/5">
            <tr><th v-for="c in cols" :key="c" class="p-2 text-left capitalize">{{ c }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r,i) in rows" :key="i" class="border-t">
              <td v-for="c in cols" :key="c" class="p-2 truncate max-w-[0]">
                <a v-if="c==='url'" :href="r[c]" class="text-blue-600 underline" target="_blank">{{ r[c] }}</a>
                <span v-else>{{ r[c] ?? '—' }}</span>
              </td>
            </tr>
            <tr v-if="!rows || !rows.length"><td :colspan="cols.length" class="p-4 text-center opacity-60">Keine Daten</td></tr>
          </tbody>
        </table>
      </div>`
  }
}}
</script>
