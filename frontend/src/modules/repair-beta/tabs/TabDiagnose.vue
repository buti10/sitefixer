<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="text-sm font-medium">Diagnose (Read-only)</div>
      <div class="flex gap-2">
        <button class="px-3 py-2 rounded-md border text-sm" @click="$emit('go','overview')">
          Übersicht
        </button>
        <button class="px-3 py-2 rounded-md bg-emerald-600 text-white text-sm disabled:opacity-50"
          :disabled="!w.selectedProject || w.diagnoseLoading" @click="w.runDiagnose()">
          {{ w.diagnoseLoading ? 'Läuft…' : 'Diagnose starten' }}
        </button>
      </div>
    </div>

    <div v-if="!w.selectedProject" class="p-3 rounded-md bg-amber-50 text-amber-800 text-sm">
      Bitte zuerst Root setzen (Tab “SFTP & Projekte”).
    </div>

    <div v-if="w.diagnoseError" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">
      {{ w.diagnoseError }}
    </div>

    <div v-if="w.diagnoseResult" class="p-3 rounded-md border bg-black/5 text-sm overflow-auto">
      <div class="text-xs font-semibold opacity-70 mb-2">Raw Diagnose (JSON)</div>
      <pre class="whitespace-pre-wrap text-xs">{{ JSON.stringify(w.diagnoseResult, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ w: any }>();
defineEmits<{ (e: "go", k: any): void }>();
</script>
