#ChatDetail.vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '../stores/ChatStore'

const route = useRoute()
const chat = useChatStore()
const tid = Number(route.params.id)

const messages = computed(()=> chat.msgs(tid))
const draft = ref('')

function fmt(ts?:string|null){ if(!ts) return ''; const d=new Date(ts); return d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) }
function ticks(mId:string){ return chat.ticksFor(tid, mId) }

function scrollBottom(){ const el = document.getElementById('chat-scroll'); if (el) el.scrollTop = el.scrollHeight }

async function boot(){
  await chat.loadMessages(tid)
  nextTick(scrollBottom)
  chat.startThreadPolling(tid, 2000)
}
onMounted(boot)
onBeforeUnmount(()=> chat.stopThreadPolling(tid))

function send(){
  const text = draft.value.trim(); if(!text) return
  chat.sendMessage(tid, text).then(()=>{ draft.value=''; nextTick(scrollBottom) })
}

// „gelesen“ markieren wenn sichtbar
function onVisible(){ chat.markVisible(tid) }
</script>

<template>
  <div class="space-y-3" @mouseenter="onVisible" @focusin="onVisible">
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold">Chat #{{ tid }}</h2>
      <div class="text-xs opacity-70">{{ chat.byId(tid)?.visitor || 'Visitor' }} • {{ chat.byId(tid)?.page || '—' }}</div>
    </div>

    <div id="chat-scroll" class="h-[62vh] rounded-xl border bg-white dark:bg-[#0f1424] overflow-y-auto p-3">
      <div v-for="m in messages" :key="m.id" class="mb-2 flex" :class="m.author==='agent' ? 'justify-end' : 'justify-start'">
        <div class="max-w-[70%]">
          <div :class="m.author==='agent' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-white/10 text-gray-900 dark:text-gray-100'"
               class="rounded-2xl px-3 py-2 text-sm">{{ m.text }}</div>
          <div class="mt-0.5 text-[11px] opacity-70 flex items-center gap-1" :class="m.author==='agent' ? 'justify-end' : 'justify-start'">
            <span>{{ fmt(m.sentAt || m.deliveredAt) }}</span>
            <span v-if="m.author==='agent'">{{ ticks(m.id) }}</span>
          </div>
        </div>
      </div>
    </div>

    <form class="rounded-xl border bg-white dark:bg-[#0f1424] p-2 flex gap-2" @submit.prevent="send">
      <textarea v-model="draft" rows="1" class="flex-1 rounded border px-3 py-2 bg-transparent resize-none text-sm"
                placeholder="Nachricht…" @keydown.enter.exact.prevent="send"></textarea>
      <button class="rounded bg-blue-600 text-white px-3 py-2 hover:bg-blue-700">Senden</button>
    </form>
  </div>
</template>
