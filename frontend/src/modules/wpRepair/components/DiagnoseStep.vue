<!-- src/modules/wpRepair/components/DiagnoseStep.vue -->
<script setup lang="ts">
import { computed } from "vue";
import { useWpRepairStore } from "../stores/wpRepair.store";

const store = useWpRepairStore();

const diag = computed<any>(() => store.diagnose?.summary || null);

const wpRoot = computed(() => diag.value?.wp_root || store.wpRoot || "—");
const wpVersion = computed(() => diag.value?.wp_version || "—");

const files = computed<Record<string, boolean>>(() => diag.value?.files || {});
const paths = computed<Record<string, boolean>>(() => diag.value?.paths || {});

function ok(v: any) {
  return v === true;
}

const hasHtaccess = computed(() => ok(files.value[".htaccess"]));
const hasWpConfig = computed(() => ok(files.value["wp-config.php"]));
const hasMaintenance = computed(() => ok(files.value[".maintenance"]));
const hasVersionPhp = computed(() => ok(files.value["version.php"]));
const hasWpContent = computed(() => ok(paths.value["wp-content"]));
const hasUploads = computed(() => ok(paths.value["uploads"]));

const findings = computed(() => store.diagnose?.findings || []);

const lastRunText = computed(() => {
  if (!store.diagnose?.lastRunAt) return "";
  try {
    return new Date(store.diagnose.lastRunAt).toLocaleString();
  } catch {
    return store.diagnose.lastRunAt;
  }
});

// --------------------
// Overall status (Ampel)
// --------------------
const overall = computed(() => {
  if (!diag.value) {
    return {
      key: "unknown" as const,
      icon: "•",
      title: "Noch keine Diagnose",
      subtitle: "Bitte Diagnose starten",
      cls: "bg-slate-50 text-slate-800 dark:bg-white/5 dark:text-slate-200",
    };
  }

  if (hasMaintenance.value) {
    return {
      key: "warning" as const,
      icon: "⚠",
      title: "Maintenance Mode aktiv",
      subtitle: "Empfohlen: Maintenance entfernen (Quick-Fix)",
      cls: "bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200",
    };
  }

  // If critical structure missing -> error
  if (!hasWpConfig.value || !hasWpContent.value) {
    return {
      key: "bad" as const,
      icon: "✖",
      title: "Grundstruktur unvollständig",
      subtitle: "wp-config/wp-content fehlt oder nicht lesbar",
      cls: "bg-red-50 text-red-800 dark:bg-red-500/15 dark:text-red-200",
    };
  }

  return {
    key: "ok" as const,
    icon: "✓",
    title: "Grundprüfung bestanden",
    subtitle: "WordPress-Struktur vorhanden und erreichbar",
    cls: "bg-emerald-50 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200",
  };
});

// --------------------
// Timeline / Progress
// --------------------
const timeline = computed(() => {
  return [
    { label: "Verbunden", ok: !!store.sessionId && store.connectionOk },
    { label: "Projekt gewählt", ok: !!store.selectedProjectRoot },
    { label: "WP-Root gesetzt", ok: !!store.wpRoot },
    { label: "Diagnose abgeschlossen", ok: !!diag.value },
  ];
});

// --------------------
// UI helpers
// --------------------
function badgeClass(v: boolean) {
  return v
    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
    : "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-200";
}
function dotClass(v: boolean) {
  return v ? "bg-emerald-500" : "bg-red-500";
}
function pill(v: boolean, okText: string, badText: string) {
  return v ? okText : badText;
}
function pillGood(v: boolean) {
  // for "should be false" states like maintenance
  return v ? "aktiv" : "deaktiviert";
}
function pillClassGood(isGood: boolean) {
  return isGood
    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
    : "bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200";
}
function dotClassGood(isGood: boolean) {
  return isGood ? "bg-emerald-500" : "bg-amber-500";
}
</script>

<template>
  <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
    <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium text-sm">
      Diagnose
    </div>

    <div class="p-4 space-y-4">
      <!-- Actions row -->
      <div class="flex flex-wrap items-center gap-3">
        <button
          class="px-4 py-2 rounded-md bg-violet-600 text-white hover:bg-violet-700 text-sm disabled:opacity-60"
          :disabled="store.loading || !store.canDiagnose"
          @click="store.runDiagnose()"
        >
          {{ store.loading ? "Bitte warten..." : "Diagnose starten" }}
        </button>

        <div v-if="store.diagnose?.lastRunAt" class="text-xs opacity-70">
          Letzter Lauf: {{ lastRunText }}
        </div>
      </div>

      <!-- Overall status (Ampel) -->
      <div class="rounded-lg px-4 py-3 flex items-start gap-3" :class="overall.cls">
        <div class="text-lg leading-none mt-0.5">{{ overall.icon }}</div>
        <div class="min-w-0">
          <div class="text-sm font-medium">{{ overall.title }}</div>
          <div class="text-xs opacity-80 mt-0.5">{{ overall.subtitle }}</div>
        </div>
      </div>

      <!-- Mini timeline -->
      <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
        <div class="text-xs opacity-70 mb-2">Workflow</div>
        <div class="flex flex-wrap gap-2">
          <div
            v-for="(t, i) in timeline"
            :key="i"
            class="inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full border border-black/10 dark:border-white/10"
            :class="t.ok
              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200'
              : 'bg-black/5 text-black/70 dark:bg-white/5 dark:text-white/70'"
          >
            <span class="h-2 w-2 rounded-full" :class="t.ok ? 'bg-emerald-500' : 'bg-slate-400'"></span>
            {{ t.label }}
          </div>
        </div>
      </div>

      <!-- Info cards -->
      <div v-if="diag" class="grid gap-3 md:grid-cols-6">
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3 md:col-span-1">
          <div class="text-xs opacity-70">WP Version</div>
          <div class="mt-1 text-sm font-semibold">{{ wpVersion }}</div>
        </div>

        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3 md:col-span-3">
          <div class="text-xs opacity-70">WP Root</div>
          <div class="mt-1 text-sm font-medium break-all">{{ wpRoot }}</div>
        </div>

        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3 md:col-span-1">
          <div class="text-xs opacity-70">wp-config.php</div>
          <div
            class="mt-2 inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full"
            :class="badgeClass(hasWpConfig)"
          >
            <span class="h-2 w-2 rounded-full" :class="dotClass(hasWpConfig)"></span>
            {{ pill(hasWpConfig, "vorhanden", "fehlt") }}
          </div>
        </div>

        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3 md:col-span-1">
          <div class="text-xs opacity-70">Maintenance</div>
          <div
            class="mt-2 inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full"
            :class="pillClassGood(!hasMaintenance)"
          >
            <span class="h-2 w-2 rounded-full" :class="dotClassGood(!hasMaintenance)"></span>
            {{ hasMaintenance ? "aktiv" : "deaktiviert" }}
          </div>
        </div>
      </div>

      <!-- Secondary checks -->
      <div v-if="diag" class="grid gap-3 md:grid-cols-4">
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
          <div class="text-xs opacity-70">.htaccess</div>
          <div
            class="mt-2 inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full"
            :class="badgeClass(hasHtaccess)"
          >
            <span class="h-2 w-2 rounded-full" :class="dotClass(hasHtaccess)"></span>
            {{ pill(hasHtaccess, "vorhanden", "fehlt") }}
          </div>
        </div>

        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
          <div class="text-xs opacity-70">version.php</div>
          <div
            class="mt-2 inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full"
            :class="badgeClass(hasVersionPhp)"
          >
            <span class="h-2 w-2 rounded-full" :class="dotClass(hasVersionPhp)"></span>
            {{ pill(hasVersionPhp, "vorhanden", "fehlt") }}
          </div>
        </div>

        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
          <div class="text-xs opacity-70">wp-content</div>
          <div
            class="mt-2 inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full"
            :class="badgeClass(hasWpContent)"
          >
            <span class="h-2 w-2 rounded-full" :class="dotClass(hasWpContent)"></span>
            {{ pill(hasWpContent, "vorhanden", "fehlt") }}
          </div>
        </div>

        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
          <div class="text-xs opacity-70">uploads</div>
          <div
            class="mt-2 inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full"
            :class="badgeClass(hasUploads)"
          >
            <span class="h-2 w-2 rounded-full" :class="dotClass(hasUploads)"></span>
            {{ pill(hasUploads, "erreichbar", "fehlt") }}
          </div>
        </div>
      </div>

      <!-- Summary collapsible (default closed) -->
      <details
        v-if="diag"
        class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020]"
      >
        <summary class="cursor-pointer px-3 py-2 text-sm font-medium select-none flex items-center gap-2">
          <span class="opacity-70">▸</span>
          <span>Technische Details (JSON)</span>
          <span class="ml-auto text-xs opacity-60">nur für Debug</span>
        </summary>
        <div class="px-3 pb-3">
          <pre class="text-xs overflow-auto rounded-md bg-black/5 dark:bg-white/5 p-3">{{ JSON.stringify(diag, null, 2) }}</pre>
        </div>
      </details>

      <!-- Findings -->
      <div class="space-y-2">
        <div class="text-sm font-medium">Findings</div>

        <div v-if="!findings.length" class="text-sm opacity-70">
          Keine Findings (oder Diagnose noch nicht ausgeführt).
        </div>

        <div v-else class="space-y-2">
          <div
            v-for="(f, idx) in findings"
            :key="idx"
            class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="text-sm font-medium">
                  {{ f.title || f.code || "Finding" }}
                </div>
                <div v-if="f.message || f.details" class="text-xs opacity-70 mt-1">
                  {{ f.message || f.details }}
                </div>
                <div v-if="f.path" class="text-xs font-mono mt-2 break-all opacity-80">
                  {{ f.path }}
                </div>
              </div>

              <!-- Placeholder for future quickfix actions -->
              <div v-if="f.quickfix" class="shrink-0">
                <button class="text-xs px-2 py-1 rounded bg-violet-600 text-white hover:bg-violet-700">
                  Fix anwenden
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-if="store.error" class="text-xs text-red-600 dark:text-red-400">
        {{ store.error }}
      </div>
    </div>
  </div>
</template>
