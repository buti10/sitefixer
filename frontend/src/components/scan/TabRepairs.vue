<template>
  <div class="space-y-4 text-sm">
    <div v-if="!scan" class="opacity-70">Kein Scan aktiv.</div>
    <div v-else>
      <div class="flex items-center gap-2">
        <button @click="loadPlan" class="px-3 py-1.5 rounded border">Dry-Run laden</button>
        <button :disabled="pending || selectedIds.length===0" @click="execute"
                class="px-3 py-1.5 rounded bg-rose-600 text-white disabled:opacity-50">
          Ausführen (geplante Aktionen)
        </button>
        <span v-if="pending" class="opacity-70">lädt…</span>
      </div>

      <div v-if="plan" class="rounded border p-3">
        <div class="font-medium mb-2">Vorgeschlagene Maßnahmen</div>
        <div class="space-y-2">
          <label v-for="a in plan.plan" :key="a.id" class="flex items-center gap-2">
            <input type="checkbox" v-model="a.selected" />
            <span class="min-w-32">{{ a.label }}</span>
            <span class="text-xs px-2 py-0.5 rounded bg-gray-100 uppercase">{{ a.risk }}</span>
            <span class="text-xs text-gray-500">({{ a.id }})</span>
          </label>
        </div>
      </div>

      <div class="rounded border p-3">
        <div class="font-medium mb-2">Aktionen-Log</div>
        <div v-if="actions.length===0" class="opacity-70">Noch keine Einträge.</div>
        <ul v-else class="space-y-1">
          <li v-for="it in actions" :key="it.id" class="flex items-center justify-between">
            <div>{{ it.action }}</div>
            <div class="text-xs opacity-70">{{ it.status }}</div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Scan } from '@/api'
import { api } from '@/api'

const props = defineProps<{ scan: Scan|null, ticketId: number, sid: string, rootPath?: string }>()
type RepairAction = { id:string; label:string; risk:'low'|'medium'|'high'; selected:boolean }
type RepairPlan = { scan_id:number; ticket_id:number; sid:string; plan:RepairAction[] }

const plan = ref<RepairPlan|null>(null)
const actions = ref<Array<{id:number; action:string; status:string}>>([])
const pending = ref(false)
const selectedIds = computed(() => plan.value ? plan.value.plan.filter(p=>p.selected).map(p=>p.id) : [])

async function loadPlan(){
  if(!props.scan) return
  pending.value = true
  try{
    const { data } = await api.get<RepairPlan>(`/repair/${props.scan.id}/plan`, {
      params: { ticket_id: props.ticketId, sid: props.sid }
    })
    plan.value = data
    const acts = await api.get(`/repair/${props.scan.id}/actions`)
    actions.value = acts.data.items
  } finally { pending.value = false }
}

async function execute(){
  if(!props.scan || !plan.value) return
  pending.value = true
  try{
    await api.post(`/repair/${props.scan.id}/execute`, {
      ticket_id: props.ticketId, sid: props.sid, actions: selectedIds.value
    })
    // <<< HIER: run aufrufen mit Root
    const root =
      props.scan?.options?.root_path ||
      props.scan?.root ||
      props.rootPath ||
      '/'
    await api.post(`/repair/${props.scan.id}/run`, { sid: props.sid, root })

    const acts = await api.get(`/repair/${props.scan.id}/actions`)
    actions.value = acts.data.items
  } finally { pending.value = false }
}
</script>
