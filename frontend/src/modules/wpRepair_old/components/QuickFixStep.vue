<!-- src/modules/wpRepair/components/QuickFixStep.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { useWpRepairStore } from "../stores/wpRepair.store";
import { FIXES, type FixKey } from "../fixes/fixRegistry";

const store = useWpRepairStore();

const maxFiles = ref<number>(500);
const dropinsInput = ref<string>("object-cache.php");

// optional (für später core replace UI)
const replaceMaxFiles = ref<number>(500);
const replaceMaxReplace = ref<number>(50);
const allowChanged = ref<boolean>(true);
const allowMissing = ref<boolean>(false);

const running = computed(() => store.isRunning);

const statusText = computed(() => {
  const st = store.actionStatus?.status;
  if (!st) return "—";
  if (st === "queued") return "Queued";
  if (st === "running") return "Running";
  if (st === "done") return "Done";
  if (st === "failed") return "Failed";
  return String(st);
});

const corePreview = computed(() => store.quickfix.corePreview);
const coreReplacePreview = computed(() => store.quickfix.coreReplacePreview);
const dropinsPreview = computed(() => store.quickfix.dropinsPreview);

function pill(ok: boolean) {
  return ok
    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
    : "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-200";
}

function parseDropins(): string[] {
  const raw = (dropinsInput.value || "").trim();
  if (!raw) return [];
  return raw
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

async function runFix(key: FixKey, params?: any) {
  await store.runFix(key, params);
}

async function previewFix(key: FixKey, params?: any) {
  await store.previewFix(key, params);
}

async function onCoreReplacePreview() {
  await previewFix("core_replace_apply", {
    max_files: replaceMaxFiles.value || 500,
    max_replace: replaceMaxReplace.value || 50,
    allow_changed: allowChanged.value,
    allow_missing: allowMissing.value,
  });
}

async function onCoreReplaceApply() {
  await runFix("core_replace_apply", {
    max_files: replaceMaxFiles.value || 500,
    max_replace: replaceMaxReplace.value || 50,
    allow_changed: allowChanged.value,
    allow_missing: allowMissing.value,
  });
}
</script>

<template>
  <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
    <div
      class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium text-sm flex items-center justify-between"
    >
      <span>Quick-Fix</span>

      <div class="text-xs opacity-70 flex items-center gap-2">
        <span class="opacity-60">Status:</span>
        <span class="font-mono">{{ statusText }}</span>
        <span v-if="store.runningActionId" class="opacity-60">·</span>
        <span v-if="store.runningActionId" class="font-mono">{{ store.runningActionId }}</span>
      </div>
    </div>

    <div class="p-4 space-y-4">
      <!-- Guard -->
      <div
        v-if="!store.canFix"
        class="rounded-lg p-3 text-sm bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"
      >
        Bitte zuerst in <b>Verbinden</b> Projekt wählen und WP-Root setzen.
      </div>

      <!-- Fix cards (registry-driven) -->
      <div class="grid gap-3 md:grid-cols-2">
        <!-- Maintenance -->
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4">
          <div class="text-sm font-medium">{{ FIXES[0].title }}</div>
          <div class="text-xs opacity-70 mt-1">{{ FIXES[0].description }}</div>
          <div class="mt-3">
            <button
              class="px-4 py-2 rounded-md bg-violet-600 text-white hover:bg-violet-700 text-sm disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix"
              @click="runFix('maintenance_remove')"
            >
              Fix starten
            </button>
          </div>
        </div>

        <!-- Permissions -->
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4">
          <div class="text-sm font-medium">{{ FIXES.find(f => f.key==='permissions_apply')?.title }}</div>
          <div class="text-xs opacity-70 mt-1">{{ FIXES.find(f => f.key==='permissions_apply')?.description }}</div>
          <div class="mt-3 flex gap-2">
            <button
              class="px-4 py-2 rounded-md border border-black/10 dark:border-white/10 text-sm hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix"
              @click="previewFix('permissions_apply')"
            >
              Preview
            </button>
            <button
              class="px-4 py-2 rounded-md bg-violet-600 text-white hover:bg-violet-700 text-sm disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix"
              @click="runFix('permissions_apply')"
            >
              Apply
            </button>
          </div>
        </div>

        <!-- Dropins -->
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4 md:col-span-2">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-sm font-medium">{{ FIXES.find(f => f.key==='dropins_apply')?.title }}</div>
              <div class="text-xs opacity-70 mt-1">{{ FIXES.find(f => f.key==='dropins_apply')?.description }}</div>
            </div>
            <div class="text-xs opacity-60 text-right">Kommagetrennt oder pro Zeile</div>
          </div>

          <div class="mt-3 flex flex-wrap items-center gap-2">
            <textarea
              v-model="dropinsInput"
              class="px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm w-full md:w-[28rem] min-h-[2.75rem]"
              placeholder="object-cache.php, advanced-cache.php"
            />
            <button
              class="px-4 py-2 rounded-md border border-black/10 dark:border-white/10 text-sm hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix"
              @click="previewFix('dropins_apply', { dropins: parseDropins() })"
            >
              Preview
            </button>
            <button
              class="px-4 py-2 rounded-md bg-violet-600 text-white hover:bg-violet-700 text-sm disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix || parseDropins().length===0"
              @click="runFix('dropins_apply', { dropins: parseDropins() })"
            >
              Apply
            </button>
          </div>

          <details v-if="dropinsPreview" class="mt-3 rounded-md border border-black/5 dark:border-white/10">
            <summary class="cursor-pointer px-3 py-2 text-sm font-medium select-none">Preview JSON</summary>
            <div class="px-3 pb-3">
              <pre class="text-xs overflow-auto rounded-md bg-black/5 dark:bg-white/5 p-3">{{ JSON.stringify(dropinsPreview, null, 2) }}</pre>
            </div>
          </details>
        </div>
      </div>

      <!-- Core Integrity preview -->
      <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-sm font-medium">Core Integrity (Preview)</div>
            <div class="text-xs opacity-70 mt-1">
              Vergleicht WP-Core gegen lokalen Core-Cache. Preview ist read-only.
            </div>
          </div>

          <div class="flex items-center gap-2">
            <input
              v-model.number="maxFiles"
              type="number"
              min="100"
              step="100"
              class="w-28 px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
            />
            <button
              class="px-4 py-2 rounded-md border border-black/10 dark:border-white/10 text-sm hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix"
              @click="runFix('core_preview', { max_files: maxFiles || 500 })"
            >
              Preview laden
            </button>
          </div>
        </div>

        <div v-if="corePreview?.ok" class="mt-3 grid gap-3 md:grid-cols-4">
          <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
            <div class="text-xs opacity-70">WP Version</div>
            <div class="text-sm font-medium">{{ corePreview.wp_version }}</div>
          </div>
          <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
            <div class="text-xs opacity-70">Checked</div>
            <div class="text-sm font-medium">{{ corePreview.checked }}</div>
          </div>
          <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
            <div class="text-xs opacity-70">Changed</div>
            <div class="text-sm font-medium">{{ corePreview.counts?.changed ?? "—" }}</div>
          </div>
          <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
            <div class="text-xs opacity-70">Missing</div>
            <div class="text-sm font-medium">{{ corePreview.counts?.missing ?? "—" }}</div>
          </div>

          <div class="md:col-span-4">
            <div class="inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full" :class="pill(!!corePreview.integrity_ok)">
              <span class="h-2 w-2 rounded-full" :class="corePreview.integrity_ok ? 'bg-emerald-500' : 'bg-red-500'"></span>
              {{ corePreview.integrity_ok ? "Integrity OK" : "Integrity nicht OK (Preview begrenzt / Findings vorhanden)" }}
            </div>
          </div>

          <details class="md:col-span-4 rounded-md border border-black/5 dark:border-white/10">
            <summary class="cursor-pointer px-3 py-2 text-sm font-medium select-none">Details (JSON)</summary>
            <div class="px-3 pb-3">
              <pre class="text-xs overflow-auto rounded-md bg-black/5 dark:bg-white/5 p-3">{{ JSON.stringify(corePreview, null, 2) }}</pre>
            </div>
          </details>
        </div>
      </div>

      <!-- Core Replace (optional UI, falls du es jetzt schon anzeigen willst) -->
      <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-sm font-medium">Core Replace (Preview / Apply)</div>
            <div class="text-xs opacity-70 mt-1">
              Preview zeigt geplante Ersetzungen. Apply startet eine Action mit Quarantäne/Rollback.
            </div>
          </div>

          <div class="flex items-center gap-2">
            <button
              class="px-4 py-2 rounded-md border border-black/10 dark:border-white/10 text-sm hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix"
              @click="onCoreReplacePreview"
            >
              Preview
            </button>
            <button
              class="px-4 py-2 rounded-md bg-violet-600 text-white hover:bg-violet-700 text-sm disabled:opacity-60"
              :disabled="store.loading || running || !store.canFix"
              @click="onCoreReplaceApply"
            >
              Apply
            </button>
          </div>
        </div>

        <div class="mt-3 grid gap-3 md:grid-cols-4">
          <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
            <div class="text-xs opacity-70">max_files</div>
            <input v-model.number="replaceMaxFiles" type="number" min="100" step="100"
              class="mt-1 w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm" />
          </div>

          <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
            <div class="text-xs opacity-70">max_replace</div>
            <input v-model.number="replaceMaxReplace" type="number" min="1" step="1"
              class="mt-1 w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm" />
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

        <details v-if="coreReplacePreview" class="mt-3 rounded-md border border-black/5 dark:border-white/10">
          <summary class="cursor-pointer px-3 py-2 text-sm font-medium select-none">Preview JSON</summary>
          <div class="px-3 pb-3">
            <pre class="text-xs overflow-auto rounded-md bg-black/5 dark:bg-white/5 p-3">{{ JSON.stringify(coreReplacePreview, null, 2) }}</pre>
          </div>
        </details>
      </div>

      <!-- Live logs -->
      <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4">
        <div class="text-sm font-medium">Live-Logs</div>
        <div class="text-xs opacity-70 mt-1">
          Zeigt Logs der laufenden Action. Nach “Done” bleiben sie als letzter Lauf sichtbar.
        </div>

        <div class="mt-3 rounded-md bg-black/5 dark:bg-white/5 p-3 text-xs font-mono overflow-auto max-h-64">
          <div v-if="!store.actionLogs.length" class="opacity-60">Keine Logs.</div>
          <div v-else v-for="(line, i) in store.actionLogs" :key="i">{{ line }}</div>
        </div>
      </div>

      <div v-if="store.error" class="text-xs text-red-600 dark:text-red-400">
        {{ store.error }}
      </div>
    </div>
  </div>
</template>
