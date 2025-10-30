<!-- layouts/AppShell.vue -->
<template>
  <div class="min-h-screen bg-gray-50 dark:bg-[#121526] text-gray-900 dark:text-gray-100">
    <div class="flex min-h-screen">
      <Sidebar :open="sidebar" @close="sidebar=false" />
      <div class="flex-1 flex flex-col">
        <Topbar
          class="w-full sticky top-0 z-20"
          :user="auth.user"
          @menu="sidebar=!sidebar"          <!-- <- statt @toggleSidebar -->
          @toggleTheme="toggleTheme"
          @logout="auth.logout()"
        />
        <main class="relative z-0 flex-1 p-6"><slot /></main>

        <!-- Global schwebender Chat-Dock -->
        <ChatDock />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '../stores/auth'
import Sidebar from '../components/Sidebar.vue'
import Topbar from '../components/Topbar.vue'
import ChatDock from '@/modules/comms-chat/components/ChatDock.vue'

const sidebar = ref(false)
const auth = useAuth()
function toggleTheme(){
  const isDark = document.documentElement.classList.toggle('dark')
  localStorage.setItem('sf_theme', isDark ? 'dark' : 'light')
}
</script>
