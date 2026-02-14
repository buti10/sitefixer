<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '../stores/auth'
import Sidebar from '../components/Sidebar.vue'          // Desktop
import SidebarMobile from '../components/SidebarMobile.vue' // Mobile
import Topbar from '../components/Topbar.vue'

const auth = useAuth()
const drawer = ref(false)

function toggleTheme () {
  const isDark = document.documentElement.classList.toggle('dark')
  localStorage.setItem('sf_theme', isDark ? 'dark' : 'light')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-[#121526] text-gray-900 dark:text-gray-100">
    <!-- Overlay nur mobil -->
    <transition name="fade">
      <div
        v-if="drawer"
        class="fixed inset-0 z-40 bg-black/40 md:hidden"
        @click="drawer = false"
      />
    </transition>

    <!-- Desktop-Sidebar -->
    <aside
      class="hidden md:flex fixed inset-y-0 left-0 w-60
             bg-white/90 dark:bg-[#141827]
             border-r border-gray-200 dark:border-white/10
             backdrop-blur-sm
             z-30"
    >
      <Sidebar />
    </aside>

    <!-- Mobile Offcanvas Sidebar -->
    <transition
      enter-active-class="transform transition ease-in-out duration-300"
      enter-from-class="-translate-x-full"
      enter-to-class="translate-x-0"
      leave-active-class="transform transition ease-in-out duration-300"
      leave-from-class="translate-x-0"
      leave-to-class="-translate-x-full"
    >
      <aside
        v-if="drawer"
        class="fixed inset-y-0 left-0 w-72 max-w-[80vw]
               bg-white dark:bg-[#141827]
               border-r border-gray-200 dark:border-white/10
               shadow-xl
               z-50
               md:hidden"
      >
        <SidebarMobile @navigate="drawer = false" />
      </aside>
    </transition>

    <!-- Inhalt -->
    <div class="relative flex flex-col min-h-screen md:pl-60">
      <Topbar
        class="sticky top-0 z-20"
        @toggleTheme="toggleTheme"
        @logout="auth.logout()"
        @menu="drawer = true"
      />

      <main class="flex-1 overflow-y-auto p-4 md:p-6">
        <slot />
      </main>
    </div>
  </div>
</template>
