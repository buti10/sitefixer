# ChatAcceptModal.vue
<script setup lang="ts">
import { useChatUi } from '../stores/UiStore'
import { useChatStore } from '../stores/ChatStore'
const ui = useChatUi()
const chat = useChatStore()
async function accept() {
  if (ui.incoming) {
    await chat.accept(ui.incoming.id)
    await chat.fetchInbox()
  }
  ui.closeAccept()
}

</script>

<template>
  <div v-if="ui.acceptModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
    <div class="w-[96vw] max-w-md rounded-2xl border bg-white dark:bg-[#0f1424] shadow-xl p-4">
      <div class="font-semibold">Neuer Chat</div>
      <div class="mt-2 text-sm opacity-80">
        {{ ui.incoming?.visitor || 'Unbekannt' }} • #{{ ui.incoming?.id }} • {{ ui.incoming?.page || '—' }}
      </div>
      <div class="mt-4 flex justify-end gap-2">
        <button class="px-3 py-2 rounded border" @click="ui.closeAccept()">Später</button>
        <button class="px-3 py-2 rounded bg-blue-600 text-white" @click="accept">Annehmen</button>
      </div>
    </div>
  </div>
</template>
