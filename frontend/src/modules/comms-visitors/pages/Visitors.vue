<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">Visitors</h1>
      <input v-model="q" placeholder="Suchen…" class="border rounded px-3 py-1 text-sm"/>
    </div>

    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="v in filtered" :key="v.id" class="rounded-xl border p-3">
        <div class="font-medium">{{ v.label }}</div>
        <div class="text-xs opacity-70">{{ v.url }}</div>
        <div class="mt-2 text-xs">Seit {{ v.since }} min aktiv</div>
        <div class="mt-3 flex gap-2">
          <button class="px-2 py-1 border rounded text-sm">Co-Browse</button>
          <button class="px-2 py-1 border rounded text-sm">Screenshot</button>
        </div>
      </div>
    </div>

    <div v-if="!filtered.length" class="p-6 text-center opacity-60">Keine aktiven Besucher</div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
const q = ref('')
const items = ref([
  { id: 1, label: 'Unbekannt (Chrome)', url: 'https://kundenseite.de/produkt', since: 3 },
  { id: 2, label: 'kunde@ex.de',        url: 'https://kundenseite.de/kontakt', since: 1 },
])
const filtered = computed(()=> items.value.filter(v =>
  !q.value || (v.label+v.url).toLowerCase().includes(q.value.toLowerCase())))
</script>
