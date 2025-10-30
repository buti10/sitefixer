#TabReports.vue
<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <div class="font-medium">Reports</div>
      <button class="px-3 py-1 rounded border text-sm"
              :disabled="loading"
              @click="load">
        {{ loading ? 'Lädt…' : 'Aktualisieren' }}
      </button>
    </div>

    <div v-if="error" class="p-3 rounded bg-red-50 text-red-700 text-sm">{{ error }}</div>

    <div v-else-if="loading" class="text-sm opacity-70">Lade Reports…</div>

    <div v-else>
      <div v-if="items.length === 0" class="text-sm opacity-70">
        Noch kein Report verfügbar.
      </div>

      <ul v-else class="divide-y divide-black/5 dark:divide-white/10 rounded border">
        <li v-for="r in items" :key="r.id" class="p-3 flex items-center gap-3">
          <div class="flex-1">
            <div class="font-medium">{{ r.title || ('Report #' + r.id) }}</div>
            <div class="text-xs opacity-70">
              Scan #{{ r.scan_id }} · {{ fmt(r.created_at) }}
            </div>
          </div>

          <div class="flex items-center gap-2">
            <a v-if="r.url_html" :href="r.url_html" target="_blank"
               class="px-3 py-1 rounded border text-sm hover:bg-black/5">HTML</a>
            <button v-if="r.url_pdf"
                    class="px-3 py-1 rounded border text-sm hover:bg-black/5"
                    @click="pdf(r.id)">
              PDF
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
import { getReportsByTicket, downloadReportPdf } from '@/api'

// Props (optional)
const props = defineProps<{ ticketId?: number }>()

// Fallback auf Route, wenn Prop fehlt
const route = useRoute()
const tid = computed(() => props.ticketId ?? Number(route.params.id))

const loading = ref(false)
const error   = ref<string | null>(null)
const items   = ref<ReportRow[]>([])

function fmt(s?: string|null){
  if(!s) return '—'
  try { return new Date(s).toLocaleString() } catch { return s }
}

async function load(){
  error.value = null
  items.value = []
  const id = tid.value
  if (!id || Number.isNaN(id)) { error.value = 'Keine Ticket-ID'; return }
  loading.value = true
  try {
    items.value = await getReportsByTicket(id)
  } catch (e:any) {
    error.value = e?.response?.data?.message || e?.message || 'Laden fehlgeschlagen'
  } finally {
    loading.value = false
  }
}

function pdf(id: string){ downloadReportPdf(id) }

onMounted(load)
</script>
