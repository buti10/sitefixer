<template>
  <header class="bg-white/70 dark:bg-[#121526]/70 backdrop-blur border-b border-black/10 dark:border-white/10">
    <div class="h-12 px-4 flex items-center justify-between">
      <!-- Burger nur mobil -->
      <button
        class="md:hidden mr-2 p-2 rounded hover:bg-black/5 dark:hover:bg-white/10"
        @click="$emit('menu')"
      >
        ☰
      </button>

      <!-- Brand nur mobil, um Doppelung mit Sidebar zu vermeiden -->
      <div class="flex-1 font-medium md:hidden">
        Sitefixer
      </div>

      <!-- Rechts: User / Actions -->
      <div class="flex items-center gap-3 ml-auto">
        <button
          class="px-2 py-1 rounded hover:bg-black/5 dark:hover:bg-white/10"
          @click="$emit('toggleTheme')"
        >
          🌓
        </button>
        <span class="text-sm opacity-80 hidden sm:inline">
          Administrator (admin)
        </span>
        <button
          class="ml-2 px-3 py-1.5 rounded bg-black text-white dark:bg-white dark:text-black"
          @click="$emit('logout')"
        >
          Logout
        </button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
defineEmits<{
  (e: 'menu'): void
  (e: 'toggleTheme'): void
  (e: 'logout'): void
}>()
</script>
