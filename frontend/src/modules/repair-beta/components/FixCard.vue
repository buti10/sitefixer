#src/modules/repair-beta/components/FixCard.vue
<template>
  <div class="rounded-2xl border p-4 bg-white hover:shadow-sm transition">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="text-sm font-semibold truncate">{{ title }}</div>
        <div class="text-xs opacity-70 mt-1">{{ desc }}</div>
      </div>

      <button class="px-3 py-2 rounded-xl border text-sm shrink-0 disabled:opacity-50"
              :disabled="disabled"
              @click="$emit('run')">
        {{ busy ? "Läuft…" : "Start" }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; desc: string; busy?: boolean; disabled?: boolean }>();
defineEmits<{ (e: "run"): void }>();
</script>
