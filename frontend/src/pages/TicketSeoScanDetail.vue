<!-- src/pages/TicketSeoScanDetail.vue -->
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
            <!-- Detail-Icon -->
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 8v4" />
              <path d="M12 16h.01" />
            </svg>
          </span>
          <span class="text-xs uppercase tracking-wide">SEO-Scan Details</span>
        </div>
        <h1 class="text-2xl font-semibold">
          Ticket #{{ ticketId }} · Scan #{{ scanId }}
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

      <!-- Mitte / Rechts: Domain + Status + Device-Toggle -->
      <div class="flex flex-col items-start md:items-end gap-3 text-sm">
        <a
          v-if="scan?.domain"
          :href="scan.domain"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-black/10 dark:border-white/20 text-xs sm:text-sm bg-white dark:bg-[#141827] hover:bg-black/5 dark:hover:bg-white/10"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18" />
            <path d="M12 3a15.3 15.3 0 0 1 4 9 15.3 15.3 0 0 1-4 9 15.3 15.3 0 0 1-4-9 15.3 15.3 0 0 1 4-9z" />
          </svg>
          <span class="max-w-[14rem] truncate">{{ scan.domain }}</span>
        </a>

        <div class="flex flex-wrap items-center gap-2">
          <span
            v-if="scan?.status"
            class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium"
            :class="scanStatusClass(scan.status)"
          >
            Status: {{ scan.status }}
          </span>
          <span class="text-xs text-gray-500 dark:text-gray-400">
            {{ fmtDateTime(scan?.created_at) }}
            <span v-if="scan?.finished_at"> → {{ fmtDateTime(scan.finished_at) }}</span>
          </span>
        </div>

        <!-- Device-Toggle -->
        <div
          v-if="hasAnyVariant"
          class="inline-flex items-center rounded-full border border-black/10 dark:border-white/20 bg-black/5 dark:bg-white/5 text-[11px] overflow-hidden"
        >
          <button
            type="button"
            class="px-3 py-1 flex items-center gap-1"
            :class="variant === 'mobile'
              ? 'bg-emerald-500 text-white'
              : 'text-gray-600 dark:text-gray-300'"
            @click="variant = 'mobile'"
          >
            <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="7" y="2" width="10" height="16" rx="2" />
              <path d="M11 19h2" />
            </svg>
            <span>Mobile</span>
          </button>
          <button
            type="button"
            class="px-3 py-1 flex items-center gap-1 border-l border-black/10 dark:border-white/10"
            :class="variant === 'desktop'
              ? 'bg-emerald-500 text-white'
              : 'text-gray-600 dark:text-gray-300'"
            @click="variant = 'desktop'"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="13" rx="2" />
              <path d="M8 21h8" />
              <path d="M12 17v4" />
            </svg>
            <span>Desktop</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Fehler / Loading -->
    <div v-if="error" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">
      {{ error }}
    </div>
    <div v-else-if="loading" class="p-4 rounded-xl border bg-white dark:bg-[#0f1424]">
      Scan-Details werden geladen…
    </div>

    <!-- Inhalt -->
    <div v-else-if="scan" class="space-y-6">
      <!-- Summary & Scores -->
      <div class="grid gap-6 lg:grid-cols-[minmax(0,2fr),minmax(0,1.5fr)]">
        <!-- Linke Seite: Meta -->
        <div
          class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm p-4 space-y-3 text-sm"
        >
          <div class="font-medium">Scan-Übersicht</div>
          <div class="grid sm:grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300">
            <div>
              <div class="text-gray-400 text-[11px] uppercase tracking-wide">Strategie</div>
              <div class="font-medium capitalize">
                {{ scan.strategy || 'mobile' }}
              </div>
            </div>
            <div>
              <div class="text-gray-400 text-[11px] uppercase tracking-wide">Max. Seiten</div>
              <div class="font-medium">{{ scan.max_pages ?? '–' }}</div>
            </div>
            <div>
              <div class="text-gray-400 text-[11px] uppercase tracking-wide">Seiten gescannt</div>
              <div class="font-medium">
                {{ scan.pages_scanned ?? pages.length }} / {{ scan.pages_total ?? pages.length }}
              </div>
            </div>
            <div>
              <div class="text-gray-400 text-[11px] uppercase tracking-wide">Ticket-ID</div>
              <div class="font-medium">#{{ scan.ticket_id }}</div>
            </div>
          </div>
        </div>

        <!-- Rechte Seite: Score-Kreis -->
        <div
          class="rounded-xl border border-black/5 dark:border-white/10 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white shadow-sm p-4 sm:p-5 flex flex-col justify-between"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-xs uppercase tracking-wide text-slate-400 mb-1">
                Gesamt-Score ({{ variantLabel }})
              </div>
              <div class="text-sm font-medium mb-1">
                SEO-Scan Bewertung
              </div>
              <div class="text-xs text-slate-400">
                Performance / SEO / (Accessibility &amp; Best Practices folgen)
              </div>
            </div>

            <div
              class="h-20 w-20 rounded-full border border-white/10 flex items-center justify-center relative overflow-hidden"
            >
              <div
                class="absolute inset-1 rounded-full"
                :class="scoreBgClass(scoreBlock.overall)"
              ></div>
              <div class="relative z-10 text-center">
                <div class="text-xs text-slate-300">Score</div>
                <div class="text-xl font-semibold">
                  {{ scoreBlock.overall ?? '–' }}
                </div>
              </div>
            </div>
          </div>

          <div class="mt-4 grid grid-cols-3 gap-2 text-xs">
            <div class="space-y-0.5">
              <div class="text-slate-400">Performance</div>
              <div class="font-semibold">
                {{ scoreBlock.performance ?? '–' }}/100
              </div>
            </div>
            <div class="space-y-0.5">
              <div class="text-slate-400">SEO</div>
              <div class="font-semibold">
                {{ scoreBlock.seo ?? '–' }}/100
              </div>
            </div>
            <div class="space-y-0.5">
              <div class="text-slate-400">Probleme</div>
              <div class="font-semibold">
                <span class="text-red-300">{{ scoreBlock.critical }}</span> /
                <span class="text-amber-300">{{ scoreBlock.warning }}</span> /
                <span class="text-slate-300">{{ scoreBlock.info }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Seiten + Findings -->
      <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
        <!-- Kopf -->
        <div
          class="px-4 py-3 border-b border-black/5 dark:border-white/10 flex flex-col gap-3 md:flex-row md:items-center md:justify-between text-sm"
        >
          <div class="flex items-center gap-2">
            <span
              class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10"
            >
              <!-- Seiten-Icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="4" y="3" width="16" height="18" rx="2" />
                <path d="M8 7h8" />
                <path d="M8 11h4" />
              </svg>
            </span>
            <div>
              <div class="font-medium">Gescannten Seiten</div>
              <div class="text-xs text-gray-500 dark:text-gray-400">
                Ansicht: {{ variantLabel }} ·
                <span v-if="currentPages.length">
                  {{ currentPages.length }} Seite(n)
                </span>
                <span v-else>Keine Seiten für diese Ansicht gespeichert.</span>
              </div>
            </div>
          </div>

          <!-- URL-Auswahl + Page-Metriken -->
          <div class="flex flex-col gap-2 md:items-end text-xs">
            <div class="flex items-center gap-2">
              <span class="text-gray-500 dark:text-gray-400">Seite wählen:</span>
              <select
                v-model.number="selectedPageId"
                class="rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1 text-xs max-w-xs"
                :disabled="!currentPages.length"
              >
                <option v-if="!currentPages.length" :value="null">Keine Seiten vorhanden</option>
                <option
                  v-for="p in currentPages"
                  :key="p.id"
                  :value="p.id"
                >
                  {{ shortUrl(p.url) }}
                </option>
              </select>
            </div>

            <div v-if="currentPage" class="flex flex-wrap gap-3 text-[11px] text-gray-500 dark:text-gray-300">
              <span>
                Performance:
                <span class="font-semibold">{{ currentPage.performance_score ?? '–' }}/100</span>
              </span>
              <span>
                SEO:
                <span class="font-semibold">{{ currentPage.seo_score ?? '–' }}/100</span>
              </span>
              <span>
                FCP / LCP:
                <span class="font-semibold">
                  {{ fmtMs(currentPage.fcp_ms) }} / {{ fmtMs(currentPage.lcp_ms) }}
                </span>
              </span>
              <span>
                CLS / TBT:
                <span class="font-semibold">
                  {{ currentPage.cls ?? '–' }} / {{ fmtMs(currentPage.tbt_ms) }}
                </span>
              </span>
              <span>
                Issues:
                <span class="font-semibold">{{ currentPage.issues_count ?? currentFindings.length }}</span>
              </span>
            </div>
          </div>
        </div>

        <!-- Body -->
        <div class="p-4 space-y-4">
          <div
            v-if="!currentPages.length"
            class="text-xs text-gray-500 dark:text-gray-400"
          >
            Für diesen Scan wurden noch keine Seiten gespeichert ({{ variantLabel }}).
          </div>

          <div v-else-if="!currentFindings.length" class="text-xs text-gray-500 dark:text-gray-400">
            Für diese Seite wurden noch keine detaillierten Findings gespeichert.
          </div>

          <!-- Findings Grid -->
          <div v-else class="space-y-3">
            <div class="flex items-center justify-between text-xs">
              <span class="font-medium text-gray-600 dark:text-gray-200">
                Findings für {{ currentPage?.url }}
              </span>
              <span class="text-gray-500 dark:text-gray-400">
                {{ currentFindings.length }} Eintrag(e) ·
                <span class="text-red-500">kritisch: {{ findingsStats.critical }}</span>,
                <span class="text-amber-500"> Warnung: {{ findingsStats.warning }}</span>,
                <span class="text-slate-400"> Info: {{ findingsStats.info }}</span>
              </span>
            </div>

            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <details
                v-for="f in currentFindings"
                :key="f.id"
                class="group rounded-xl border border-black/5 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] p-3 text-xs"
              >
                <summary class="flex items-start gap-2 cursor-pointer list-none">
                  <span
                    class="inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-medium mt-0.5"
                    :class="findingTypeClass(f.type)"
                  >
                    {{ f.type || 'info' }}
                  </span>
                  <div class="flex-1 space-y-0.5">
                    <div class="font-semibold">
                      {{ f.category || 'Allgemein' }}
                      <span v-if="f.rule" class="text-gray-400">· {{ f.rule }}</span>
                    </div>
                    <div class="text-gray-600 dark:text-gray-200">
                      {{ f.message }}
                    </div>
                    <div class="text-[11px] text-emerald-700 dark:text-emerald-300">
                      Klicken für Details &amp; Lösung
                    </div>
                  </div>
                  <svg
                    class="h-3.5 w-3.5 mt-1 text-gray-400 group-open:rotate-90 transition-transform"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <path d="M9 18l6-6-6-6" />
                  </svg>
                </summary>

                <div class="mt-2 pl-6 space-y-2">
                  <div v-if="f.details" class="text-[11px] text-gray-500 dark:text-gray-300">
                    Hintergrund: {{ f.details }}
                  </div>

                  <div
                    v-if="f.suggestion"
                    class="rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/30 px-2.5 py-2"
                  >
                    <div class="text-[11px] font-semibold text-emerald-800 dark:text-emerald-200 mb-0.5">
                      So behebst du das:
                    </div>
                    <div class="text-[11px] text-emerald-900 dark:text-emerald-100 whitespace-pre-wrap">
                      {{ f.suggestion }}
                    </div>
                  </div>

                  <div
                    v-if="f.raw_json"
                    class="text-[10px] text-gray-400 dark:text-gray-500"
                  >
                    Technische Details aus Google PSI sind gespeichert und können später
                    für ein technisches Debugging verwendet werden.
                  </div>
                </div>
              </details>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Fallback -->
    <div v-else class="p-4 rounded-xl border bg-white dark:bg-[#0f1424] text-sm">
      Kein SEO-Scan gefunden.
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { getTicket } from '../api'

const route = useRoute()
const ticketId = Number(route.params.id)
const scanId = Number(route.params.scanId)

const ticket = ref<any | null>(null)
const scan = ref<any | null>(null)
const pages = ref<any[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

// mobile / desktop
const variant = ref<'mobile' | 'desktop'>('mobile')

onMounted(async () => {
  try {
    // Ticket laden (für Kopfbereich)
    try {
      ticket.value = await getTicket(ticketId)
    } catch {
      // Ticket-Fehler ignorieren
    }

    const res = await api.get(`/seo/scans/${scanId}/findings`)
    if (!res.data?.ok) {
      throw new Error(res.data?.error || 'Scan nicht gefunden')
    }
    scan.value = res.data.scan
    pages.value = Array.isArray(res.data.pages) ? res.data.pages : []
  } catch (e: any) {
    error.value = e?.response?.data?.error || e?.message || 'Scan-Details konnten nicht geladen werden'
  } finally {
    loading.value = false
  }
})

// Hilfsfunktionen und abgeleitete Daten
const hasAnyVariant = computed(() => {
  return pages.value.some(p => normalizeVariant(p) === 'mobile') ||
    pages.value.some(p => normalizeVariant(p) === 'desktop')
})

function normalizeVariant(p: any): 'mobile' | 'desktop' {
  const raw = String(p?.variant || p?.view || p?.strategy || '').toLowerCase()
  if (raw.includes('desktop')) return 'desktop'
  if (raw.includes('mobile')) return 'mobile'
  // Fallback: wenn Scan-Strategie Desktop erwähnt, sonst Mobile
  const s = String(scan.value?.strategy || '').toLowerCase()
  if (s.includes('desktop')) return 'desktop'
  if (s.includes('mobile')) return 'mobile'
  return 'mobile'
}

const pagesByVariant = computed(() => {
  const m: { mobile: any[]; desktop: any[] } = { mobile: [], desktop: [] }
  for (const p of pages.value) {
    m[normalizeVariant(p)].push(p)
  }
  return m
})

const currentPages = computed(() => pagesByVariant.value[variant.value])

const selectedPageId = ref<number | null>(null)

watch(
  currentPages,
  (list) => {
    if (!list.length) {
      selectedPageId.value = null
      return
    }
    if (!selectedPageId.value || !list.some(p => p.id === selectedPageId.value)) {
      selectedPageId.value = list[0].id
    }
  },
  { immediate: true },
)

const currentPage = computed(() =>
  currentPages.value.find(p => p.id === selectedPageId.value) || currentPages.value[0] || null,
)

const currentFindings = computed(() => (currentPage.value?.findings as any[]) || [])

// Score-Berechnung je Variante (aus Seiten aggregieren)
const metricsByVariant = computed(() => {
  const result: Record<'mobile' | 'desktop', any> = {
    mobile: { performance: null, seo: null, overall: null, critical: 0, warning: 0, info: 0 },
    desktop: { performance: null, seo: null, overall: null, critical: 0, warning: 0, info: 0 },
  }

  ;(['mobile', 'desktop'] as const).forEach(v => {
    const list = pagesByVariant.value[v]
    if (!list.length) return

    let perfSum = 0
    let seoSum = 0
    let perfCount = 0
    let seoCount = 0
    let crit = 0
    let warn = 0
    let info = 0

    for (const p of list) {
      if (p.performance_score != null) {
        perfSum += Number(p.performance_score)
        perfCount++
      }
      if (p.seo_score != null) {
        seoSum += Number(p.seo_score)
        seoCount++
      }
      const fList: any[] = Array.isArray(p.findings) ? p.findings : []
      for (const f of fList) {
        const t = String(f.type || '').toLowerCase()
        if (t === 'critical') crit++
        else if (t === 'warning') warn++
        else info++
      }
    }

    const perf = perfCount ? Math.round(perfSum / perfCount) : null
    const seo = seoCount ? Math.round(seoSum / seoCount) : null
    const overall =
      perf != null && seo != null ? Math.round((perf + seo) / 2) : perf ?? seo ?? null

    result[v] = {
      performance: perf,
      seo,
      overall,
      critical: crit,
      warning: warn,
      info,
    }
  })

  return result
})

const scoreBlock = computed(() => metricsByVariant.value[variant.value])

const findingsStats = computed(() => {
  let critical = 0
  let warning = 0
  let info = 0
  for (const f of currentFindings.value) {
    const t = String(f.type || '').toLowerCase()
    if (t === 'critical') critical++
    else if (t === 'warning') warning++
    else info++
  }
  return { critical, warning, info }
})

const variantLabel = computed(() => (variant.value === 'mobile' ? 'Mobile' : 'Desktop'))

// Helfer
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

function fmtMs(v?: number | null) {
  if (v == null) return '–'
  return `${v} ms`
}

function shortUrl(u?: string | null) {
  if (!u) return '-'
  return String(u).replace(/^https?:\/\//i, '').replace(/\/+$/, '')
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

function findingTypeClass(raw?: string | null) {
  const t = (raw || '').toLowerCase()
  if (t === 'critical') {
    return 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-200'
  }
  if (t === 'warning') {
    return 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200'
  }
  return 'bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200'
}
</script>
