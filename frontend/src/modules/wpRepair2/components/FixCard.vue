<!-- src/modules/wpRepair/components/FixCard.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useWpRepairStore } from "../stores/wpRepair.store";
import { renderFixSummary } from "../fixes/renderFixSummary";
import type { FixDef, FixKey } from "../fixes/fixRegistry";

// Icons (Heroicons)
import {
  ShieldCheckIcon,
  WrenchIcon,
  LockClosedIcon,
  PuzzlePieceIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from "@heroicons/vue/24/outline";

const ICONS: Record<string, any> = {
  ShieldCheckIcon,
  WrenchIcon,
  LockClosedIcon,
  PuzzlePieceIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
};

const props = defineProps<{
  fix: FixDef;
  /** params vom Parent (Inputs je Fix) */
  params?: any;
  /** optional: Parent kann die Card deaktivieren */
  disabled?: boolean;
}>();

const store = useWpRepairStore();

const lastParams = ref<any>(null);

const isBusy = computed(() => !!props.disabled || store.loading || store.isRunning);

const currentFixRunning = computed(() => store.runningFixKey === props.fix.key && store.isRunning);

const statusValue = computed(() => {
  if (currentFixRunning.value) return "running";
  if (store.lastCompletedFixKey === props.fix.key) {
    // Backend liefert meist action.status (applied/failed/partial/skipped)
    const a = store.lastCompletedAction;
    return (a?.status || a?.meta?.status || "").toString() || "done";
  }
  return "idle";
});

const badge = computed(() => {
  const v = statusValue.value.toLowerCase();
  if (v === "running") return { text: "running", cls: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-200" };
  if (["applied", "ok", "done"].includes(v)) return { text: "ok", cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200" };
  if (["partial"].includes(v)) return { text: "partial", cls: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200" };
  if (["failed", "error"].includes(v)) return { text: "failed", cls: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200" };
  if (["skipped"].includes(v)) return { text: "skipped", cls: "bg-slate-100 text-slate-800 dark:bg-slate-800/40 dark:text-slate-200" };
  return { text: "idle", cls: "bg-slate-100 text-slate-800 dark:bg-slate-800/40 dark:text-slate-200" };
});

const IconComp = computed(() => {
  const name = props.fix.ui?.icon || "";
  return ICONS[name] || ShieldCheckIcon;
});

function safeParams(p: any) {
  // FixRegistry erwartet oft {rules:{...}} etc. Wir speichern nur, damit Preview/Apply konsistent sind.
  return p ?? props.params ?? {};
}

async function doPreview(params?: any) {
  if (!props.fix.preview) return;
  lastParams.value = safeParams(params);
  await store.previewFix(props.fix.key as FixKey, lastParams.value);
}

async function doRun(params?: any) {
  lastParams.value = safeParams(params);
  // Bei Apply ist Preview für dieses Fix nicht mehr relevant
  delete store.previewCache[props.fix.key];
  await store.runFix(props.fix.key as FixKey, lastParams.value);
}

const summary = computed(() => {
  // Priorität: Preview-Daten -> sonst lastCompletedAction, wenn dieses Fix zuletzt lief -> sonst null
  const data =
    store.previewCache[props.fix.key] ??
    (store.lastCompletedFixKey === props.fix.key ? store.lastCompletedAction : null);

  if (!data) return null;

  return renderFixSummary(props.fix.key as FixKey, data);
});

async function runSummaryAction(a: any) {
  const fk = a?.fixKey as FixKey;
  if (!fk) return;

  const params = a?.params || {};
  if (a?.mode === "preview") {
    // Preview kann auch für andere Cards sein (wird in previewCache gespeichert)
    await store.previewFix(fk, params);
    return;
  }
  await store.runFix(fk, params);
}

// Wenn Fix wechselt: Preview resetten
watch(
  () => props.fix.key,
  () => {
    delete store.previewCache[props.fix.key];
    lastParams.value = null;
  }
);
</script>

<template>
  <div class="rounded-2xl border border-slate-200/70 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-start gap-3">
        <div class="mt-0.5 rounded-xl bg-slate-100 p-2 dark:bg-slate-800/50">
          <component :is="IconComp" class="h-5 w-5 text-slate-700 dark:text-slate-200" />
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100">{{ fix.title }}</h3>
            <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="badge.cls">{{ badge.text }}</span>
          </div>
          <p class="mt-1 text-xs text-slate-600 dark:text-slate-300">{{ fix.description }}</p>
          <p v-if="fix.ui?.paramsHint" class="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {{ fix.ui.paramsHint }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button
          v-if="fix.preview"
          class="rounded-xl border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-slate-900"
          :disabled="isBusy"
          @click="doPreview()"
        >
          {{ fix.ui?.previewLabel || "Preview" }}
        </button>

        <button
          class="rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          :disabled="isBusy"
          @click="doRun()"
        >
          {{ fix.ui?.runLabel || (fix.isAction ? "Apply" : "Run") }}
        </button>
      </div>
    </div>

    <div v-if="$slots.params" class="mt-4">
      <slot name="params" />
    </div>

    <!-- Summary / Recommendations -->
    <div v-if="summary" class="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/40">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <span
              class="rounded-full px-2 py-0.5 text-[11px] font-medium"
              :class="summary.variant === 'ok'
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200'
                : summary.variant === 'warn'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200'
                  : 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200'"
            >
              {{ summary.badge }}
            </span>
            <p class="text-xs font-semibold text-slate-900 dark:text-slate-100">{{ summary.title }}</p>
          </div>

          <p class="mt-1 text-xs text-slate-700 dark:text-slate-200">{{ summary.message }}</p>

          <ul v-if="summary.bullets?.length" class="mt-2 space-y-1 text-xs text-slate-600 dark:text-slate-300">
            <li v-for="(b, i) in summary.bullets" :key="i">• {{ b }}</li>
          </ul>

          <p v-if="summary.aiHint" class="mt-2 text-xs text-slate-600 dark:text-slate-300">
            <span class="font-semibold">Empfehlung:</span> {{ summary.aiHint }}
          </p>
        </div>

        <div v-if="summary.actions?.length" class="flex flex-col gap-2">
          <button
            v-for="(a, i) in summary.actions"
            :key="i"
            class="rounded-xl px-3 py-2 text-xs font-semibold disabled:opacity-50"
            :class="a.variant === 'primary'
              ? 'bg-indigo-600 text-white hover:bg-indigo-500'
              : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-900'"
            :disabled="isBusy"
            @click="runSummaryAction(a)"
          >
            {{ a.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- JSON Preview -->
    <details v-if="store.previewCache[fix.key]" class="mt-4">
      <summary class="cursor-pointer select-none text-xs font-semibold text-slate-700 dark:text-slate-200">
        Preview (JSON)
      </summary>
      <pre class="mt-2 max-h-80 overflow-auto rounded-xl bg-black p-3 text-[11px] leading-relaxed text-white">{{ JSON.stringify(store.previewCache[fix.key], null, 2) }}</pre>
    </details>

    <!-- Last completed action JSON -->
    <details v-else-if="store.lastCompletedFixKey === fix.key && store.lastCompletedAction" class="mt-4">
      <summary class="cursor-pointer select-none text-xs font-semibold text-slate-700 dark:text-slate-200">
        Result (JSON)
      </summary>
      <pre class="mt-2 max-h-80 overflow-auto rounded-xl bg-black p-3 text-[11px] leading-relaxed text-white">{{ JSON.stringify(store.lastCompletedAction, null, 2) }}</pre>
    </details>
  </div>
</template>
