<!-- src/components/scan/TabReports.vue -->
<template>
  <div class="space-y-3">
    <!-- Kopfzeile -->
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <div class="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-50 dark:bg-blue-900/40">
          📄
        </div>
        <div>
          <div class="font-medium">Reports</div>
          <div class="text-xs opacity-70">
            {{ items.length }} Report{{ items.length === 1 ? '' : 's' }} verfügbar
          </div>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button
          class="px-3 py-1 rounded-lg border text-xs sm:text-sm hover:bg-black/5 dark:hover:bg-white/10"
          :disabled="loading || clearingAll"
          @click="load"
        >
          {{ loading ? 'Lädt…' : 'Aktualisieren' }}
        </button>

        <button
          class="px-3 py-1 rounded-lg border border-red-300 text-xs sm:text-sm text-red-600 dark:text-red-300 hover:bg-red-50/70 dark:hover:bg-red-900/30 disabled:opacity-50"
          :disabled="loading || clearingAll || items.length === 0"
          @click="removeAll"
        >
          {{ clearingAll ? 'Löscht…' : 'Alle löschen' }}
        </button>
      </div>
    </div>

    <!-- Status / Fehler -->
    <div v-if="error" class="p-3 rounded bg-red-50 text-red-700 text-sm">{{ error }}</div>
    <div v-else-if="loading && items.length === 0" class="text-sm opacity-70">Lade Reports…</div>

    <!-- Liste -->
    <div v-else>
      <div v-if="items.length === 0" class="text-sm opacity-70">
        Noch kein Report verfügbar.
      </div>

      <ul v-else class="divide-y divide-black/5 dark:divide-white/10 rounded-xl border border-black/5 dark:border-white/10 bg-black/2 dark:bg-white/5">
        <li
          v-for="r in items"
          :key="r.id"
          class="p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center gap-3"
        >
          <div class="flex-1 flex items-start gap-3">
            <div class="mt-1">
              <div class="w-7 h-7 rounded-full bg-emerald-50 dark:bg-emerald-900/40 flex items-center justify-center text-xs">
                #{{ r.id }}
              </div>
            </div>
            <div>
              <div class="font-medium text-sm sm:text-base">
                {{ r.title || ('Report #' + r.id) }}
              </div>
              <div class="text-[11px] sm:text-xs opacity-70 mt-0.5">
                Scan #{{ r.scan_id }} · {{ fmt(r.created_at) }}
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 sm:gap-3">
            <a
              v-if="r.url_html"
              :href="r.url_html"
              target="_blank"
              class="px-3 py-1 rounded-lg border text-xs sm:text-sm hover:bg-black/5 dark:hover:bg-white/10"
            >
              HTML
            </a>

            <button
              v-if="r.url_pdf"
              class="px-3 py-1 rounded-lg border text-xs sm:text-sm hover:bg-black/5 dark:hover:bg-white/10"
              :disabled="downloadingId === r.id"
              @click="pdf(r.id)"
            >
              {{ downloadingId === r.id ? 'Lädt…' : 'PDF' }}
            </button>

            <button
              class="px-2 py-1 rounded-lg border border-red-200 text-xs sm:text-sm text-red-600 dark:text-red-300 hover:bg-red-50/70 dark:hover:bg-red-900/30 disabled:opacity-50 flex items-center gap-1"
              :disabled="deletingId === r.id"
              @click="removeOne(r.id)"
              title="Diesen Report löschen"
            >
              <span>🗑️</span>
              <span v-if="deletingId === r.id">Löscht…</span>
              <span v-else>Entfernen</span>
            </button>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { ReportRow } from '@/api'
import {
  getReportsByTicket,
  downloadReportPdf,
  deleteReport,              // neu
  deleteReportsByTicket       // neu
} from '@/api'

// Props (optional)
const props = defineProps<{ ticketId?: number }>()

// Fallback auf Route, wenn Prop fehlt
const route = useRoute()
const tid = computed(() => props.ticketId ?? Number(route.params.id))

const loading      = ref(false)
const error        = ref<string | null>(null)
const items        = ref<ReportRow[]>([])
const deletingId   = ref<string | number | null>(null)
const clearingAll  = ref(false)
const downloadingId = ref<string | number | null>(null)

// Datum immer in Europa/Berlin anzeigen
function fmt(s?: string | null) {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleString('de-DE', {
      timeZone: 'Europe/Berlin',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return s
  }
}

async function load() {
  error.value = null
  const id = tid.value
  if (!id || Number.isNaN(id)) {
    error.value = 'Keine Ticket-ID'
    return
  }
  loading.value = true
  try {
    items.value = await getReportsByTicket(id)
  } catch (e: any) {
    error.value = e?.response?.data?.message || e?.message || 'Laden fehlgeschlagen'
  } finally {
    loading.value = false
  }
}

function pdf(id: string | number) {
  downloadingId.value = id
  try {
    downloadReportPdf(String(id))
  } finally {
    // Download läuft im Browser – hier nur kurz den Zustand zurücksetzen
    setTimeout(() => { downloadingId.value = null }, 500)
  }
}

async function removeOne(id: string | number) {
  if (!confirm(`Report #${id} wirklich löschen?`)) return
  deletingId.value = id
  try {
    await deleteReport(String(id))
    items.value = items.value.filter(r => String(r.id) !== String(id))
  } catch (e: any) {
    console.error('deleteReport failed', e?.response?.data || e)
  } finally {
    deletingId.value = null
  }
}

async function removeAll() {
  if (items.value.length === 0) return
  if (!confirm('Alle Reports für dieses Ticket löschen?')) return
  const id = tid.value
  if (!id || Number.isNaN(id)) return

  clearingAll.value = true
  try {
    await deleteReportsByTicket(id)
    items.value = []
  } catch (e: any) {
    console.error('deleteReportsByTicket failed', e?.response?.data || e)
  } finally {
    clearingAll.value = false
  }
}

onMounted(load)
</script>
