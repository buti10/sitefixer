<!-- src/modules/wpRepair/components/FixesStep.vue -->
<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from "vue";
import { useWpRepairStore } from "../stores/wpRepair.store";

const store = useWpRepairStore();

type FixItem = {
  id: string;
  title: string;
  description: string;
  risk: "low" | "medium" | "high";
  component: any;
};

const FixMaintenance = defineAsyncComponent(() => import("../fixes/ui/FixMaintenance.vue"));
const FixPermissions = defineAsyncComponent(() => import("../fixes/ui/FixPermissions.vue"));
const FixDropins = defineAsyncComponent(() => import("../fixes/ui/FixDropins.vue"));
const FixCoreIntegrity = defineAsyncComponent(() => import("../fixes/ui/FixCoreIntegrity.vue"));
const FixCoreReplace = defineAsyncComponent(() => import("../fixes/ui/FixCoreReplace.vue"));

const fixes = computed<FixItem[]>(() => [
  {
    id: "maintenance",
    title: "Maintenance entfernen",
    description: "Entfernt .maintenance (wenn vorhanden). Sicher – kein Risiko.",
    risk: "low",
    component: FixMaintenance,
  },
  {
    id: "permissions",
    title: "Permissions anwenden",
    description: "Setzt sichere Standard-Permissions im WordPress-Root.",
    risk: "medium",
    component: FixPermissions,
  },
  {
    id: "dropins",
    title: "Drop-ins deaktivieren",
    description: "Deaktiviert problematische Cache-Dropins (z. B. object-cache.php).",
    risk: "medium",
    component: FixDropins,
  },
  {
    id: "core_integrity",
    title: "Core Integrity (Preview)",
    description: "Vergleicht WordPress-Core mit lokalem Core-Cache (read-only).",
    risk: "low",
    component: FixCoreIntegrity,
  },
  {
    id: "core_replace",
    title: "Core Replace",
    description: "Ersetzt manipulierte Core-Dateien inkl. Quarantäne & Rollback.",
    risk: "high",
    component: FixCoreReplace,
  },
]);

const openId = ref<string>("maintenance");

const canFix = computed(() => store.canFix);

function riskBadge(risk: string) {
  if (risk === "low") return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200";
  if (risk === "high") return "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200";
  return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200";
}
</script>

<template>
  <div class="space-y-4">
    <div
      v-if="!canFix"
      class="rounded-xl p-3 text-sm bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"
    >
      Bitte zuerst in <b>Verbinden</b> Projekt wählen und WP-Root setzen.
    </div>

    <!-- Accordion -->
    <div class="space-y-3">
      <div
        v-for="it in fixes"
        :key="it.id"
        class="rounded-2xl border border-slate-200/70 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"
      >
        <button
          class="w-full flex items-start justify-between gap-3 p-4 text-left"
          @click="openId = (openId === it.id ? '' : it.id)"
        >
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <div class="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {{ it.title }}
              </div>
              <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="riskBadge(it.risk)">
                {{ it.risk }}
              </span>
            </div>
            <div class="mt-1 text-xs text-slate-600 dark:text-slate-300">
              {{ it.description }}
            </div>
          </div>

          <div class="mt-0.5 shrink-0 rounded-xl border border-slate-200 px-2 py-1 text-xs text-slate-700 dark:border-slate-800 dark:text-slate-200">
            {{ openId === it.id ? "Schließen" : "Öffnen" }}
          </div>
        </button>

        <div v-if="openId === it.id" class="px-4 pb-4">
          <component :is="it.component" />
        </div>
      </div>
    </div>

    <!-- Live logs -->
    <div class="rounded-2xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-4">
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
