<!-- src/pages/TicketSeoScans.vue -->
<template>
  <div class="space-y-6">
    <!-- Header -->
    <div
      class="rounded-xl bg-white/80 dark:bg-[#0f1424]/80 border border-black/5 dark:border-white/10 shadow-sm p-4 sm:p-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between"
    >
      <!-- Links: Ticket + Kunde -->
      <div class="space-y-1">
        <div class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span
            class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10"
          >
            <!-- Chart / SEO Icon -->
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 3v18h18" />
              <path d="m7 14 3-3 4 4 5-7" />
            </svg>
          </span>
          <span class="text-xs uppercase tracking-wide">SEO-Scan</span>
        </div>
        <h1 class="text-2xl font-semibold">
          Ticket #{{ ticketId }}
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ ticket?.name || 'Unbekannter Kunde' }}
          <span v-if="ticket?.email" class="mx-1">·</span>
          <a
            v-if="ticket?.email"
            :href="`mailto:${ticket.email}`"
            class="text-blue-600 hover:underline break-all"
          >
            {{ ticket.email }}
          </a>
        </p>
      </div>

      <!-- Mitte: Domain / CMS -->
      <div class="flex flex-wrap gap-2 items-center">
        <a
          v-if="ticket?.domain"
          :href="norm(ticket.domain)"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-black/10 dark:border-white/20 text-xs sm:text-sm bg-white dark:bg-[#141827] hover:bg-black/5 dark:hover:bg:white/10"
        >
          <!-- Globe-Icon -->
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18" />
            <path d="M12 3a15.3 15.3 0 0 1 4 9 15.3 15.3 0 0 1-4 9 15.3 15.3 0 0 1-4-9 15.3 15.3 0 0 1 4-9z" />
          </svg>
          <span class="max-w-[12rem] truncate">{{ ticket.domain }}</span>
        </a>

        <span
          v-if="ticket?.cms"
          class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border border-black/10 dark:border-white/20 bg-black/5 dark:bg:white/5"
        >
          CMS: {{ ticket.cms }}
        </span>
      </div>

      <!-- Rechts: Zurück -->
      <div class="flex md:flex-col gap-2 md:items-end">
        <RouterLink
          :to="`/tickets/${ticketId}`"
          class="inline-flex items-center justify-center gap-1 rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs sm:text-sm text-gray-700 dark:text-gray-100 hover:bg-black/5 dark:hover:bg:white/10"
        >
          <span>←</span>
          <span>Zurück zum Ticket</span>
        </RouterLink>
      </div>
    </div>

    <!-- Fehler / Loading -->
    <div v-if="error" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">
      {{ error }}
    </div>
    <div v-else-if="loadingTicket" class="p-4 rounded-xl border bg-white dark:bg-[#0f1424]">
      Ticket wird geladen…
    </div>

    <!-- Inhalt -->
    <div v-else class="space-y-6">
      <!-- Top-Grid: Quick-Action + Summary -->
      <div class="grid gap-6 lg:grid-cols-[minmax(0,2fr),minmax(0,1.5fr)]">
        <!-- Quick-Action: SEO-Scan starten -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2 text-sm font-medium">
              <span
                class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-200"
              >
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 3v18h18" />
                  <path d="m7 14 3-3 4 4 5-7" />
                </svg>
              </span>
              <span>SEO-Scan für {{ shortDomain }}</span>
            </div>
            <span class="text-[11px] text-gray-500 dark:text-gray-400">
              Alle Unterseiten (bis Limit)
            </span>
          </div>

          <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
            Starte einen vollständigen SEO- & Performance-Scan mit Google PageSpeed Insights und eigenen Checks.
          </p>

          <div class="flex flex-wrap gap-3 items-center">
            <button
              type="button"
              class="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50 inline-flex items-center gap-1.5"
              :disabled="scanStarting || !ticket?.domain"
              @click="startScan"
            >
              <svg
                v-if="scanStarting"
                class="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path
                  d="M21 12a9 9 0 1 1-9-9"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              <svg
                v-else
                class="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="m5 3 14 9-14 9z" />
              </svg>
              <span>{{ scanStarting ? 'Scan wird gestartet…' : 'Neuen SEO-Scan starten' }}</span>
            </button>

            <div class="text-xs text-gray-500 dark:text-gray-400">
              Max. Seiten pro Scan:
              <span class="font-medium">{{ maxPages }}</span>
            </div>
          </div>

          <div v-if="scanError" class="mt-3 text-xs text-red-500">
            {{ scanError }}
          </div>
        </div>

        <!-- Summary: letzter Scan / Baseline -->
        <div
          class="rounded-xl border border-black/5 dark:border-white/10 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white shadow-sm p-4 sm:p-5 flex flex-col justify-between"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-xs uppercase tracking-wide text-slate-400 mb-1">Zusammenfassung</div>
              <div class="text-sm font-medium">
                <span v-if="lastScan">Letzter SEO-Scan</span>
                <span v-else>Noch kein SEO-Scan vorhanden</span>
              </div>
              <div v-if="lastScan" class="text-xs text-slate-400 mt-1">
                {{ fmtDateTime(lastScan.created_at) }}
                <span v-if="lastScan.status !== 'done'"> · Status: {{ lastScan.status }}</span>
              </div>
            </div>

            <div
              class="h-20 w-20 rounded-full border border-white/10 flex items-center justify-center relative overflow-hidden"
            >
              <div
                class="absolute inset-1 rounded-full"
                :class="scoreBgClass(scanField(lastScan, 'overall_score', 'mobile'))"
              ></div>
              <div class="relative z-10 text-center">
                <div class="text-xs text-slate-300">Score</div>
                <div class="text-xl font-semibold">
                  {{ scanField(lastScan, 'overall_score', 'mobile') ?? '–' }}
                </div>
              </div>
            </div>
          </div>

          <!-- Mobile / Desktop Kurzvergleich -->
          <div v-if="lastScan" class="mt-4 grid grid-cols-2 gap-4 text-xs">
            <div class="space-y-1">
              <div class="flex items-center gap-1 text-slate-400">
                <!-- Phone Icon -->
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="7" y="2" width="10" height="20" rx="2" />
                  <path d="M11 18h2" />
                </svg>
                <span>Mobile</span>
              </div>
              <div class="font-semibold">
                Score: {{ scanField(lastScan, 'overall_score', 'mobile') ?? '–' }}/100
              </div>
              <div>
                Performance: {{ scanField(lastScan, 'performance_score', 'mobile') ?? '–' }}/100
              </div>
              <div>
                SEO: {{ scanField(lastScan, 'seo_score', 'mobile') ?? '–' }}/100
              </div>
            </div>

            <div class="space-y-1">
              <div class="flex items-center gap-1 text-slate-400">
                <!-- Desktop Icon -->
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="4" width="18" height="12" rx="2" />
                  <path d="M8 20h8" />
                  <path d="M12 16v4" />
                </svg>
                <span>Desktop</span>
              </div>
              <div class="font-semibold">
                Score: {{ scanField(lastScan, 'overall_score', 'desktop') ?? '–' }}/100
              </div>
              <div>
                Performance: {{ scanField(lastScan, 'performance_score', 'desktop') ?? '–' }}/100
              </div>
              <div>
                SEO: {{ scanField(lastScan, 'seo_score', 'desktop') ?? '–' }}/100
              </div>
            </div>
          </div>

          <div v-if="baselineScan" class="mt-4 pt-3 border-t border-white/10 text-xs text-slate-300">
            Baseline-Scan:
            <span class="font-medium text-white">
              {{ fmtDateTime(baselineScan.created_at) }}
            </span>
            · Score (Mobile):
            <span class="font-medium text-white">
              {{ scanField(baselineScan, 'overall_score', 'mobile') ?? '–' }}/100
            </span>
          </div>
        </div>
      </div>

      <!-- Scan-Liste -->
      <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
        <div
          class="px-4 py-3 border-b border-black/5 dark:border-white/10 flex items-center justify-between gap-2 text-sm font-medium"
        >
          <div class="flex items-center gap-2">
            <span
              class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg:white/10"
            >
              <!-- List Icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M8 6h13" />
                <path d="M8 12h13" />
                <path d="M8 18h13" />
                <path d="M3 6h.01" />
                <path d="M3 12h.01" />
                <path d="M3 18h.01" />
              </svg>
            </span>
            <span>Alle SEO-Scans</span>
          </div>
          <div class="text-xs text-gray-500 dark:text-gray-400">
            {{ scans.length ? `${scans.length} Scans` : 'Noch keine Scans' }}
          </div>
        </div>

        <div v-if="scansLoading" class="p-4 text-xs text-gray-500 dark:text-gray-400">
          SEO-Scans werden geladen…
        </div>
        <div v-else-if="scansError" class="p-4 text-xs text-red-500">
          {{ scansError }}
        </div>
        <div v-else class="divide-y divide-black/5 dark:divide-white/10">
          <div v-if="!scans.length" class="p-4 text-xs text-gray-500 dark:text-gray-400">
            Es wurden noch keine SEO-Scans für dieses Ticket durchgeführt.
          </div>

          <div
            v-for="scan in scans"
            :key="scan.id"
            class="px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-sm"
          >
            <div class="flex items-center gap-3">
              <!-- Status-Badge -->
              <span
                class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium"
                :class="scanStatusClass(scan.status)"
              >
                {{ scan.status }}
              </span>

              <div>
                <div class="font-medium">
                  {{ fmtDateTime(scan.created_at) }}
                </div>
                <div class="text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
                  <div class="flex items-center gap-1">
                    <!-- Phone -->
                    <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="7" y="2" width="10" height="20" rx="2" />
                      <path d="M11 18h2" />
                    </svg>
                    <span>
                      M: {{ scanField(scan, 'overall_score', 'mobile') ?? '–' }}/100
                      · Perf: {{ scanField(scan, 'performance_score', 'mobile') ?? '–' }}/100
                    </span>
                  </div>
                  <div class="flex items-center gap-1">
                    <!-- Desktop -->
                    <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="4" width="18" height="12" rx="2" />
                      <path d="M8 20h8" />
                      <path d="M12 16v4" />
                    </svg>
                    <span>
                      D: {{ scanField(scan, 'overall_score', 'desktop') ?? '–' }}/100
                      · Perf: {{ scanField(scan, 'performance_score', 'desktop') ?? '–' }}/100
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-2 justify-between sm:justify-end">
              <span
                v-if="scan.is_baseline"
                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-200"
              >
                Baseline
              </span>

              <span
                v-if="lastScan && scan.id === lastScan.id"
                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200"
              >
                Letzter Scan
              </span>

              <RouterLink
                :to="`/tickets/${ticketId}/scans/seo/${scan.id}`"
                class="inline-flex items-center gap-1 rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs hover:bg-black/5 dark:hover:bg-white/10"
              >
                <span>Details</span>
                <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </RouterLink>

              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-md border border-red-200 text-red-600 px-3 py-1.5 text-xs hover:bg-red-50 dark:border-red-500/40 dark:hover:bg-red-500/10"
                @click="deleteScan(scan.id)"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 6h18" />
                  <path d="M8 6V4h8v2" />
                  <rect x="5" y="6" width="14" height="14" rx="2" />
                  <path d="M10 11v6" />
                  <path d="M14 11v6" />
                </svg>
                <span>Löschen</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { getTicket } from '../api'

const route = useRoute()
const router = useRouter()
const ticketId = Number(route.params.id)

// Ticket-Daten: zuerst aus history.state, dann API
const ticket = ref<any | null>((history.state as any)?.ticket || null)
const loadingTicket = ref(!ticket.value)
const error = ref<string | null>(null)

// SEO-Scan-States
const scans = ref<any[]>([])
const scansLoading = ref(false)
const scansError = ref<string | null>(null)

const scanStarting = ref(false)
const scanError = ref<string | null>(null)

// Limit-Einstellung
const maxPages = ref(100)

// abgeleitete Werte
const lastScan = computed(() => (scans.value.length ? scans.value[0] : null))
const baselineScan = computed(() => scans.value.find(s => s.is_baseline))
const shortDomain = computed(() => {
  const d = ticket.value?.domain || ''
  if (!d) return 'Domain'
  return String(d).replace(/^https?:\/\//i, '').replace(/\/+$/, '')
})

// Ticket laden
onMounted(async () => {
  if (!ticket.value) {
    try {
      const t = await getTicket(ticketId)
      ticket.value = t
      sessionStorage.setItem('sf_last_ticket', JSON.stringify(t))
    } catch (e: any) {
      error.value = e?.response?.data?.msg || e?.message || 'Konnte Ticket nicht laden'
    } finally {
      loadingTicket.value = false
    }
  } else {
    loadingTicket.value = false
  }

  await loadScans()
})

async function loadScans() {
  scansLoading.value = true
  scansError.value = null
  try {
    const res = await api.get('/seo/scans', {
      params: { ticket_id: ticketId },
    })
    if (res.data?.ok && Array.isArray(res.data.scans)) {
      scans.value = res.data.scans
    } else {
      scans.value = []
    }
  } catch (e: any) {
    scansError.value = e?.response?.data?.error || e?.message || 'SEO-Scans konnten nicht geladen werden'
  } finally {
    scansLoading.value = false
  }
}

async function startScan() {
  if (!ticket.value?.domain) {
    scanError.value = 'Keine Domain im Ticket vorhanden.'
    return
  }
  scanStarting.value = true
  scanError.value = null
  try {
    const res = await api.post('/seo/scans', {
      ticket_id: ticketId,
      domain: ticket.value.domain,
      max_pages: maxPages.value,
      strategy: 'mobile', // Basis, Worker macht intern Mobile + Desktop
    })
    if (!res.data?.ok) {
      throw new Error(res.data?.error || 'Scan konnte nicht gestartet werden')
    }
    await loadScans()
  } catch (e: any) {
    scanError.value = e?.response?.data?.error || e?.message || 'SEO-Scan konnte nicht gestartet werden'
  } finally {
    scanStarting.value = false
  }
}

// Scan löschen
async function deleteScan(id: number) {
  if (!confirm('SEO-Scan wirklich löschen?')) return
  try {
    await api.delete(`/seo/scans/${id}`, { params: { ticket_id: ticketId } })
    scans.value = scans.value.filter(s => s.id !== id)
  } catch (e: any) {
    alert(e?.response?.data?.error || e?.message || 'Scan konnte nicht gelöscht werden')
  }
}

// Helper für Mobile/Desktop-Felder mit Fallback
function scanField(scan: any | null | undefined, base: string, view: 'mobile' | 'desktop') {
  if (!scan) return null
  const s: any = scan
  const suffix = view === 'mobile' ? '_mobile' : '_desktop'
  return s[base + suffix] ?? s[base] ?? null
}

// Helfer
function norm(u?: string) {
  return !u ? '#' : /^https?:\/\//i.test(u) ? u : `https://${u}`
}

function fmtDateTime(d?: string | null) {
  if (!d) return '—'
  try {
    const dt = new Date(d)
    const iso = isNaN(dt.getTime()) ? new Date(String(d)).toISOString() : dt.toISOString()
    return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`
  } catch {
    return String(d)
  }
}

function scanStatusClass(raw?: string | null) {
  const s = (raw || '').toLowerCase()
  if (s === 'pending') {
    return 'bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200'
  }
  if (s === 'running') {
    return 'bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-200'
  }
  if (s === 'done') {
    return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200'
  }
  if (s === 'failed') {
    return 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-200'
  }
  return 'bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-100'
}

function scoreBgClass(score?: number | null) {
  if (score == null) return 'bg-slate-800'
  if (score >= 90) return 'bg-emerald-600/80'
  if (score >= 70) return 'bg-emerald-500/70'
  if (score >= 50) return 'bg-amber-500/80'
  return 'bg-red-500/80'
}
</script>
