<template>
  <div class="rounded-xl border p-4 text-sm">
    <div class="font-semibold mb-2">Findings</div>
    <div v-if="!items?.length" class="opacity-70">Keine Findings.</div>
    <ul v-else class="space-y-2">
      <li v-for="(f,i) in items" :key="i" class="p-2 rounded border">
        <div class="text-xs opacity-70">{{ f.path }}</div>
        <div class="text-sm">{{ f.kind }} · {{ f.severity }}</div>
        <pre v-if="f.detail?.snippet" class="mt-1 bg-black/5 p-2 rounded text-xs overflow-x-auto">{{ f.detail.snippet }}</pre>
      </li>
    </ul>
  </div>
</template>
<script setup lang="ts">
defineProps<{ items?: any[] }>()
</script>
