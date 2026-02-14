# ChatMiniPanel.vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useChatStore } from '../stores/ChatStore'
import { useChatUi }   from '../stores/UiStore'

const chat = useChatStore()
const ui   = useChatUi()

const q = ref('')

onMounted(() => {
  if (chat.loadState === 'idle') chat.fetchInbox()
})

const baseItems = computed(() =>
  chat.inbox.filter(x => x.status === 'waiting' || x.status === 'active' || x.status === 'open')
)

const items = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return baseItems.value
  return baseItems.value.filter(x =>
    (x.visitor ?? '').toLowerCase().includes(s) ||
    (x.page ?? '').toLowerCase().includes(s) ||
    String(x.id).includes(s)
  )
})


function chipClass(s: 'waiting'|'active'|'open'|'closed') {
  switch (s) {
    case 'waiting': return 'bg-amber-50 text-amber-700 border-amber-200'
    case 'active':  return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    case 'open':    return 'bg-sky-50 text-sky-700 border-sky-200'
    default:        return 'bg-slate-50 text-slate-700 border-slate-200'
  }
}

function fmtAgo(iso?: string) {
  if (!iso) return '–'
  const d = new Date(iso).getTime()
  const sec = Math.max(1, Math.floor((Date.now() - d) / 1000))
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m`
  const h = Math.floor(min / 60)
  return `${h}h`
}
async function mini(id:number){ await chat.accept(id); chat.openMini?.(id); chat.markThreadRead?.(id); ui.openMini() }
async function goFull(id:number){ await chat.accept(id); chat.markThreadRead?.(id); ui.closePanel() }


</script>

<template>
  <div
    v-show="ui.panelOpen"
    class="fixed right-3 bottom-20 z-40 w-[92vw] max-w-[360px] sm:max-w-[420px]
           rounded-2xl border bg-white/95 dark:bg-[#0f1424]/95 shadow-xl
           transition pointer-events-auto"
    role="dialog" aria-label="Offene Chats"
  >
    <div class="px-3 py-2 border-b flex items-center justify-between gap-2">
      <div class="font-semibold text-sm">
        Offene Chats
        <span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/10">{{ baseItems.length }}</span>
      </div>
      <input
        v-model="q"
        class="text-xs px-2 py-1 rounded border bg-transparent w-32"
        placeholder="Suche…"
        aria-label="Chats suchen"
      />
      <button
        class="text-xs px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/10"
        @click="ui.closePanel()"
      >Schließen</button>
    </div>

    <!-- Ladezustand -->
    <div v-if="chat.loadState==='loading'" class="p-4 text-sm opacity-70">
      Lädt…
    </div>

    <div v-else class="max-h-80 overflow-auto divide-y">
      <div v-for="c in items" :key="c.id" class="p-3 text-sm">
        <div class="flex items-center justify-between gap-2">
          <div class="font-medium truncate">{{ c.visitor || 'Unbekannt' }}</div>
          <span class="px-2 py-0.5 text-[11px] rounded-full border" :class="chipClass(c.status)">
            {{ c.status }}
          </span>
        </div>

        <div class="mt-1 flex items-center justify-between opacity-80 gap-2">
          <div class="truncate max-w-[65%]">{{ c.page || '—' }}</div>
          <div class="flex items-center gap-1 text-[11px]">
            <span class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/10">{{ c.message_count ?? 0 }} msgs</span>
            <span class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/10">{{ fmtAgo(c.waiting_since) }}</span>
          </div>
        </div>

        <div class="mt-2 flex gap-2 justify-end">
          <button
            v-if="c.status==='waiting'"
            class="px-2.5 py-1.5 rounded-lg border hover:bg-black/5 dark:hover:bg-white/10"
            @click="chat.accept(c.id)"
            title="Annehmen"
          >Annehmen</button>

          <button
            class="px-2.5 py-1.5 rounded-lg border hover:bg-black/5 dark:hover:bg-white/10"
            @click="mini(c.id)"
            title="Als Mini öffnen"
          >Mini</button>

          <RouterLink
            :to="`/chat/${c.id}`"
            class="px-2.5 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
            @click="goFull(c.id)"
          >Vollbild</RouterLink>
        </div>
      </div>

      <div v-if="!items.length" class="p-4 text-center text-sm opacity-60">Keine offenen Chats</div>
    </div>
  </div>
</template>
