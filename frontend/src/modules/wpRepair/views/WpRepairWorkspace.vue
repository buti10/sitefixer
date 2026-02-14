<!-- src/modules/wpRepair/views/WpRepairWorkspace.vue -->
<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useRoute } from "vue-router";
import { useWpRepairStore } from "../stores/wpRepair.store";

// Ticket live nachladen (dein axios API)
// Hinweis: In deinem Projekt scheint getTicket() tatsächlich ein Ticket-Objekt mit ftp_* zurückzugeben.
import { getTicket } from "@/api";

import StepsSidebar from "../components/StepsSidebar.vue";
import ConnectionStep from "../components/ConnectionStep.vue";
import DiagnoseStep from "../components/DiagnoseStep.vue";
import FixesStep from "../components/FixesStep.vue";

const route = useRoute();
const store = useWpRepairStore();

const ticketId = Number(route.params.id);
const ticket = ref<any>(null);

// Passwort-Visibility
const show = ref({ ftp: false, web: false, host: false });

const ftpHost = computed(() => ticket.value?.ftp_host || ticket.value?.ftp_server || ticket.value?.zugang_ftp_host || "");
const ftpUser = computed(() => ticket.value?.ftp_user || ticket.value?.zugang_ftp_user || "");
const ftpPass = computed(() => ticket.value?.ftp_pass || ticket.value?.zugang_ftp_pass || "");
const ftpPort = computed(() => Number(ticket.value?.ftp_port || ticket.value?.zugang_ftp_port || 22));

const webLogin = computed(() => ticket.value?.website_login || ticket.value?.website_user || ticket.value?.zugang_website_login || ticket.value?.website_user || "");
const webPass = computed(() => ticket.value?.website_pass || ticket.value?.zugang_website_pass || ticket.value?.website_pass || "");
const hostUser = computed(() => ticket.value?.hosting_user || ticket.value?.zugang_hosting_user || "");
const hostPass = computed(() => ticket.value?.hosting_pass || ticket.value?.zugang_hosting_pass || "");
const hostUrl  = computed(() => ticket.value?.hosting_url || ticket.value?.hoster_url || ticket.value?.zugang_hosting_url || "");

const isTicketLoaded = computed(() => !!ticket.value && Number(ticket.value?.ticket_id || ticket.value?.id) === ticketId);

function readTicketFromNav() {
  const st = (history.state as any)?.ticket;
  if (st && (Number(st.ticket_id || st.id) === ticketId)) return st;

  try {
    const s = sessionStorage.getItem("sf_last_ticket");
    const parsed = s ? JSON.parse(s) : null;
    if (parsed && (Number(parsed.ticket_id || parsed.id) === ticketId)) return parsed;
  } catch {}

  return null;
}

function saveTicketToSessionStorage(obj: any) {
  try {
    sessionStorage.setItem("sf_last_ticket", JSON.stringify(obj));
  } catch {}
}

/**
 * WICHTIG:
 * - store.ensureSession() darf NICHT automatisch laufen, weil es sonst nur ticketId sendet
 *   und dein Backend ftp_host/ftp_user/ftp_pass erwartet.
 * - Session wird im ConnectionStep gestartet, sobald User "Verbindung testen" klickt:
 *   -> startSession(ticket)
 *
 * Deshalb: hier nur store.resetForTicket() und Ticket laden.
 */
onMounted(async () => {
  store.resetForTicket(ticketId);

  ticket.value = readTicketFromNav();

  // Falls ticket fehlt oder falsches ticket → nachladen
  if (!ticket.value || Number(ticket.value.ticket_id || ticket.value.id) !== ticketId) {
    try {
      const r = await getTicket(ticketId);
      if (r) {
        ticket.value = r;
        saveTicketToSessionStorage(r);
      }
    } catch {
      // ignore
    }
  }

  // Ticket dem Store geben, damit ConnectionStep die ftp_* Daten hat
  if (ticket.value) {
    store.setTicket(ticket.value);
  }
});

function toggle(which: "ftp" | "web" | "host") {
  show.value = { ...show.value, [which]: !show.value[which] } as any;
}

function fmt(val: any) {
  if (val === undefined || val === null) return "—";
  const s = String(val).trim();
  return s ? s : "—";
}

function normUrl(url: string) {
  const u = (url || "").trim();
  if (!u) return "";
  if (/^https?:\/\//i.test(u)) return u;
  return "https://" + u;
}
</script>

<template>
  <div class="p-6 space-y-4">
    <!-- Header / Kundendaten -->
    <div
      class="rounded-xl bg-white/80 dark:bg-[#0f1424]/80 border border-black/5 dark:border-white/10 shadow-sm p-4"
    >
      <div class="flex items-start justify-between gap-4">
        <div class="space-y-1">
          <h1 class="text-xl font-semibold">WP-Repair</h1>
          <p class="text-sm opacity-70">Ticket ID: {{ ticketId }}</p>

          <p v-if="ticket?.name" class="text-sm">
            {{ ticket.name }}
            <span v-if="ticket?.email" class="opacity-70">· {{ ticket.email }}</span>
          </p>

          <p v-if="ticket?.domain" class="text-sm">
            <a
              class="text-blue-600 hover:underline"
              :href="normUrl(ticket.domain)"
              target="_blank"
              rel="noreferrer"
            >
              {{ ticket.domain }}
            </a>
          </p>
        </div>

        <div class="text-xs opacity-70 text-right">
          <div v-if="ticket?.hoster">Hoster: {{ ticket.hoster }}</div>
          <div v-else-if="ticket?.hosting_provider">Hoster: {{ ticket.hosting_provider }}</div>
          <div v-if="ticket?.cms">CMS: {{ ticket.cms }}</div>
          <div v-if="ticket?.status">Status: {{ ticket.status }}</div>
        </div>
      </div>

      <!-- Zusätzliche Kundendaten (alles was geliefert wird, kompakt) -->
      <div v-if="isTicketLoaded" class="mt-3 grid gap-2 md:grid-cols-3">
        <div class="text-xs opacity-70">
          <div class="font-medium text-[12px] opacity-90 mb-1">Ticket Infos</div>
          <div>PSA: <span class="opacity-90">{{ fmt(ticket?.psa_name || ticket?.handler) }}</span></div>
          <div>Angebot: <span class="opacity-90">{{ fmt(ticket?.angebot) }}</span></div>
          <div>Beschreibung: <span class="opacity-90">{{ fmt(ticket?.beschreibung) }}</span></div>
        </div>

        <div class="text-xs opacity-70">
          <div class="font-medium text-[12px] opacity-90 mb-1">Links</div>
          <div v-if="ticket?.payment_link">
            Payment:
            <a class="text-blue-600 hover:underline" :href="normUrl(ticket.payment_link)" target="_blank" rel="noreferrer">
              öffnen
            </a>
          </div>
          <div v-else-if="ticket?.stripe">
            Payment:
            <a class="text-blue-600 hover:underline" :href="normUrl(ticket.stripe)" target="_blank" rel="noreferrer">
              öffnen
            </a>
          </div>
        </div>

        <div class="text-xs opacity-70">
          <div class="font-medium text-[12px] opacity-90 mb-1">Technik</div>
          <div>FTP Port: <span class="opacity-90">{{ ftpPort }}</span></div>
        </div>
      </div>

      <!-- Access Cards -->
      <div class="mt-4 grid gap-3 md:grid-cols-3">
        <!-- FTP -->
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
          <div class="text-sm font-medium mb-2">FTP</div>

          <div class="text-xs opacity-70">Host</div>
          <div class="text-sm break-all">{{ fmt(ftpHost) }}</div>

          <div class="text-xs opacity-70 mt-2">User</div>
          <div class="text-sm break-all">{{ fmt(ftpUser) }}</div>

          <div class="text-xs opacity-70 mt-2">Passwort</div>
          <div class="flex items-center gap-2">
            <span class="text-sm select-all">
              {{ ftpPass ? (show.ftp ? ftpPass : "••••••••") : "—" }}
            </span>
            <button
              class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20"
              :disabled="!ftpPass"
              @click="toggle('ftp')"
            >
              {{ show.ftp ? "Verbergen" : "Anzeigen" }}
            </button>
          </div>
        </div>

        <!-- Website -->
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
          <div class="text-sm font-medium mb-2">Website</div>

          <div class="text-xs opacity-70">Login</div>
          <div class="text-sm break-all">{{ fmt(webLogin) }}</div>

          <div class="text-xs opacity-70 mt-2">Passwort</div>
          <div class="flex items-center gap-2">
            <span class="text-sm select-all">
              {{ webPass ? (show.web ? webPass : "••••••••") : "—" }}
            </span>
            <button
              class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20"
              :disabled="!webPass"
              @click="toggle('web')"
            >
              {{ show.web ? "Verbergen" : "Anzeigen" }}
            </button>
          </div>
        </div>

        <!-- Hosting -->
        <div class="rounded-lg border border-black/5 dark:border-white/10 bg-white dark:bg-[#0b1020] p-3">
          <div class="text-sm font-medium mb-2">Hosting</div>

          <div class="text-xs opacity-70">URL</div>
          <div class="text-sm break-all">{{ fmt(hostUrl) }}</div>

          <div class="text-xs opacity-70 mt-2">User</div>
          <div class="text-sm break-all">{{ fmt(hostUser) }}</div>

          <div class="text-xs opacity-70 mt-2">Passwort</div>
          <div class="flex items-center gap-2">
            <span class="text-sm select-all">
              {{ hostPass ? (show.host ? hostPass : "••••••••") : "—" }}
            </span>
            <button
              class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20"
              :disabled="!hostPass"
              @click="toggle('host')"
            >
              {{ show.host ? "Verbergen" : "Anzeigen" }}
            </button>
          </div>
        </div>
      </div>

      <!-- Hinweis wenn Ticket geladen, aber FTP Daten fehlen -->
      <div
        v-if="isTicketLoaded && (!ftpHost || !ftpUser || !ftpPass)"
        class="mt-3 text-xs text-red-600 dark:text-red-400"
      >
        Achtung: FTP-Daten unvollständig. WP-Repair Session kann nicht starten (ftp_host/ftp_user/ftp_pass fehlen).
      </div>
    </div>

    <!-- Wizard layout -->
    <div class="grid grid-cols-12 gap-6">
      <div class="col-span-12 lg:col-span-3">
        <StepsSidebar :active="store.activeStep" :canDiagnose="store.canDiagnose" @select="store.goStep" />
      </div>

      <div class="col-span-12 lg:col-span-9 space-y-4">
        <!-- WICHTIG: ConnectionStep muss startSession(store.ticket) nutzen -->
        <ConnectionStep v-if="store.activeStep === 'connect'" />
        <DiagnoseStep v-else-if="store.activeStep === 'diagnose'" />
        <FixesStep v-else-if="store.activeStep === 'quickfix'" />

        <div
          v-else
          class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm p-4 text-sm opacity-70"
        >
          Step noch nicht implementiert.
        </div>
      </div>
    </div>
  </div>
</template>
