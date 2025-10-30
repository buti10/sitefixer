# ChatDock.vue
<template>
  <div class="fixed right-4 bottom-4 z-40 pointer-events-auto">
    <button
      type="button"
      class="relative h-12 px-4 rounded-full shadow-lg border
             bg-white text-gray-900 dark:bg-[#0f1424] dark:text-gray-100
             flex items-center gap-2 hover:shadow-xl transition"
      @click="ui.togglePanel" aria-label="Open chat panel"
    >
      <span class="text-lg">💬</span>
      <span class="text-sm font-medium">Chat</span>

      <span v-if="badge>0"
            class="absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full
                   bg-blue-600 text-white text-[11px] leading-5 text-center">
        {{ badge }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '../stores/ChatStore'
import { useChatUi } from '../stores/UiStore'
const chat = useChatStore()
const ui = useChatUi()
// zeigt etwas, auch wenn unread=0: waiting oder offene Minis
const badge = computed(() =>
  Math.max(Number(chat.totalUnread || 0), Number(chat.waiting?.length || 0), Number(chat.windows?.length || 0))
)
</script>
