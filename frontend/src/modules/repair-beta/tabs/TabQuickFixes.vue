<!-- #repair-beta/tabs/TabQuickFixes.vue -->
<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <div class="text-sm font-semibold">Schnell-Fixes</div>
        <div class="text-xs opacity-70">Sichere Standard-Reparaturen (Root erforderlich).</div>
      </div>

      <div class="flex items-center gap-3">
        <label class="flex items-center gap-2 text-xs">
          <input type="checkbox" class="accent-black" v-model="dryRun" />
          Dry-Run
        </label>

        <div class="text-xs opacity-70">
          Root: <span class="font-mono">{{ w.activeRootPath || "—" }}</span>
        </div>

        <button class="px-3 py-2 rounded-lg border text-sm" :disabled="!w.sessionId || !w.activeRootPath"
          @click="() => { w.showAudit = true; w.loadActionHistory(); }">
          Audit / Verlauf
        </button>
      </div>
    </div>

    <div v-if="!w.sessionId" class="p-3 rounded-xl bg-amber-50 text-amber-800 text-sm">
      Bitte zuerst SFTP verbinden.
    </div>

    <div v-else-if="!w.activeRootPath" class="p-3 rounded-xl bg-amber-50 text-amber-800 text-sm">
      Bitte zuerst ein Projekt/Root setzen.
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-3">
      <!-- Fix Cards -->
      <div class="lg:col-span-2 grid gap-3 sm:grid-cols-2">
        <FixCard title=".htaccess reparieren" desc="WP Standard-Regeln wiederherstellen (Single/Multi)."
          :busy="w.fixBusy === 'htaccess'" :disabled="!!w.fixBusy" @run="() => w.fixHtaccess({ dry_run: !!dryRun })" />
        <FixCard title="Drop-ins prüfen" desc="Cache/DB Drop-ins erkennen, Auffälligkeiten melden."
          :busy="w.fixBusy === 'dropins'" :disabled="!!w.fixBusy" @run="() => w.fixDropins({ dry_run: !!dryRun })" />
        <FixCard title="Permissions normalisieren" desc="Verzeichnisse/Dateien prüfen (Dry-Run oder anwenden)."
          :busy="w.fixBusy === 'perms'" :disabled="!!w.fixBusy" @run="() => w.fixPerms({ dry_run: !!dryRun })" />
        <FixCard title=".maintenance entfernen" desc="Hängt WordPress im Wartungsmodus? Entfernt die Datei."
          :busy="w.fixBusy === 'maint'" :disabled="!!w.fixBusy" @run="() => w.fixMaintenance({ dry_run: !!dryRun })" />
      </div>

      <!-- Result Panel -->
      <div class="rounded-2xl border bg-white p-3 space-y-2">
        <div class="flex items-center justify-between">
          <div class="text-xs font-semibold opacity-80">Ergebnis</div>
          <button v-if="w.lastActionId" class="text-xs underline" @click="w.rollbackLast?.()">
            Rückgängig
          </button>
        </div>

        <div v-if="w.fixError" class="p-2 rounded-lg bg-red-50 text-red-700 text-xs">
          {{ w.fixError }}
        </div>

        <pre v-else-if="w.fixResult"
          class="text-[11px] whitespace-pre-wrap bg-black/5 rounded-xl p-2 max-h-[20rem] overflow-auto">{{ JSON.stringify(w.fixResult, null, 2) }}</pre>

        <div v-else class="text-xs opacity-70">
          Starte einen Fix, um ein Ergebnis zu sehen.
        </div>
      </div>

      <!-- Audit / Verlauf FULL WIDTH -->
      <div class="lg:col-span-3 rounded-2xl border bg-white p-3 space-y-2">
        <div class="flex items-center justify-between">
          <div class="text-xs font-semibold opacity-80">Audit / Verlauf</div>

          <div class="flex items-center gap-2">
            <button class="text-xs underline" @click="w.loadDbRuns?.()">
              Aktualisieren
            </button>
            <button v-if="w.showAudit" class="text-xs underline" @click="w.showAudit = false">
              Schließen
            </button>
            <button v-else class="text-xs underline" @click="w.showAudit = true">
              Anzeigen
            </button>
          </div>
        </div>

        <div v-if="!w.showAudit" class="text-xs opacity-70">
          Klicke auf „Anzeigen“, um den Verlauf zu öffnen.
        </div>

        <template v-else>
          <div v-if="w.dbBusy" class="text-xs opacity-70">Lädt…</div>

          <div v-else-if="!w.dbRuns?.length" class="text-xs opacity-70">
            Noch keine Aktionen.
          </div>

          <div v-else class="space-y-2">
            <div v-for="r in w.dbRuns" :key="r.id" class="rounded-xl border p-2">
              <div class="flex items-center justify-between">
                <div class="text-xs font-semibold">
                  Run #{{ r.id }} · {{ r.summary?.action_id || r.kind }}
                </div>
                <div class="text-[11px] opacity-70">
                  {{ r.status }} · {{ r.started_at }}
                </div>
              </div>

              <div class="text-[11px] opacity-70 mt-1">
                {{ r.summary?.message || r.summary?.note || "" }}
              </div>

              <div class="mt-2 flex items-center gap-3">
                <button class="text-xs underline" @click="w.loadDbRunDetail?.(r.id)">
                  Details
                </button>

                <button v-if="r.summary?.rollback_available && r.summary?.action_id" class="text-xs underline"
                  @click="w.rollbackAction?.(r.summary.action_id)">
                  Rückgängig
                </button>
              </div>
            </div>
          </div>

          <div v-if="w.dbRunDetail" class="mt-3 rounded-xl border p-2 bg-black/2">
            <div class="text-xs font-semibold mb-2">Run-Details</div>
            <pre class="text-[11px] whitespace-pre-wrap bg-black/5 rounded-lg p-2 overflow-auto max-h-[18rem]">{{
              JSON.stringify(w.dbRunDetail, null, 2)
            }}</pre>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import FixCard from "../components/FixCard.vue";

defineProps<{ w: any }>();
const dryRun = ref(true);
</script>
