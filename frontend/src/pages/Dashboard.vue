<!-- src/pages/Dashboard.vue -->
<template>
  <div class="space-y-6">
    <!-- Header / Controls -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <h1 class="text-2xl font-semibold">Dashboard</h1>

      <div class="flex flex-col sm:flex-row gap-2 sm:items-center">
        <input
          v-model="q"
          type="search"
          placeholder="Suchen… (Ticket, Name, E-Mail, Domain)"
          class="px-3 py-2 rounded-md border border-gray-300 dark:border-white/20 bg-white dark:bg-[#141827] text-sm w-full sm:w-72"
        />
        <input
          v-model="month"
          type="month"
          class="px-3 py-2 rounded-md border border-gray-300 dark:border-white/20 bg-white dark:bg-[#141827] text-sm"
        />
        <button
          class="px-3 py-2 rounded-md bg-gray-900 text-white dark:bg-white dark:text-gray-900 disabled:opacity-60"
          @click="refresh"
          :disabled="loading"
          title="Aktualisieren"
        >
          ↻
        </button>
      </div>
    </div>

    <!-- Status/Fehler -->
    <div v-if="error" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">
      {{ error }}
    </div>

    <!-- KPI Cards -->
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard label="Tickets (Monat)" :value="stats.total" />
      <KpiCard label="Offen" :value="stats.open" />
      <KpiCard label="Geschlossen" :value="stats.closed" />
      <KpiCard label="Weitere Stati" :value="Object.keys(stats.byStatus).length - baseStatusKeys.length" />
    </div>

    <!-- Status Breakdown -->
    <div class="bg-white dark:bg-[#0f1424] rounded-xl shadow-sm border border-black/5 dark:border-white/10">
      <div class="p-4 flex flex-wrap gap-3">
        <span
          v-for="(n, key) in stats.byStatus"
          :key="key"
          class="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm bg-gray-100 dark:bg-white/10"
        >
          <Badge :status="key" />
          <span class="font-medium capitalize">{{ key }}</span>
          <span class="opacity-70">· {{ n }}</span>
        </span>
      </div>
    </div>

    <!-- Tabelle -->
    <div class="bg-white dark:bg-[#0f1424] rounded-xl shadow-sm overflow-hidden border border-black/5 dark:border-white/10">
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-gray-700 dark:bg-gray-800/60 dark:text-gray-200">
            <tr>
              <th class="px-4 py-3 text-left font-medium">Ticket</th>
              <th class="px-4 py-3 text-left font-medium">Datum</th>
              <th class="px-4 py-3 text-left font-medium">Name</th>
              <th class="px-4 py-3 text-left font-medium">E-Mail</th>
              <th class="px-4 py-3 text-left font-medium">Domain</th>
              <th class="px-4 py-3 text-left font-medium">Prio</th>
              <th class="px-4 py-3 text-left font-medium">Status</th>
              <th class="px-4 py-3 text-right font-medium">Aktion</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="8" class="px-4 py-6 text-center text-gray-500">Lädt…</td>
            </tr>

            <tr
              v-for="t in filtered"
              :key="t.ticket_id"
              class="border-t hover:bg-gray-50 dark:border-white/10 dark:hover:bg-white/5"
            >
              <td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">#{{ t.ticket_id }}</td>
              <td class="px-4 py-3">{{ formatDate(t.created_at) }}</td>
              <td class="px-4 py-3">{{ t.name || '—' }}</td>
              <td class="px-4 py-3">
                <a v-if="t.email" class="text-blue-600 hover:underline" :href="`mailto:${t.email}`">{{ t.email }}</a>
                <span v-else>—</span>
              </td>
              <td class="px-4 py-3">
                <a
                  v-if="t.domain"
                  class="text-blue-600 hover:underline"
                  :href="normalizedUrl(t.domain)"
                  target="_blank"
                  rel="noopener"
                >{{ t.domain }}</a>
                <span v-else>—</span>
              </td>
              <td class="px-4 py-3">
                <span class="inline-block px-2 py-0.5 rounded text-xs font-medium" :class="prioClass(t.prio)">
                  {{ t.prio || '—' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <Badge :status="t.status" />
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  class="px-3 py-1.5 rounded-md bg-blue-600 text-white hover:bg-blue-700"
                  @click="openDetail(t)"
                >
                  Details
                </button>
              </td>
            </tr>

            <tr v-if="!loading && filtered.length === 0">
              <td colspan="8" class="px-4 py-6 text-center text-gray-500">Keine Einträge gefunden.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getTickets } from '../api'

type Ticket = {
  ticket_id: number
  name?: string
  email?: string
  domain?: string
  prio?: string | null
  status?: string | null
  created_at?: string | null
}

const router = useRouter()

const loading = ref(false)
const error = ref<string | null>(null)
const rows = ref<Ticket[]>([])

const q = ref('')
const month = ref(todayMonth())

const baseStatusKeys = ['open','offen','neu','pending','closed','done','resolved'] as const

function todayMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`
}
function monthStartEnd(ym: string) {
  const [y, m] = ym.split('-').map(Number)
  const lastDay = new Date(y, m, 0).getDate()
  const mm = String(m).padStart(2, '0')
  return {
    start: `${y}-${mm}-01`,
    end:   `${y}-${mm}-${String(lastDay).padStart(2,'0')}`
  }
}
function sameMonth(d: string | null | undefined, ym: string) {
  if (!d) return false
  const s = /^\d{4}-\d{2}/.test(d) ? d.slice(0,7) : new Date(d).toISOString().slice(0,7)
  return s === ym
}
function normalizedUrl(u?: string) {
  if (!u) return '#'
  return /^https?:\/\//i.test(u) ? u : `https://${u}`
}
function formatDate(d?: string | null) {
  if (!d) return '—'
  try {
    const iso = /^\d{4}-\d{2}-\d{2}/.test(d) ? d : new Date(d).toISOString()
    return iso.slice(0,10)
  } catch { return String(d).slice(0,10) }
}
function prioClass(p?: string | null) {
  const v = (p || '').toLowerCase()
  if (['high','hoch','urgent','prio1','p1'].includes(v))  return 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300'
  if (['medium','mittel','prio2','p2'].includes(v))       return 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300'
  if (['low','niedrig','prio3','p3'].includes(v))         return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300'
  return 'bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-200'
}

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  return rows.value
    .filter(r => sameMonth(r.created_at ?? null, month.value))
    .filter(r => {
      if (!s) return true
      const hay = [
        r.ticket_id, r.name, r.email, r.domain, r.status, r.prio, formatDate(r.created_at)
      ].filter(Boolean).join(' ').toLowerCase()
      return hay.includes(s)
    })
})

const stats = computed(() => {
  const subset = filtered.value
  const byStatus: Record<string, number> = {}
  let open = 0, closed = 0
  for (const t of subset) {
    const key = (t.status || 'unbekannt').toString().toLowerCase()
    byStatus[key] = (byStatus[key] || 0) + 1
    if (['open','bezahlt','neu','await'].includes(key)) open++
    if (['closed','done','resolved','erledigt'].includes(key)) closed++
  }
  return { total: subset.length, open, closed, byStatus }
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const { start, end } = monthStartEnd(month.value)
    const data = await getTickets({ start, end })
    rows.value = (Array.isArray(data) ? data : []).map((r: any) => ({
      ticket_id : Number(r.ticket_id ?? r.id ?? r.entry_id),
      name      : r.name ?? '',
      email     : r.email ?? '',
      domain    : r.domain ?? r.url ?? '',
      prio      : r.prio ?? r.priority ?? null,
      status    : r.status ?? null,
      created_at: r.created_at ?? r.date_created ?? r.createdAt ?? r.date ?? null,
      // Zugänge + Aliasse
      ftp_host  : r.ftp_host  ?? r.ftp_server           ?? r.zugang_ftp_host      ?? '',
      ftp_user  : r.ftp_user  ??                         r.zugang_ftp_user        ?? '',
      ftp_pass  : r.ftp_pass  ??                         r.zugang_ftp_pass        ?? '',

      website_login : r.website_login ?? r.website_user  ?? r.zugang_website_login ?? '',
      website_user  : r.website_user  ?? r.website_login ?? r.zugang_website_user  ?? '',
      website_pass  : r.website_pass  ??                 r.zugang_website_pass    ?? '',

      hosting_url   : r.hosting_url   ?? r.hoster_url    ?? r.zugang_hosting_url   ?? '',
      hosting_user  : r.hosting_user  ??                 r.zugang_hosting_user    ?? '',
      hosting_pass  : r.hosting_pass  ??                 r.zugang_hosting_pass    ?? '',

      cms           : r.cms ?? r.system ?? '',
      beschreibung  : r.beschreibung ?? r.description ?? r.msg ?? '',
      hoster        : r.hoster ?? r.hosting_provider ?? '',
    }))
  } catch (e: any) {
    error.value = e?.response?.data?.msg || e?.message || 'Fehler beim Laden'
  } finally {
    loading.value = false
  }
}

async function refresh() { await load() }

function openDetail(t: Ticket) {
  try {
    const minimal = {
      ticket_id : t.ticket_id,
      name      : t.name || '',
      email     : t.email || '',
      domain    : t.domain || '',
      prio      : t.prio || '',
      status    : t.status || '',
      created_at: t.created_at || ''
    }
    const json = JSON.stringify(t)
    sessionStorage.setItem('sf_last_ticket', json)
    const s = btoa(encodeURIComponent(json))
    router.push({ name: 'ticket', params: { id: t.ticket_id }, query: { s } })
  } catch {
    router.push({ name: 'ticket', params: { id: t.ticket_id } })
  }
}

onMounted(load)
watch(month, load)
</script>

<script lang="ts">
export default {
  components: {
    KpiCard: {
      props: { label: String, value: [String, Number] },
      template: `
        <div class="rounded-xl bg-white dark:bg-[#0f1424] p-4 shadow-sm border border-black/5 dark:border-white/10">
          <div class="text-sm opacity-70 mb-1">{{ label }}</div>
          <div class="text-2xl font-semibold">{{ value }}</div>
        </div>
      `
    },
    Badge: {
      props: { status: { type: String, default: '' } },
      computed: {
        cls (): string {
          const s = (this.status || '').toLowerCase()
          if (['open','offen','neu','pending'].includes(s))
            return 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-300'
          if (['closed','done','resolved','erledigt'].includes(s))
            return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300'
          if (['urgent','error','fail'].includes(s))
            return 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300'
          return 'bg-gray-100 text-gray-800 dark:bg-white/10 dark:text-gray-200'
        }
      },
      template: `
        <span class="inline-block px-2 py-0.5 rounded text-xs font-medium capitalize" :class="cls">
          {{ (status || '—') }}
        </span>
      `
    }
  }
}
</script>
