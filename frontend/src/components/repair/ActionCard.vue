<template>
  <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm p-4 space-y-2">
    <div class="font-medium text-sm">{{ title }}</div>
    <div class="text-xs text-gray-500 dark:text-gray-400 leading-snug">{{ desc }}</div>
    <button
      class="w-full px-3 py-2 rounded-md text-sm text-white disabled:opacity-50"
      :class="busy ? 'bg-gray-400 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-700'"
      :disabled="busy"
      @click="$emit('run')"
    >
      {{ busy ? 'Läuft…' : 'Ausführen' }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  desc: string
  busy?: boolean
}>()

defineEmits<{
  (e: 'run'): void
}>()
</script>
