<!-- src/components/SidebarMobile.vue -->
<script setup lang="ts">
import { useRoute, RouterLink } from 'vue-router'
import { ref, onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'

const emit = defineEmits<{ (e: 'navigate'): void }>()

const route = useRoute()

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

function close() {
  emit('navigate')
}

// Live-Besucher (für Badge)
const onlineCount = ref<number | null>(null)
let timer: number | null = null

async function fetchOnlineCount() {
  try {
    const res = await api.get('/live/visitors')
    onlineCount.value = res.data?.total_online ?? 0
  } catch (e) {}
}

onMounted(() => {
  fetchOnlineCount()
  timer = window.setInterval(fetchOnlineCount, 3000)
})

onBeforeUnmount(() => {
  if (timer) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>

<template>
  <div class="flex flex-col h-full bg-white dark:bg-[#141827]">
    <!-- Header mit X -->
    <div class="h-12 px-4 flex items-center justify-between border-b border-black/10 dark:border-white/10">
      <div class="flex items-center gap-2">
        <div class="h-7 w-7 rounded-xl border border-black/10 dark:border-white/15 flex items-center justify-center text-xs font-semibold">
          SF
        </div>
        <div class="font-semibold">Sitefixer</div>
      </div>
      <button
        class="p-2 rounded hover:bg-black/5 dark:hover:bg-white/10"
        @click="close"
        aria-label="Close"
      >
        <svg class="h-5 w-5" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>

    <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-6 text-sm">
      <!-- Überblick -->
      <div>
        <div class="px-2 text-[11px] font-semibold tracking-wide text-gray-400 uppercase mb-2">
          Überblick
        </div>

        <RouterLink
          to="/"
          class="flex items-center gap-2 px-2 py-2 rounded-lg"
          :class="isActive('/') ? 'bg-black text-white dark:bg-white dark:text-black' : 'hover:bg-black/5 dark:hover:bg-white/10'"
          @click="close"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="9" rx="1" />
            <rect x="14" y="3" width="7" height="5" rx="1" />
            <rect x="14" y="11" width="7" height="10" rx="1" />
            <rect x="3" y="15" width="7" height="6" rx="1" />
          </svg>
          <span>Dashboard</span>
        </RouterLink>

        <RouterLink
          to="/users"
          class="flex items-center gap-2 px-2 py-2 rounded-lg mt-1"
          :class="isActive('/users') ? 'bg-black text-white dark:bg-white dark:text-black' : 'hover:bg-black/5 dark:hover:bg-white/10'"
          @click="close"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="8" r="3" />
            <path d="M6 19c0-2.2 2.1-4 6-4s6 1.8 6 4" />
          </svg>
          <span>Users</span>
        </RouterLink>

        <RouterLink
          to="/settings"
          class="flex items-center gap-2 px-2 py-2 rounded-lg mt-1"
          :class="isActive('/settings') ? 'bg-black text-white dark:bg-white dark:text-black' : 'hover:bg-black/5 dark:hover:bg-white/10'"
          @click="close"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 .6 1.65 1.65 0 0 0-.33 1.05V22a2 2 0 0 1-4 0v-.06A1.65 1.65 0 0 0 8 19.4 1.65 1.65 0 0 0 6.18 19l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15 1.65 1.65 0 0 0 4 14a1.65 1.65 0 0 0-1-.6H3a2 2 0 0 1 0-4h.06A1.65 1.65 0 0 0 4.6 8 1.65 1.65 0 0 0 5 6.18l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6 1.65 1.65 0 0 0 10 4h.06a2 2 0 0 1 3.88 0H14" />
          </svg>
          <span>Settings</span>
        </RouterLink>
      </div>

      <!-- Kommunikation -->
      <div>
        <div class="px-2 text-[11px] font-semibold tracking-wide text-gray-400 uppercase mb-2">
          Kommunikation
        </div>

        <RouterLink
          to="/comms/woot"
          class="flex items-center justify-between px-2 py-2 rounded-lg"
          :class="isActive('/comms/woot') ? 'bg-black text-white dark:bg-white dark:text-black' : 'hover:bg-black/5 dark:hover:bg-white/10'"
          @click="close"
        >
          <div class="flex items-center gap-2">
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 5h16v9H7l-3 3z" />
            </svg>
            <span>Chatwoot</span>
          </div>
        </RouterLink>
      </div>

      <!-- Monitoring -->
      <div>
        <div class="px-2 text-[11px] font-semibold tracking-wide text-gray-400 uppercase mb-2">
          Monitoring
        </div>

        <RouterLink
          to="/live-visitors"
          class="flex items-center justify-between px-2 py-2 rounded-lg"
          :class="isActive('/live-visitors') ? 'bg-black text-white dark:bg-white dark:text-black' : 'hover:bg-black/5 dark:hover:bg-white/10'"
          @click="close"
        >
          <div class="flex items-center gap-2">
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="9" cy="9" r="3" />
              <circle cx="17" cy="9" r="3" />
              <path d="M4 20c0-2.2 2-4 5-4" />
              <path d="M13 16c3 0 5 1.8 5 4" />
            </svg>
            <span>Live Besucher</span>
          </div>

          <span
            v-if="onlineCount !== null"
            class="inline-flex items-center justify-center rounded-full text-[11px] px-2 py-0.5 bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-100"
          >
            {{ onlineCount }}
          </span>
        </RouterLink>
      </div>
    </nav>
  </div>
</template>
