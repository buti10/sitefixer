<!-- src/pages/RepairBeta.vue -->
<template>
  <div class="space-y-6">
    <!-- Header -->
    <div
      class="rounded-xl bg-white/80 dark:bg-[#0f1424]/80 border border-black/5 dark:border-white/10 shadow-sm p-4 sm:p-5">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="space-y-1">
          <div class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 2v6l-5 9a4 4 0 0 0 3.5 6h7A4 4 0 0 0 19 17l-5-9V2" />
                <path d="M8 8h8" />
              </svg>
            </span>
            <span class="text-xs uppercase tracking-wide">Repair Beta</span>
          </div>

          <h1 class="text-2xl font-semibold">Ticket #{{ ticket.ticket_id ?? id }} · Repair Wizard</h1>

          <div class="flex flex-wrap items-center gap-2 text-sm">
            <a v-if="ticket.domain" :href="norm(ticket.domain)" target="_blank" rel="noopener"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-black/10 dark:border-white/20 bg-white dark:bg-[#141827] hover:bg-black/5 dark:hover:bg-white/10 text-xs sm:text-sm">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="9" />
                <path d="M3 12h18" />
                <path d="M12 3a15.3 15.3 0 0 1 4 9 15.3 15.3 0 0 1-4 9 15.3 15.3 0 0 1-4-9 15.3 15.3 0 0 1 4-9z" />
              </svg>
              <span class="max-w-[16rem] truncate">{{ ticket.domain }}</span>
            </a>

            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium capitalize"
              :class="statusPillClass(ticket.status)">
              {{ ticket.status || 'Status unbekannt' }}
            </span>

            <span class="text-xs text-gray-500 dark:text-gray-400">
              Verbinden → Projekt wählen → Diagnose → Schnell-Fixes → Plugins/Themes/Core → Report
            </span>
          </div>

          <div v-if="ticketError" class="mt-2 text-xs text-red-600">{{ ticketError }}</div>
        </div>

        <RouterLink :to="`/tickets/${id}`"
          class="inline-flex items-center justify-center gap-1 rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs sm:text-sm text-gray-700 dark:text-gray-100 hover:bg-black/5 dark:hover:bg-white/10">
          <span>←</span><span>Zurück</span>
        </RouterLink>
      </div>

      <!-- Access cards -->
      <div class="mt-4 grid gap-3 lg:grid-cols-3" v-if="!w.ticketLoading">
        <!-- SFTP -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/60 dark:bg-white/5">
          <div class="text-xs opacity-70 mb-1">SFTP</div>
          <div class="text-sm space-y-1">
            <div class="truncate"><b>Host:</b> {{ w.sftpHost || '—' }}</div>
            <div class="truncate"><b>User:</b> {{ w.sftpUser || '—' }}</div>
            <div class="truncate"><b>Port:</b> {{ w.sftpPort || '22' }}</div>

            <div class="pt-1">
              <div class="text-xs opacity-70 mb-0.5">Passwort</div>
              <div class="flex items-center gap-2">
                <span class="select-all">
                  {{ w.sftpPass ? (w.show.sftp ? w.sftpPass : '••••••••') : '—' }}
                </span>

                <button type="button"
                  class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                  :disabled="!w.sftpPass" @click="w.show.sftp = !w.show.sftp">
                  {{ w.show.sftp ? 'Verbergen' : 'Anzeigen' }}
                </button>

                <button type="button"
                  class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                  :disabled="!w.sftpPass" @click="w.copyToClipboard(w.sftpPass, 'sftp')">
                  {{ w.copied === 'sftp' ? 'Kopiert' : 'Kopieren' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- WP Login -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/60 dark:bg-white/5">
          <div class="text-xs opacity-70 mb-1">WP Login</div>
          <div class="text-sm space-y-1">
            <div class="truncate"><b>User:</b> {{ w.wpUser || '—' }}</div>
            <div class="pt-1">
              <div class="text-xs opacity-70 mb-0.5">Passwort</div>
              <div class="flex items-center gap-2">
                <span class="select-all">
                  {{ w.wpPass ? (w.show.wp ? w.wpPass : '••••••••') : '—' }}
                </span>

                <button type="button"
                  class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                  :disabled="!w.wpPass" @click="w.show.wp = !w.show.wp">
                  {{ w.show.wp ? 'Verbergen' : 'Anzeigen' }}
                </button>

                <button type="button"
                  class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                  :disabled="!w.wpPass" @click="w.copyToClipboard(w.wpPass, 'wp')">
                  {{ w.copied === 'wp' ? 'Kopiert' : 'Kopieren' }}
                </button>
              </div>
            </div>

          </div>
        </div>

        <!-- Hosting -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/60 dark:bg-white/5">
          <div class="text-xs opacity-70 mb-1">Hosting</div>
          <div class="text-sm space-y-1">
            <div class="truncate"><b>URL:</b> {{ w.hostingUrl || '—' }}</div>
            <div class="truncate"><b>User:</b> {{ w.hostingUser || '—' }}</div>
            <div class="pt-1">
              <div class="text-xs opacity-70 mb-0.5">Passwort</div>
              <div class="flex items-center gap-2">
                <span class="select-all">
                  {{ w.hostingPass ? (w.show.host ? w.hostingPass : '••••••••') : '—' }}
                </span>

                <button type="button"
                  class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                  :disabled="!w.hostingPass" @click="w.show.host = !w.show.host">
                  {{ w.show.host ? 'Verbergen' : 'Anzeigen' }}
                </button>

                <button type="button"
                  class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                  :disabled="!w.hostingPass" @click="w.copyToClipboard(w.hostingPass, 'host')">
                  {{ w.copied === 'host' ? 'Kopiert' : 'Kopieren' }}
                </button>
              </div>
            </div>
            <!-- analog wie oben mit w.hostingPass / w.show.host -->
          </div>
        </div>
      </div>


      <!-- Quick status strip -->
      <div class="mt-4 grid gap-3 md:grid-cols-3">
        <div class="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/60 dark:bg-white/5">
          <div class="text-xs opacity-70 mb-1">SFTP</div>
          <div class="text-sm">
            <b :class="w.sessionId ? 'text-emerald-600 dark:text-emerald-300' : ''">
              {{ w.sessionId ? 'verbunden' : 'nicht verbunden' }}
            </b>
            <div class="text-[11px] opacity-70 mt-1">Session: {{ w.sessionId ? w.sessionId.slice(0, 10) + '…' : '—' }}
            </div>
          </div>
        </div>
        <div class="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/60 dark:bg-white/5">
          <div class="text-xs opacity-70 mb-1">Root</div>
          <div class="text-sm">
            <b>{{ w.selectedProject || w.rootPathHint || '—' }}</b>
            <div class="text-[11px] opacity-70 mt-1">Root setzen im Tab “SFTP & Projekte” oder im Explorer.</div>
          </div>
        </div>
        <div class="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/60 dark:bg-white/5">
          <div class="text-xs opacity-70 mb-1">Diagnose</div>
          <div class="text-sm">
            <b>{{ w.diagnoseResult ? 'vorhanden' : 'noch nicht gestartet' }}</b>
            <div class="text-[11px] opacity-70 mt-1">Empfehlung: Root setzen → Diagnose starten → Schnell-Fixes.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <!-- Tabs -->
    <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
      <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 flex flex-wrap gap-2">
        <button v-for="t in tabs" :key="t.key"
          class="px-3 py-1.5 rounded-full text-xs font-medium border border-black/10 dark:border-white/20" :class="activeTab === t.key
            ? 'bg-black text-white dark:bg-white dark:text-gray-900'
            : 'bg-transparent hover:bg-black/5 dark:hover:bg-white/10'" @click="activeTab = t.key">
          {{ t.label }}
        </button>
      </div>

      <div class="p-4">
        <TabOverview v-if="activeTab === 'overview'" :w="w" @go="(k) => (activeTab = k)" />

        <TabSftpProjects v-else-if="activeTab === 'sftp'" :w="w" @go="(k) => (activeTab = k)" />

        <TabExplorer v-else-if="activeTab === 'explorer'" :w="w" @go="(k) => (activeTab = k)" />

        <TabDiagnose v-else-if="activeTab === 'diagnose'" :w="w" @go="(k) => (activeTab = k)" />

        <TabQuickFixes v-else-if="activeTab === 'quickfixes'" :w="w" @go="(k) => (activeTab = k)" />

        <TabPlugins v-else-if="activeTab === 'plugins'" />
        <TabThemes v-else-if="activeTab === 'themes'" />
        <TabCore v-else-if="activeTab === 'core'" />
        <TabDatabase v-else-if="activeTab === 'db'" />
        <TabEnv v-else-if="activeTab === 'env'" />
        <TabReport v-else-if="activeTab === 'report'" />
        <TabAudit v-else-if="activeTab === 'audit'" />
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { useRepairWizard, type TabKey } from "../modules/repair-beta/useRepairWizard";
const route = useRoute();

// Tabs
import TabOverview from "../modules/repair-beta/tabs/TabOverview.vue";
import TabSftpProjects from "../modules/repair-beta/tabs/TabSftpProjects.vue";
import TabExplorer from "../modules/repair-beta/tabs/TabExplorer.vue";
import TabDiagnose from "../modules/repair-beta/tabs/TabDiagnose.vue";
import TabQuickFixes from "../modules/repair-beta/tabs/TabQuickFixes.vue";
import TabPlugins from "../modules/repair-beta/tabs/TabPlugins.vue";
import TabThemes from "../modules/repair-beta/tabs/TabThemes.vue";
import TabCore from "../modules/repair-beta/tabs/TabCore.vue";
import TabDatabase from "../modules/repair-beta/tabs/TabDatabase.vue";
import TabEnv from "../modules/repair-beta/tabs/TabEnv.vue";
import TabReport from "../modules/repair-beta/tabs/TabReport.vue";
import TabAudit from "../modules/repair-beta/tabs/TabAudit.vue";

const w = useRepairWizard();
const id = w.id;
// => Damit dein bestehender Header NICHT umgeschrieben werden muss:
const {
  ticket,
  ticketLoading,
  ticketError,

  sftpHost,
  sftpUser,
  sftpPort,
  sftpPass,

  wpUser,
  wpPass,

  hostingUrl,
  hostingUser,
  hostingPass,

  show,
  copied,
  copyToClipboard,
  norm,
  statusPillClass,

  sessionId,
  selectedProject,
  rootPathHint,
  diagnoseResult,
} = w;

const tabs = [
  { key: "overview", label: "Übersicht" },
  { key: "sftp", label: "SFTP & Projekte" },
  { key: "diagnose", label: "Diagnose" },
  { key: "quickfixes", label: "Schnell-Fixes" },
  { key: "plugins", label: "Plugins" },
  { key: "themes", label: "Themes" },
  { key: "core", label: "Core" },
  { key: "db", label: "Datenbank" },
  { key: "env", label: "Umgebung" },
  { key: "report", label: "Abschluss & Report" },
  { key: "audit", label: "Audit" },
  { key: "explorer", label: "Explorer" },
] as const;

const activeTab = ref<TabKey>("overview");
</script>
