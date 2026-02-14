<script setup lang="ts">
const props = defineProps<{
  active: string;
  canDiagnose: boolean;
}>();
const emit = defineEmits<{
  (e: "select", step: "connect" | "diagnose" | "quickfix" | "history"): void;
}>();

const items = [
  { key: "connect", label: "1) Verbinden" },
  { key: "diagnose", label: "2) Diagnose" },
  { key: "quickfix", label: "3) Quick-Fix" },
  { key: "history", label: "4) History" },
] as const;
</script>

<template>
  <div class="space-y-2">
    <button
      v-for="it in items"
      :key="it.key"
      class="w-full text-left px-3 py-2 rounded-lg border border-black/5 dark:border-white/10"
      :class="[
        active === it.key
          ? 'bg-violet-600 text-white border-transparent'
          : 'bg-white dark:bg-[#0f1424] hover:bg-black/5 dark:hover:bg-white/5',
        (it.key !== 'connect' && !canDiagnose) ? 'opacity-50 cursor-not-allowed' : ''
      ]"
      :disabled="it.key !== 'connect' && !canDiagnose"
      @click="emit('select', it.key as any)"
    >
      <div class="text-sm font-medium">{{ it.label }}</div>
    </button>
  </div>
</template>
