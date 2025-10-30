<template>
  <aside class="h-full w-64 shrink-0 relative z-30 border-r bg-white dark:bg-[#0f1424]">
    <nav class="h-full flex flex-col">
      <div class="p-4 font-semibold text-lg">Sitefixer</div>

      <!-- Core -->
      <RouterLink to="/"         class="block px-4 py-2 rounded mx-2" :class="linkClass('/')">Dashboard</RouterLink>
      <RouterLink to="/users"    class="block px-4 py-2 rounded mx-2" :class="linkClass('/users')">Users</RouterLink>
      <RouterLink to="/settings" class="block px-4 py-2 rounded mx-2" :class="linkClass('/settings')">Settings</RouterLink>

      <!-- Comms -->
      <div class="mt-4 px-4 text-xs uppercase opacity-60">Comms</div>
      <RouterLink to="/mail/inbox" class="block px-4 py-2 rounded mx-2" :class="linkClass('/mail')">Mail</RouterLink>
      <RouterLink to="/chat/inbox" class="block px-4 py-2 rounded mx-2" :class="linkClass('/chat')">Chat</RouterLink>

      <!-- Stats -->
      <div class="mt-4 px-4 text-xs uppercase opacity-60">Stats</div>
      <RouterLink to="/stats/chat"     class="block px-4 py-2 rounded mx-2" :class="linkClass('/stats/chat')">Chat-Stats</RouterLink>
      <RouterLink to="/stats/mail"     class="block px-4 py-2 rounded mx-2" :class="linkClass('/stats/mail')">Mail-Stats</RouterLink>
      <RouterLink to="/stats/visitors" class="block px-4 py-2 rounded mx-2" :class="linkClass('/stats/visitors')">Visitors</RouterLink>

      <div class="flex-1" />
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
const route = useRoute()
function linkClass(base: string) {
  const active = route.path === base || route.path.startsWith(base + '/') || (base === '/' && route.path === '/')
  return active ? 'bg-black/5 dark:bg-white/10 font-medium' : 'hover:bg-black/5 dark:hover:bg-white/10'
}
</script>
