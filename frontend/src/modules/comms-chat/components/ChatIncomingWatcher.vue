# ChatIncomingWatcher.vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useChatStore } from '../stores/ChatStore'
import { useChatUi } from '../stores/UiStore'

const chat = useChatStore()
const ui = useChatUi()

let t: number | null = null
let audio: HTMLAudioElement

function tick() {
  const before = new Set(ui.seenWaiting)
  const now = chat.inbox.filter(x => x.status === 'waiting')
  for (const c of now) {
    if (!before.has(c.id)) {
      ui.seenWaiting.add(c.id)
      ui.openAccept(c)
      try { audio.play() } catch {}
    }
  }
}

onMounted(async () => {
  audio = new Audio('/sounds/incoming.mp3')
  await chat.fetchInbox()          // ← richtiges casing
  tick()
  t = window.setInterval(async () => { await chat.fetchInbox(); tick() }, 5000)
})

onBeforeUnmount(() => { if (t) window.clearInterval(t) })
</script>

<template><span class="hidden" /></template>
