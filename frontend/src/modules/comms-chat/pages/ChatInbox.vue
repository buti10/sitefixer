<!-- modules/comms-chat/pages/ChatInbox.vue -->
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useChatStore } from '../stores/ChatStore'
import { RouterLink } from 'vue-router'

const chat = useChatStore()
const q = ref('')

onMounted(() => chat.startInboxPolling(5000))
onBeforeUnmount(() => chat.stopInboxPolling())


const list = computed(()=>{
  const s = q.value.trim().toLowerCase()
  const items = chat.inbox
  if(!s) return items
  return items.filter(x =>
    (x.visitor ?? '').toLowerCase().includes(s) ||
    (x.page ?? '').toLowerCase().includes(s) ||
    String(x.id).includes(s)
  )
})
function badgeClass(s:'waiting'|'active'|'open'|'closed'){
  if (s==='waiting') return 'bg-amber-100 text-amber-800'
  if (s==='active')  return 'bg-emerald-100 text-emerald-800'
  if (s==='open')    return 'bg-sky-100 text-sky-800'
  return 'bg-slate-100 text-slate-700'
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold">Chat Inbox</h1>
      <input v-model="q" class="w-60 max-w-[70vw] px-3 py-2 rounded border bg-transparent" placeholder="Suchen…" />
    </div>

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div v-for="c in list" :key="c.id" class="rounded-2xl border bg-white dark:bg-[#0f1424] p-3 shadow-sm">
        <div class="flex items-center justify-between gap-2">
          <div class="font-medium truncate">{{ c.visitor || 'Visitor' }}</div>
          <span class="px-2 py-0.5 text-[11px] rounded-full" :class="badgeClass(c.status)">{{ c.status }}</span>
        </div>
        <div class="mt-1 text-xs opacity-80 truncate" title="Herkunft">{{ c.page || '—' }}</div>
        <div class="mt-1 text-xs opacity-60 flex items-center gap-3">
          <span class="inline-flex items-center gap-1"><span>🕒</span>{{ c.waiting_since ? new Date(c.waiting_since).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '—' }}</span>
          <span class="inline-flex items-center gap-1"><span>👤</span>{{ c.assignee || 'frei' }}</span>
          <span class="inline-flex items-center gap-1"><span>💬</span>{{ c.message_count ?? 0 }}</span>
        </div>
        <div class="mt-3 flex gap-2 justify-end">
          <RouterLink :to="`/chat/${c.id}`" class="px-2.5 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700">Öffnen</RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>
