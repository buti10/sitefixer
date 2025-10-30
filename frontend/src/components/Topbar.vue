<template>
  <header class="bg-white/70 dark:bg-[#121526]/70 backdrop-blur border-b border-black/10 dark:border-white/10">
    <div class="h-12 px-4 flex items-center justify-between">
      <button class="md:hidden mr-2 p-2 rounded hover:bg-black/5 dark:hover:bg-white/10" @click="$emit('menu')">☰</button>
      <div class="flex-1 font-medium">Sitefixer</div>
      <div class="flex items-center gap-3">
        <RouterLink to="/mail" class="relative inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/10">
          📧 <span class="text-sm">Mail</span>
          <span v-if="mailUnread>0"
                class="absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-blue-600 text-white text-[11px] leading-5 text-center">
            {{ mailUnread }}
          </span>
        </RouterLink>
        <RouterLink to="/chat/inbox" class="relative inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/10">
          💬 <span class="text-sm">Chat</span>
          <span v-if="chatUnread>0"
                class="absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-blue-600 text-white text-[11px] leading-5 text-center">
            {{ chatUnread }}
          </span>
        </RouterLink>
        <button class="px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/10" @click="$emit('toggleTheme')">🌓</button>
        <span class="text-sm opacity-80">Administrator (admin)</span>
        <button class="ml-2 px-3 py-1.5 rounded bg-black text-white dark:bg-white dark:text-black" @click="$emit('logout')">Logout</button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useMailStore } from '@/modules/comms-mail/stores/MailStore'
import { useChatStore } from '@/modules/comms-chat/stores/ChatStore'
const mail = useMailStore(); const chat = useChatStore()
onMounted(()=>{ mail.fetchInbox(); chat.fetchInbox(); setInterval(()=>{ mail.fetchInbox(); chat.fetchInbox() }, 30000) })
defineEmits<{(e:'menu'):void,(e:'toggleTheme'):void,(e:'logout'):void}>()
</script>
