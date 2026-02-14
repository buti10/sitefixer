<!-- src/modules/wpRepair/components/ConnectionStep.vue -->
<script setup lang="ts">
import { ref } from "vue";
import { useWpRepairStore } from "../stores/wpRepair.store";

const store = useWpRepairStore();
const wpRootInput = ref("");

function syncWpRootFromStore() {
  wpRootInput.value = store.wpRoot || "";
}

async function onConnect() {
  await store.connectAndLoadProjects();
  syncWpRootFromStore();
}

async function onSelectProject(val: string) {
  await store.setProjectRoot(val);
  syncWpRootFromStore();
}

async function onDetectWpRoot() {
  await store.detectAndSetWpRoot(5);
  syncWpRootFromStore();
}

async function onSaveWpRoot() {
  await store.setRootManually(wpRootInput.value);
  syncWpRootFromStore();
}
</script>

<template>
  <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
    <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium text-sm">
      Verbindung & WP-Root
    </div>

    <div class="p-4 space-y-4">
      <div class="text-sm">
        <span class="opacity-70">Session:</span>
        <span class="ml-1 font-mono">{{ store.sessionId || "—" }}</span>
      </div>

      <div class="flex flex-wrap gap-2">
        <button
          class="px-4 py-2 rounded-md bg-violet-600 text-white hover:bg-violet-700 text-sm disabled:opacity-60"
          :disabled="store.loading"
          @click="onConnect"
        >
          {{ store.loading ? "Bitte warten..." : "Verbindung testen" }}
        </button>

        <button
          class="px-4 py-2 rounded-md border border-black/10 dark:border-white/10 text-sm hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-60"
          :disabled="store.loading || !store.sessionId || !store.selectedProjectRoot"
          @click="onDetectWpRoot"
        >
          WP-Root automatisch finden
        </button>

        <button
          class="px-4 py-2 rounded-md bg-gray-800 text-white text-sm disabled:opacity-60"
          :disabled="!store.canDiagnose"
          @click="store.goStep('diagnose')"
        >
          Weiter zu Diagnose
        </button>
      </div>

      <!-- Projekt Auswahl -->
      <div v-if="store.sessionId" class="space-y-2">
        <div class="text-xs opacity-70">Projekt (Webspace Root)</div>
        <select
          class="w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
          :value="store.selectedProjectRoot"
          @change="onSelectProject(($event.target as HTMLSelectElement).value)"
        >
          <option value="" disabled>Bitte Projekt wählen…</option>
          <option v-for="p in store.projects" :key="p.root_path" :value="p.root_path">
            {{ p.label }}
          </option>
        </select>

        <div class="text-xs opacity-60">
          Hinweis: Erst Projekt wählen, dann WP-Root suchen.
        </div>
      </div>

      <!-- WP Root -->
      <div class="space-y-2">
        <div class="text-xs opacity-70">WP-Root</div>
        <input
          v-model="wpRootInput"
          class="w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
          placeholder="/path/to/wordpress"
        />

        <div class="flex gap-2">
          <button
            class="px-3 py-2 rounded-md border border-black/10 dark:border-white/10 text-sm hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-60"
            :disabled="store.loading || !store.sessionId"
            @click="onSaveWpRoot"
          >
            WP-Root speichern
          </button>
        </div>
      </div>

      <div v-if="store.error" class="text-xs text-red-600 dark:text-red-400">
        {{ store.error }}
      </div>
    </div>
  </div>
</template>
