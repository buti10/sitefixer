<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="text-sm font-medium">Übersicht (Triage)</div>

      <div class="flex gap-2">
        <button
          class="px-3 py-2 rounded-md border border-black/10 dark:border-white/20 text-sm hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-50"
          :disabled="!w.selectedProject"
          @click="$emit('go', 'diagnose')"
        >
          Zur Diagnose
        </button>

        <button
          class="px-3 py-2 rounded-md bg-emerald-600 text-white text-sm hover:bg-emerald-700 disabled:opacity-50"
          :disabled="!w.selectedProject || w.diagnoseLoading"
          @click="w.runDiagnose"
        >
          {{ w.diagnoseLoading ? "Läuft…" : "Diagnose starten" }}
        </button>
      </div>
    </div>

    <div v-if="!w.sessionId" class="p-3 rounded-md bg-amber-50 text-amber-800 text-sm">
      Schritt 1: SFTP verbinden (Tab “SFTP & Projekte”).
    </div>

    <div v-else-if="!w.selectedProject" class="p-3 rounded-md bg-amber-50 text-amber-800 text-sm">
      Schritt 2: WordPress-Root setzen (Tab “SFTP & Projekte” oder im Explorer).
    </div>

    <div v-else class="grid gap-4 md:grid-cols-3">
      <div class="rounded-xl border border-black/5 dark:border-white/10 p-3">
        <div class="text-xs opacity-70 mb-1">Nächster Schritt</div>
        <div class="text-sm">
          <b>Diagnose starten</b>
          <div class="text-[11px] opacity-70 mt-1">Ermittelt Ursache + priorisierte Actions.</div>
        </div>
      </div>

      <div class="rounded-xl border border-black/5 dark:border-white/10 p-3">
        <div class="text-xs opacity-70 mb-1">Scope (für später)</div>
        <div class="text-sm">
          <b>{{ w.diagnoseScopePath || w.selectedProject || "—" }}</b>
          <div class="text-[11px] opacity-70 mt-1">
            Hinweis: Diagnose-Scope ist vorbereitet. Backend nutzt aktuell noch Ticket-Root.
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-black/5 dark:border-white/10 p-3">
        <div class="text-xs opacity-70 mb-1">Letzte Diagnose</div>
        <div class="text-sm">
          <b>{{ w.diagnoseResult?.suspected_cause || "—" }}</b>
          <div class="text-[11px] opacity-70 mt-1">Wechsel zu Schnell-Fixes nach Diagnose.</div>
        </div>
      </div>
    </div>

    <div v-if="w.diagnoseError" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">
      {{ w.diagnoseError }}
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ w: any }>();
defineEmits<{ (e: "go", k: any): void }>();
</script>
