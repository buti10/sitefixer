<!-- src/pages/modules/comms-woot/WootOverview.vue -->
<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import api from '@/api'

type WootConf = {
  account_id?: string | number
  base?: string
  ok?: boolean
  has_pat?: boolean
  has_platform?: boolean
}

type WootAccount = {
  id?: number
  name?: string
  locale?: string
  timezone?: string
  auto_resolve_duration?: number
  [key: string]: any
}

type WootStats = {
  conversations_count: number
  incoming_messages_count: number
  outgoing_messages_count: number
  resolutions_count: number
  [key: string]: any
}

type OriginRow = {
  page: string
  count: number
}

type RangeKey = 'today' | '7d' | '30d'

type RecentLog = {
  conversation_id: number
  email: string | null
  page: string | null
  initiated_at: string | null
  browser: string | null
  browser_language: string | null
  platform: string | null
  channel: string | null
  psa_name: string | null
  agent_name: string | null
}

const loading = ref(true)
const error = ref<string | null>(null)

const conf = ref<WootConf | null>(null)
const account = ref<WootAccount | null>(null)
const stats = ref<WootStats | null>(null)

const range = ref<RangeKey>('7d')
const since = ref<number>(0)
const until = ref<number>(0)
// oben im <script setup>
const cleanupDays = ref(30)

const ssoLoading = ref(false)

const origins = ref<OriginRow[]>([])
const recent = ref<RecentLog[]>([])

const cleanupLoading = ref(false)
const cleanupInfo = ref<string | null>(null)

// Filter / Suche für "Letzte Chats"
const filterChannel = ref<'all' | 'web' | 'other'>('all')
const search = ref('')

// Formatter für Europa/Berlin
const berlinFormatter = new Intl.DateTimeFormat('de-DE', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'Europe/Berlin',
})

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return berlinFormatter.format(date)
}

const totalOriginChats = computed(() =>
  origins.value.reduce((sum, o) => sum + (o.count || 0), 0)
)

const filteredRecent = computed(() => {
  let items = recent.value.slice()

  if (filterChannel.value === 'web') {
    items = items.filter((r) =>
      (r.channel || '').toLowerCase().includes('webwidget')
    )
  } else if (filterChannel.value === 'other') {
    items = items.filter(
      (r) => !(r.channel || '').toLowerCase().includes('webwidget')
    )
  }

  const term = search.value.trim().toLowerCase()
  if (term) {
    items = items.filter(
      (r) =>
        (r.email || '').toLowerCase().includes(term) ||
        (r.page || '').toLowerCase().includes(term)
    )
  }

  return items
})

function calcRange(r: RangeKey) {
  const now = Math.floor(Date.now() / 1000)
  let from = now

  if (r === 'today') {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    from = Math.floor(d.getTime() / 1000)
  } else if (r === '7d') {
    from = now - 7 * 86400
  } else if (r === '30d') {
    from = now - 30 * 86400
  }

  since.value = from
  until.value = now
}

async function loadOrigins() {
  try {
    const { data } = await api.get('/comms/woot/reports/origins', {
      params: {
        since: since.value || undefined,
        until: until.value || undefined,
      },
    })

    const items = Array.isArray(data?.items) ? data.items : []
    origins.value = items.map((it: any) => ({
      page: it.page || it.referer || 'unbekannt',
      count: Number(it.count || 0),
    }))
  } catch (e) {
    console.error('loadOrigins failed', e)
  }
}

async function loadRecent() {
  try {
    const { data } = await api.get('/comms/woot/logs/recent', {
      params: { limit: 25 },
    })
    const items = Array.isArray(data?.items) ? data.items : []

    recent.value = items.map((it: any) => ({
      conversation_id: Number(it.cw_conversation_id || it.id || 0),
      email: it.email ?? null,
      page: it.page || it.referer || null,
      initiated_at: it.initiated_at ?? null,
      browser: it.browser_name || null,
      browser_language: it.browser_language || null,
      platform: it.platform_name || null,
      channel: it.channel || null,
      psa_name: it.psa_name || null,
      agent_name: it.assigned_name || null,
    }))
  } catch (e) {
    console.error('loadRecent failed', e)
  }
}

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const [confRes, accountRes, statsRes] = await Promise.all([
      api.get('/comms/woot/_conf'),
      api.get('/comms/woot/account', { params: { id: 1 } }),
      api.get('/comms/woot/reports/inbox', {
        params: {
          since: since.value,
          until: until.value,
          business_hours: false,
        },
      }),
    ])

    conf.value = confRes.data
    account.value = accountRes.data

    const raw = statsRes.data || {}
    const src: any =
      raw.current && typeof raw.current === 'object' ? raw.current : raw

    stats.value = {
      conversations_count: Number(src.conversations_count || 0),
      incoming_messages_count: Number(src.incoming_messages_count || 0),
      outgoing_messages_count: Number(src.outgoing_messages_count || 0),
      resolutions_count: Number(
        src.resolutions_count ?? src.resolution_count ?? 0
      ),
    }
  } catch (e: any) {
    error.value =
      e?.response?.data?.error ||
      e?.message ||
      'Fehler beim Laden der Chatwoot-Daten.'
  } finally {
    loading.value = false
  }
}

async function openWootSso() {
  ssoLoading.value = true
  error.value = null
  try {
    const { data } = await api.get('/comms/woot/sso-link')
    const url = data?.url || data?.link || data
    if (url && typeof url === 'string') {
      window.open(url, '_blank', 'noopener')
    } else {
      error.value = 'Kein gültiger SSO-Link vom Server erhalten.'
    }
  } catch (e: any) {
    const backendError = e?.response?.data?.error
    const status = e?.response?.data?.status || e?.response?.status

    if (status === 400 && backendError === 'woot_user_id missing on user') {
      error.value =
        'Diesem Benutzer ist noch keine Chatwoot-ID zugeordnet. Bitte in den Benutzer-Einstellungen eine Chatwoot-ID eintragen.'
    } else {
      error.value =
        backendError ||
        e?.message ||
        'SSO-Link konnte nicht geladen werden.'
    }
  } finally {
    ssoLoading.value = false
  }
}

async function cleanupOld() {
  if (
    !window.confirm(
      `Alle Chat-Logs, die älter als ${cleanupDays.value} Tage sind, wirklich löschen?`
    )
  ) {
    return
  }

  cleanupLoading.value = true
  cleanupInfo.value = null

  try {
    let response: any

    try {
      response = await api.delete('/comms/woot/logs/cleanup', {
        params: { days: cleanupDays.value },
      })
    } catch (e: any) {
      if (e?.response?.status === 405) {
        response = await api.post('/comms/woot/logs/cleanup', {
          days: cleanupDays.value,
        })
      } else {
        throw e
      }
    }

    const data = response?.data || {}
    if (data.ok) {
      cleanupInfo.value = `${data.deleted || 0} Einträge gelöscht.`
      await Promise.all([loadOrigins(), loadRecent()])
    } else {
      cleanupInfo.value = data.error || 'Bereinigung fehlgeschlagen.'
    }
  } catch (e: any) {
    cleanupInfo.value =
      e?.response?.data?.error || e?.message || 'Bereinigung fehlgeschlagen.'
  } finally {
    cleanupLoading.value = false
  }
}


onMounted(() => {
  calcRange(range.value)
  loadData()
  loadOrigins()
  loadRecent()
})

watch(range, (val) => {
  calcRange(val)
  loadData()
  loadOrigins()
})
</script>

<template>
  <div class="p-4 md:p-6 space-y-6">
    <!-- Kopf -->
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <div
          class="h-9 w-9 rounded-2xl bg-sky-100 text-sky-700 flex items-center justify-center text-lg dark:bg-sky-500/10 dark:text-sky-300"
        >
          💬
        </div>
        <div>
          <h1 class="text-xl md:text-2xl font-semibold">Chatwoot Übersicht</h1>
          <p class="text-sm text-gray-500">
            Status der Chatwoot-Anbindung, SSO-Login und Chat-Performance.
          </p>
          <p class="text-xs text-gray-400 mt-1">
            Alle Zeiten werden in
            <span class="font-medium">Europa/Berlin</span>
            angezeigt.
          </p>
        </div>
      </div>

      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-60 disabled:cursor-not-allowed dark:border-white/10 dark:hover:bg-white/5"
        @click="openWootSso"
        :disabled="ssoLoading || !conf?.ok"
      >
        <span
          v-if="ssoLoading"
          class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"
        />
        <span>Chatwoot öffnen</span>
      </button>
    </div>

    <!-- Fehler / Loading -->
    <div
      v-if="error"
      class="text-sm text-red-600 border border-red-200 bg-red-50 px-3 py-2 rounded-md dark:border-red-500/40 dark:bg-red-500/10"
    >
      {{ error }}
    </div>

    <div v-if="loading && !error" class="text-sm text-gray-500">
      Lädt Chatwoot-Daten …
    </div>

    <!-- Verbindung + Stats -->
    <div v-if="!loading && !error" class="grid gap-4 lg:grid-cols-3">
      <!-- Verbindung / Account -->
      <div
        class="rounded-xl border bg-white px-4 py-3 shadow-sm dark:bg-[#0f1424] dark:border-white/10 flex flex-col gap-3"
      >
        <div class="flex items-center justify-between">
          <div class="font-medium flex items-center gap-2">
            <span
              class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-sky-700 text-xs dark:bg-sky-500/15 dark:text-sky-300"
            >
              🔗
            </span>
            Verbindung
          </div>
          <span
            class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium border"
            :class="conf?.ok
              ? 'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/40'
              : 'bg-red-50 text-red-700 border-red-100 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/40'"
          >
            <span
              class="mr-1 inline-block h-1.5 w-1.5 rounded-full"
              :class="conf?.ok ? 'bg-emerald-500' : 'bg-red-500'"
            />
            {{ conf?.ok ? 'Verbunden' : 'Fehler' }}
          </span>
        </div>

        <div class="text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <div class="truncate">
            Basis-URL:
            <span class="font-mono text-[11px]">
              {{ conf?.base || '—' }}
            </span>
          </div>
          <div>
            Account-ID:
            <span class="font-mono text-[11px]">
              {{ conf?.account_id || '—' }}
            </span>
          </div>
          <div class="mt-1 flex flex-wrap gap-1">
            <span
              v-if="conf?.has_pat"
              class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-700 dark:bg:white/5 dark:text-gray-200"
            >
              PAT konfiguriert
            </span>
            <span
              v-if="conf?.has_platform"
              class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-700 dark:bg:white/5 dark:text-gray-200"
            >
              Platform API aktiv
            </span>
          </div>
        </div>

        <div
          v-if="account"
          class="border-t pt-2 mt-1 text-xs text-gray-500 dark:text-gray-400 dark:border-white/10 space-y-1"
        >
          <div class="font-semibold text-gray-700 dark:text-gray-200">
            {{ account.name || 'Account' }}
          </div>
          <div>Zeitzone: {{ account.timezone || '—' }}</div>
          <div>Sprache: {{ account.locale || '—' }}</div>
        </div>
      </div>

      <!-- Zeitraum + Statistiken -->
      <div
        class="rounded-xl border bg-white px-4 py-3 shadow-sm dark:bg-[#0f1424] dark:border-white/10 flex flex-col gap-3 lg:col-span-2"
      >
        <div class="flex items-center justify-between gap-3">
          <div class="font-medium flex items-center gap-2">
            <span
              class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 text-xs dark:bg-indigo-500/15 dark:text-indigo-300"
            >
              📊
            </span>
            Inbox-Statistik
          </div>
          <div class="flex items-center gap-1 text-[11px]">
            <button
              v-for="opt in ['today','7d','30d']"
              :key="opt"
              type="button"
              class="px-2 py-1 rounded-md border"
              :class="range === opt
                ? 'bg-gray-900 text-white border-gray-900 dark:bg-white dark:text-black'
                : 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-white/10 dark:text-gray-300 dark:hover:bg-white/5'"
              @click="range = opt as RangeKey"
            >
              {{ opt === 'today' ? 'Heute' : opt === '7d' ? '7 Tage' : '30 Tage' }}
            </button>
          </div>
        </div>

        <div
          v-if="stats"
          class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-1 text-xs"
        >
          <div
            class="rounded-lg border bg-gray-50 px-3 py-2 dark:bg-white/5 dark:border-white/10"
          >
            <div class="text-[11px] text-gray-500 dark:text-gray-400">
              Konversationen
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ stats.conversations_count }}
            </div>
          </div>

          <div
            class="rounded-lg border bg-gray-50 px-3 py-2 dark:bg:white/5 dark:border-white/10"
          >
            <div class="text-[11px] text-gray-500 dark:text-gray-400">
              Eingehende Nachrichten
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ stats.incoming_messages_count }}
            </div>
          </div>

          <div
            class="rounded-lg border bg-gray-50 px-3 py-2 dark:bg:white/5 dark:border-white/10"
          >
            <div class="text-[11px] text-gray-500 dark:text-gray-400">
              Gesendete Nachrichten
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ stats.outgoing_messages_count }}
            </div>
          </div>

          <div
            class="rounded-lg border bg-gray-50 px-3 py-2 dark:bg:white/5 dark:border-white/10"
          >
            <div class="text-[11px] text-gray-500 dark:text-gray-400">
              Gelöste Konversationen
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ stats.resolutions_count }}
            </div>
          </div>
        </div>

        <div v-else class="text-xs text-gray-500 mt-2">
          Keine Statistikdaten vom Server erhalten.
        </div>

        <div class="mt-2 text-[11px] text-gray-400">
          Datenquelle:
          <span class="font-mono">/api/comms/woot/reports/inbox</span>
        </div>
      </div>
    </div>

    <!-- Top-Herkunftsseiten + Letzte Chats -->
    <div
      class="mt-4 rounded-xl border bg-white px-4 py-4 shadow-sm dark:bg-[#0f1424] dark:border-white/10 space-y-4"
    >
      <!-- Top-Herkunftsseiten -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <div>
            <div class="font-medium text-sm flex items-center gap-2">
              <span
                class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 text-xs dark:bg-emerald-500/15 dark:text-emerald-300"
              >
                📍
              </span>
              Top-Herkunftsseiten
            </div>
            <div class="text-[11px] text-gray-500">
              Basierend auf gespeicherten Webhook-Daten
              <span v-if="totalOriginChats">
                ({{ totalOriginChats }} Chats)
              </span
              >.
            </div>
          </div>
        </div>

        <div v-if="!origins.length" class="text-xs text-gray-500 py-2">
          Noch keine Herkunftsseiten erfasst. Starte einen Chat über das Widget,
          um Daten zu sammeln.
        </div>

        <div v-else class="space-y-3">
          <!-- kompakte Top-Karten -->
          <div class="grid md:grid-cols-2 gap-4">
            <div
              v-for="o in origins.slice(0, 4)"
              :key="o.page + '-card'"
              class="rounded-lg border bg-gray-50 px-3 py-2 text-xs dark:bg-white/5 dark:border-white/10"
            >
              <div class="flex items-center justify-between gap-2 mb-1">
                <div class="truncate font-medium text-[11px]">
                  {{ o.page }}
                </div>
                <div class="text-[11px] font-semibold">
                  {{ o.count }} Chats
                </div>
              </div>
              <div class="flex items-center gap-2 text-[10px] text-gray-500">
                <div
                  class="flex-1 h-1.5 rounded-full bg-gray-200 dark:bg-white/10 overflow-hidden"
                >
                  <div
                    class="h-full rounded-full bg-gray-900 dark:bg-white"
                    :style="{
                      width:
                        totalOriginChats > 0
                          ? Math.max(4, (o.count / totalOriginChats) * 100) + '%'
                          : '0%',
                    }"
                  />
                </div>
                <div class="w-10 text-right">
                  {{
                    totalOriginChats > 0
                      ? ((o.count / totalOriginChats) * 100).toFixed(0) + '%'
                      : '0%'
                  }}
                </div>
              </div>
            </div>
          </div>

          <!-- vollständige Tabelle -->
          <div class="border-t pt-3 text-xs dark:border-white/10">
            <table class="w-full">
              <thead>
                <tr class="text-left text-gray-500 dark:text-gray-400">
                  <th class="py-1 pr-2">Seite</th>
                  <th class="py-1 pr-2 w-16 text-right">Chats</th>
                  <th class="py-1 pr-2 w-16 text-right hidden sm:table-cell">
                    Anteil
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="o in origins"
                  :key="o.page"
                  class="border-t border-black/5 dark:border-white/10"
                >
                  <td class="py-1 pr-2 truncate max-w-xs">
                    {{ o.page || 'unbekannt' }}
                  </td>
                  <td class="py-1 pr-2 text-right font-semibold">
                    {{ o.count }}
                  </td>
                  <td class="py-1 pr-2 text-right hidden sm:table-cell">
                    {{
                      totalOriginChats > 0
                        ? ((o.count / totalOriginChats) * 100).toFixed(0) + '%'
                        : '0%'
                    }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="mt-1 text-[11px] text-gray-400">
            Datenquelle:
            <span class="font-mono">/api/comms/woot/reports/origins</span>
          </div>
        </div>
      </div>

      <!-- Letzte Chats -->
      <div
        class="rounded-xl border bg-white px-4 py-3 shadow-sm dark:bg-[#050816] dark:border-white/10"
      >
        <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <div class="font-medium text-sm flex items-center gap-2">
              <span
                class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 text-xs dark:bg-indigo-500/15 dark:text-indigo-300"
              >
                🕒
              </span>
              Letzte Chats
            </div>
            <div class="text-[11px] text-gray-500">
              Übersicht der letzten Konversationen mit Herkunft, Browser und
              Routing.
            </div>
          </div>

          <div class="flex flex-col items-end gap-2 text-[11px]">
            <div class="flex items-center gap-1">
              <button
                type="button"
                class="px-2 py-1 rounded-full border"
                :class="filterChannel === 'all'
                  ? 'bg-gray-900 text-white border-gray-900 dark:bg-white dark:text-black'
                  : 'border-gray-300 text-gray-600 dark:border-white/20 dark:text-gray-300'"
                @click="filterChannel = 'all'"
              >
                Alle
              </button>
              <button
                type="button"
                class="px-2 py-1 rounded-full border"
                :class="filterChannel === 'web'
                  ? 'bg-gray-900 text-white border-gray-900 dark:bg-white dark:text-black'
                  : 'border-gray-300 text-gray-600 dark:border-white/20 dark:text-gray-300'"
                @click="filterChannel = 'web'"
              >
                Web-Widget
              </button>
              <button
                type="button"
                class="px-2 py-1 rounded-full border"
                :class="filterChannel === 'other'
                  ? 'bg-gray-900 text-white border-gray-900 dark:bg-white dark:text-black'
                  : 'border-gray-300 text-gray-600 dark:border-white/20 dark:text-gray-300'"
                @click="filterChannel = 'other'"
              >
                Andere
              </button>
            </div>

            <div class="flex items-center gap-2">
              <input
                v-model="search"
                type="text"
                placeholder="Filter nach Seite oder E-Mail …"
                class="h-7 w-48 rounded-md border border-gray-300 px-2 text-[11px] dark:bg-[#050816] dark:border-white/20"
              />
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between mb-2 text-[11px]">
          <div class="text-gray-400">
            Datenquelle:
            <span class="font-mono">/api/comms/woot/logs/recent</span>
          </div>
          <div class="flex items-center gap-2">
            <select
              v-model.number="cleanupDays"
              class="h-7 rounded-md border border-gray-300 px-2 text-[11px] dark:bg-[#050816] dark:border-white/20"
            >
              <option :value="1">> 1 Tage</option>
              <option :value="7">> 7 Tage</option>
              <option :value="14">> 14 Tage</option>
              <option :value="30">> 30 Tage</option>
            </select>

            <button
              type="button"
              class="px-2 py-1 rounded-md border text-[11px] flex items-center gap-1 hover:bg-red-50 dark:hover:bg-red-500/10 dark:border-white/20"
              :disabled="cleanupLoading"
              @click="cleanupOld"
            >
              <span
                v-if="cleanupLoading"
                class="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin"
              />
              <span>Logs löschen</span>
            </button>
            <span v-if="cleanupInfo" class="text-gray-500">
              {{ cleanupInfo }}
            </span>
          </div>
        </div>

        <div v-if="!filteredRecent.length" class="text-xs text-gray-500 py-2">
          Noch keine Chats geloggt (oder Filter schränkt alles aus).
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr
                class="text-left text-gray-500 dark:text-gray-400 border-b border-black/5 dark:border-white/10"
              >
                <th class="py-1 pr-2">Chat</th>
                <th class="py-1 pr-2">Seite</th>
                <th class="py-1 pr-2">Kunde</th>
                <th class="py-1 pr-2">Browser / Gerät</th>
                <th class="py-1 pr-2">Sprache</th>
                <th class="py-1 pr-2">PSA</th>
                <th class="py-1 pr-2">Agent</th>
                <th class="py-1 pr-2 text-right">Start (EU/Berlin)</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in filteredRecent"
                :key="row.conversation_id"
                class="border-b border-black/5 dark:border-white/5 hover:bg-gray-50/60 dark:hover:bg-white/5"
              >
                <td class="py-1 pr-2">
                  <span
                    class="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium dark:bg-white/10"
                  >
                    <span>#{{ row.conversation_id }}</span>
                    <span
                      class="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-gray-900 text-[9px] text-white dark:bg-white dark:text-black"
                    >
                      {{
                        (row.channel || 'web')
                          .toLowerCase()
                          .includes('webwidget')
                          ? 'W'
                          : 'C'
                      }}
                    </span>
                  </span>
                </td>
                <td class="py-1 pr-2 max-w-xs truncate">
                  <a
                    v-if="row.page"
                    :href="row.page"
                    target="_blank"
                    rel="noopener"
                    class="text-xs text-blue-600 hover:underline"
                    :title="row.page"
                  >
                    {{ row.page }}
                  </a>
                  <span v-else>—</span>
                </td>
                <td class="py-1 pr-2">
                  <span class="font-medium">
                    {{ row.email || 'Unbekannt' }}
                  </span>
                </td>
                <td class="py-1 pr-2">
                  <div class="flex items-center gap-1">
                    <span
                      class="inline-flex h-5 w-5 items-center justify-center rounded-full bg-gray-900 text-[9px] text-white dark:bg-white dark:text-black"
                    >
                      🖥
                    </span>
                    <div class="flex flex-col leading-tight">
                      <span>
                        {{ row.browser || 'Browser' }} ·
                        {{ row.platform || 'OS' }}
                      </span>
                      <span class="text-[10px] text-gray-500">
                        {{ row.browser_language || '—' }}
                      </span>
                    </div>
                  </div>
                </td>
                <td class="py-1 pr-2">
                  <span
                    class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-700 dark:bg-white/10 dark:text-gray-100"
                  >
                    🌐 {{ row.browser_language || '—' }}
                  </span>
                </td>
                <td class="py-1 pr-2">
                  <span
                    v-if="row.psa_name"
                    class="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-500/10 dark:text-amber-200"
                  >
                    🎯 {{ row.psa_name }}
                  </span>
                  <span v-else class="text-[11px] text-gray-400">—</span>
                </td>
                <td class="py-1 pr-2">
                  <span
                    v-if="row.agent_name"
                    class="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200"
                  >
                    👤 {{ row.agent_name }}
                  </span>
                  <span v-else class="text-[11px] text-gray-400">
                    Unassigned
                  </span>
                </td>
                <td class="py-1 pr-2 text-right text-[11px] text-gray-500">
                  {{ formatDateTime(row.initiated_at) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
