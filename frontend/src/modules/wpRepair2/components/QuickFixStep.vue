<!-- src/modules/wpRepair/components/QuickFixStep.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { useWpRepairStore } from "../stores/wpRepair.store";
import { FIXES, type FixKey } from "../fixes/fixRegistry";
import FixCard from "../components/FixCard.vue";

const store = useWpRepairStore();

// Shared params state (nur für Fixes die Inputs brauchen)
const maxFiles = ref<number>(500);
const dropinsInput = ref<string>("object-cache.php");

const replaceMaxFiles = ref<number>(500);
const replaceMaxReplace = ref<number>(50);
const allowChanged = ref<boolean>(true);
const allowMissing = ref<boolean>(false);

const running = computed(() => store.isRunning);

function parseDropins(): string[] {
  const raw = (dropinsInput.value || "").trim();
  if (!raw) return [];
  return raw
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function getParamsForFix(key: FixKey) {
  if (key === "core_preview") return { max_files: maxFiles.value || 500 };
  if (key === "dropins_apply") return { dropins: parseDropins() };
  if (key === "core_replace_apply")
    return {
      max_files: replaceMaxFiles.value || 500,
      max_replace: replaceMaxReplace.value || 50,
      allow_changed: allowChanged.value,
      allow_missing: allowMissing.value,
    };
  return {};
}
</script>

<template>
  <div class="space-y-4">
    <div
      v-if="!store.canFix"
      class="rounded-lg p-3 text-sm bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"
    >
      Bitte zuerst in <b>Verbinden</b> Projekt wählen und WP-Root setzen.
    </div>

    <!-- Cards -->
    <div class="grid gap-4 lg:grid-cols-2">
      <FixCard
        v-for="fix in FIXES"
        :key="fix.key"
        :fix="fix"
        :disabled="store.loading || running || !store.canFix"
        :params="getParamsForFix(fix.key)"
      >
        <!-- Params Slot: Dropins -->
        <template v-if="fix.key === 'dropins_apply'" #params>
          <div class="space-y-2">
            <div class="text-xs opacity-70">
              {{ fix.ui?.paramsHint || "Kommagetrennt oder pro Zeile" }}
            </div>
            <textarea
              v-model="dropinsInput"
              class="px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm w-full min-h-[3rem]"
              placeholder="object-cache.php, advanced-cache.php"
            />
          </div>
        </template>

        <!-- Params Slot: Core Preview -->
        <template v-else-if="fix.key === 'core_preview'" #params>
          <div class="flex items-center gap-2">
            <label class="text-xs opacity-70">max_files</label>
            <input
              v-model.number="maxFiles"
              type="number"
              min="100"
              step="100"
              class="w-28 px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
            />
          </div>
        </template>

        <!-- Params Slot: Core Replace -->
        <template v-else-if="fix.key === 'core_replace_apply'" #params>
          <div class="grid gap-3 md:grid-cols-4">
            <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
              <div class="text-xs opacity-70">max_files</div>
              <input
                v-model.number="replaceMaxFiles"
                type="number"
                min="100"
                step="100"
                class="mt-1 w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
              />
            </div>

            <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
              <div class="text-xs opacity-70">max_replace</div>
              <input
                v-model.number="replaceMaxReplace"
                type="number"
                min="1"
                step="1"
                class="mt-1 w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
              />
            </div>

            <div class="rounded-md border border-black/5 dark:border-white/10 p-3 flex items-center gap-2">
              <input id="allowChanged" type="checkbox" v-model="allowChanged" />
              <label for="allowChanged" class="text-sm">allow_changed</label>
            </div>

            <div class="rounded-md border border-black/5 dark:border-white/10 p-3 flex items-center gap-2">
              <input id="allowMissing" type="checkbox" v-model="allowMissing" />
              <label for="allowMissing" class="text-sm">allow_missing</label>
            </div>
          </div>
        </template>
      </FixCard>
    </div>

    <!-- Live logs -->
    <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4">
      <div class="text-sm font-medium">Live-Logs</div>
      <div class="text-xs opacity-70 mt-1">
        Logs der laufenden Action. Nach Abschluss bleiben sie als letzter Lauf sichtbar.
      </div>

      <div class="mt-3 rounded-md bg-black/5 dark:bg-white/5 p-3 text-xs font-mono overflow-auto max-h-64">
        <div v-if="!store.actionLogs.length" class="opacity-60">Keine Logs.</div>
        <div v-else v-for="(line, i) in store.actionLogs" :key="i">{{ line }}</div>
      </div>

      <div v-if="store.error" class="mt-2 text-xs text-red-600 dark:text-red-400">
        {{ store.error }}
      </div>
    </div>
  </div>
</template>
