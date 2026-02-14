//UiStore.ts
import { defineStore } from 'pinia'
 import { ref } from 'vue'
 import type { ChatItem } from './ChatStore'
export const useChatUi = defineStore('chat-ui', () => {
  const panelOpen = ref(false)
  const miniOpen = ref(false)
  const acceptModalOpen = ref(false)
  const incoming = ref<ChatItem | null>(null)

  // rein intern, keine Reaktivität nötig
  const seenWaiting = new Set<number>()

  function openPanel(){ panelOpen.value = true }
  function closePanel(){ panelOpen.value = false }
  function togglePanel(){ panelOpen.value = !panelOpen.value }
  function openMini(){ miniOpen.value = true }
  function closeMini(){ miniOpen.value = false }
  function toggleMini(){ miniOpen.value = !miniOpen.value }

  function openAccept(c?: ChatItem){ if (c) incoming.value = c; acceptModalOpen.value = true }
  function closeAccept(){ acceptModalOpen.value = false; incoming.value = null }

  return { panelOpen, miniOpen, acceptModalOpen, incoming,
           seenWaiting, openPanel, closePanel, togglePanel,
           openMini, closeMini, toggleMini, openAccept, closeAccept }
})
