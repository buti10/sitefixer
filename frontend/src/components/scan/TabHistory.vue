#TabHistory.vue
<template>
  <div class="text-sm divide-y">
    <div v-for="s in items" :key="s.id" class="py-2 flex items-center justify-between">
      <div class="flex flex-col">
        <div class="font-mono text-xs opacity-60">{{ s.created_at ?? '' }}</div>
        <div>#{{ s.id }} · <span class="uppercase">{{ s.status }}</span></div>
      </div>
      <div class="flex items-center gap-2">
        <div class="font-mono w-14 text-right">{{ s.progress ?? 0 }}%</div>
        <button class="px-2 py-1 rounded border" @click="$emit('select', s)">Öffnen</button>
        <button class="px-2 py-1 rounded border text-rose-700" @click="$emit('remove', s)">Löschen</button>
      </div>
    </div>
    <div v-if="!items || items.length===0" class="opacity-70 p-3">Kein Verlauf.</div>
  </div>
</template>
<script setup lang="ts">
import type { Scan } from '@/api'
defineProps<{ items: Scan[] }>()
defineEmits<{ (e:'select', s:Scan):void; (e:'remove', s:Scan):void }>()
</script>
