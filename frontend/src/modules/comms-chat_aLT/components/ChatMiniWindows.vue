# ChatMiniWindows.vue

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { RouterLink } from 'vue-router'
import { Picker } from 'emoji-mart-vue-fast'
import emojiData from '@emoji-mart/data'
import { useChatStore } from '../stores/ChatStore'
import { useChatUi } from '../stores/UiStore'

const chat = useChatStore()
const ui   = useChatUi()

const ids = computed(() => chat.windows)
const byId = (id: number) => chat.byId?.(id)
const msgs = (id:number) => chat.msgs?.(id) ?? []

const draft = ref<Record<number,string>>({})
const fileInput = ref<HTMLInputElement|null>(null)
const fileName = ref<Record<number,string>>({})
const showEmojiPicker = ref<Record<number,boolean>>({})

let t: number | null = null
onMounted(() => { t = window.setInterval(() => ids.value.forEach(id => chat.loadMessages(id)), 4000) })
onBeforeUnmount(() => { if (t) window.clearInterval(t) })

function toggleEmojiPicker(id:number){ showEmojiPicker.value[id] = !showEmojiPicker.value[id] }
function addEmoji(id:number, e:any){ draft.value[id] = (draft.value[id] ?? '') + e.native; showEmojiPicker.value[id] = false }
function onFileChange(e:Event, id:number){ const f = (e.target as HTMLInputElement).files?.[0]; if (f) fileName.value[id] = f.name }
function clearFile(id:number){ if (fileInput.value) fileInput.value.value = ''; fileName.value[id] = '' }

async function sendMessage(id:number){
  const text = (draft.value[id] ?? '').trim()
  if (!text && !fileName.value[id]) return
  await chat.sendMessage(id, text || `[Datei: ${fileName.value[id]}]`)
  draft.value[id] = ''; clearFile(id)
}

async function onOpen(id:number){
  await chat.loadMessages?.(id)
}

</script>

<template>
  <div v-if="ui.miniOpen && ids.length" class="fixed inset-0 z-40 pointer-events-none">
    <div
      v-for="(id, i) in ids"
      :key="id"
      class="pointer-events-auto fixed bottom-24 right-4 w-[360px] max-w-[92vw] sm:max-w-[420px]
             rounded-2xl border bg-white dark:bg-[#0f1424] shadow-xl flex flex-col"
      :style="{ transform: `translateX(-${i * 14}px)` }"
      @mouseenter="onOpen(id)"
      role="dialog"
      :aria-label="`Mini-Chat #${id}`"
    >
      <div class="px-3 py-2 flex items-center justify-between border-b">
        <div class="truncate text-sm font-medium">
          {{ byId(id)?.visitor || 'Unbekannt' }} <span class="opacity-60 text-xs">#{{ id }}</span>
        </div>
        <div class="flex items-center gap-3">
          <RouterLink :to="`/chat/${id}`" class="text-blue-600 text-sm" @click="ui.closePanel()">Vollbild</RouterLink>
          <button class="text-sm opacity-70 hover:opacity-100" type="button" @click="chat.closeMini(id)">✕</button>
        </div>
      </div>

      <div class="flex-1 p-3 text-sm overflow-auto border-b bg-white/80 dark:bg-[#0f1424]/80">
        <div v-for="m in msgs(id)" :key="m.id" class="mb-2 flex" :class="m.author==='agent' ? 'justify-end' : 'justify-start'">
          <div class="inline-block rounded-2xl px-3 py-1.5"
               :class="m.author==='agent' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-white/10 text-gray-900 dark:text-gray-100'">
            {{ m.text }}
          </div>
        </div>
      </div>

      <div v-if="fileName[id]" class="px-3 py-2 text-xs border-b bg-slate-50 dark:bg-white/10 flex items-center justify-between">
        <span class="truncate">{{ fileName[id] }}</span>
        <button class="text-red-600 text-xs" type="button" @click="clearFile(id)">✕</button>
      </div>

      <form class="flex items-end gap-2 p-3" @submit.prevent="sendMessage(id)">
        <input ref="fileInput" type="file" class="hidden" @change="e=>onFileChange(e,id)" />
        <button type="button" class="p-2 rounded border hover:bg-black/5 dark:hover:bg-white/10" title="Datei anhängen" @click="fileInput?.click()">📎</button>

        <div class="relative">
          <button type="button" class="p-2 rounded border hover:bg-black/5 dark:hover:bg-white/10" title="Emoji" @click="toggleEmojiPicker(id)">😊</button>
          <div v-if="showEmojiPicker[id]" class="absolute bottom-10 right-0 z-50 bg-white dark:bg-[#0f1424] border rounded-xl shadow-xl">
            <Picker :data="emojiData" @emoji-select="e=>addEmoji(id,e)" theme="light" :preview-position="'none'" :per-line="8" :emoji-size="22" style="max-width:260px" />
          </div>
        </div>

        <textarea
          v-model="draft[id]"
          rows="1"
          class="flex-1 rounded border px-3 py-2 bg-transparent resize-none text-sm"
          placeholder="Nachricht…"
          @keydown.enter.exact.prevent="sendMessage(id)"
        ></textarea>

        <button class="rounded bg-blue-600 text-white px-3 py-2 hover:bg-blue-700" type="submit">Senden</button>
      </form>
    </div>
  </div>
</template>

<style scoped>
textarea::-webkit-scrollbar { width: 0; }
</style>
