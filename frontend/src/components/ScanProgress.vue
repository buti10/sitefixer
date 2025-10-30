<template>
  <div class="rounded-xl border p-4">
    <div class="flex items-center justify-between mb-2">
      <h3 class="font-semibold">Scan-Fortschritt</h3>
      <span class="text-xs opacity-60">{{ status || 'running' }}</span>
    </div>
    <div class="w-full h-2 rounded bg-black/10">
      <div class="h-2 rounded bg-blue-600" :style="{ width: (progress || 0) + '%' }"></div>
    </div>
    <div class="grid grid-cols-5 gap-2 text-xs mt-3">
      <div>Total: {{ counts?.total ?? 0 }}</div>
      <div>Scanned: {{ counts?.scanned ?? 0 }}</div>
      <div>Clean: {{ counts?.clean ?? 0 }}</div>
      <div>Susp.: {{ counts?.suspicious ?? 0 }}</div>
      <div>Mal.: {{ counts?.malicious ?? 0 }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Counts {
  total?: number; scanned?: number; clean?: number;
  suspicious?: number; malicious?: number; errors?: number;
}
defineProps<{
  progress?: number
  counts?: Counts
  status?: string
}>()
</script>
