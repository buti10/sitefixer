<template>
  <div class="bg-gray-50 dark:bg-[#121526] text-gray-900 dark:text-gray-100">
    <aside class="hidden md:block fixed inset-y-0 left-0 w-60 bg-gray-100 dark:bg-[#141827] border-r border-gray-200 dark:border-white/10 overflow-y-auto">
      <Sidebar />
    </aside>

    <transition name="fade"><div v-if="drawer" class="fixed z-40 bg-black/40 md:hidden" @click="drawer=false"/></transition>
    <transition name="slide">
      <aside
  class="hidden md:block fixed inset-y-0 left-0 w-60
         bg-gray-100 dark:bg-[#141827]
         border-r border-gray-200 dark:border-white/10 overflow-y-auto
         z-50">
        <Sidebar @navigate="drawer=false" />
      </aside>
    </transition>

    <div class="relative min-h-screen md:pl-60 flex flex-col pointer-events-none">
      <Topbar class="sticky top-0 z-30 pointer-events-auto" @toggleTheme="toggleTheme" @logout="auth.logout()" @menu="drawer=true" />
      <main class="flex-1 overflow-y-auto p-6 pointer-events-auto"><slot /></main>

      <!-- Chat-Layer: clicks passieren durch die Hülle -->
      <div class="fixed z-20 pointer-events-none">
        <ChatDock />
        <ChatMiniPanel class="pointer-events-auto" />
        <ChatMiniWindows class="pointer-events-auto" />
        <ChatIncomingWatcher />
        <ChatAcceptModal class="pointer-events-auto" />
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
import ChatMiniPanel from '@/modules/comms-chat/components/ChatMiniPanel.vue'
import ChatMiniWindows from '@/modules/comms-chat/components/ChatMiniWindows.vue'
import ChatIncomingWatcher from '@/modules/comms-chat/components/ChatIncomingWatcher.vue'
import ChatAcceptModal from '@/modules/comms-chat/components/ChatAcceptModal.vue'
const auth = useAuth()
const drawer = ref(false)

function toggleTheme () {
  const isDark = document.documentElement.classList.toggle('dark')
  localStorage.setItem('sf_theme', isDark ? 'dark' : 'light')
}
</script>

<style>
.fade-enter-active,.fade-leave-active{transition:opacity .15s}
.fade-enter-from,.fade-leave-to{opacity:0}
.slide-enter-active,.slide-leave-active{transition:transform .2s}
.slide-enter-from,.slide-leave-to{transform:translateX(-100%)}
</style>
