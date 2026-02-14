<!-- src/pages/LiveVisitors.vue -->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import api from '@/api'

type VisitorsResponse = {
  total_online: number
  visitors: any[]
  by_page: Record<string, number>
  by_browser: Record<string, number>
  by_country: Record<string, number>
  by_device?: Record<string, number>
  by_os?: Record<string, number>
  window_minutes?: number
  include_bots?: boolean
  last_updated?: string
}

const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<VisitorsResponse | null>(null)
let timer: number | null = null

async function load() {
  try {
    error.value = null
    const res = await api.get('/live/visitors') // optional: ?window=2&bots=0
    data.value = res.data
  } catch (e) {
    error.value = 'Fehler beim Laden der Live-Daten'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  timer = window.setInterval(load, 5000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

// für Tabellen/Card-Ansicht
const visitors = computed(() => data.value?.visitors ?? [])

// letztes Update als Uhrzeit
const lastUpdated = computed(() => {
  if (!data.value?.last_updated) return null
  return new Date(data.value.last_updated).toLocaleTimeString()
})

// Device-Icon + Label
function deviceIcon(type?: string | null): string {
  switch ((type || '').toLowerCase()) {
    case 'mobile':
      return '📱'
    case 'tablet':
      return '📲'
    case 'desktop':
      return '💻'
    case 'bot':
      return '🤖'
    default:
      return '❓'
  }
}

function deviceLabel(type?: string | null): string {
  switch ((type || '').toLowerCase()) {
    case 'mobile':
      return 'Handy'
    case 'tablet':
      return 'Tablet'
    case 'desktop':
      return 'Desktop'
    case 'bot':
      return 'Bot / Crawler'
    default:
      return 'Unbekannt'
  }
}

// Country-Mapping (XK -> Kosovo)
function mapCountry(cc?: string | null): string {
  if (!cc) return 'Unbekannt'
  if (cc === 'XK') return 'Kosovo'
  return cc
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold">Live Besucher</h1>
        <p class="mt-1 text-sm text-gray-500">
          Aktive Sessions der letzten {{ data?.window_minutes ?? 2 }} Minuten – automatisch
          aktualisiert.
        </p>
      </div>

      <div v-if="lastUpdated" class="text-xs text-gray-500">
        Letztes Update:
        <span class="font-medium text-gray-700 dark:text-gray-100">{{ lastUpdated }}</span>
      </div>
    </div>

    <!-- Fehler / Loading -->
    <div v-if="error" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">
      {{ error }}
    </div>

    <div
      v-else-if="loading"
      class="p-4 rounded-xl border bg-white dark:bg-[#0f1424] text-sm"
    >
      Lädt…
    </div>

    <!-- Inhalt -->
    <div v-else-if="data" class="space-y-6">
      <!-- KPI Cards -->
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <!-- Aktive Besucher -->
        <div
          class="rounded-2xl border bg-white dark:bg-[#0f1424] p-4 flex flex-col justify-between"
        >
          <div class="flex items-center justify-between gap-2">
            <div>
              <div class="text-[11px] uppercase tracking-wide text-gray-400">
                Aktive Besucher
              </div>
              <div class="mt-2 text-3xl font-semibold">
                {{ data.total_online }}
              </div>
            </div>
            <div class="text-xs text-gray-400 text-right">
              Fenster<br />
              <span class="font-medium text-gray-700 dark:text-gray-100">
                {{ data.window_minutes ?? 2 }}&nbsp;Minuten
              </span>
            </div>
          </div>
          <div class="mt-3 text-xs text-gray-500">
            Aktualisiert alle 5&nbsp;Sekunden.
          </div>
        </div>

        <!-- Browser & Geräte -->
        <div class="rounded-2xl border bg-white dark:bg-[#0f1424] p-4">
          <div class="text-[11px] uppercase tracking-wide text-gray-400">
            Browser &amp; Geräte
          </div>
          <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <!-- Browser -->
            <div class="space-y-2 text-sm">
              <div class="text-xs font-medium text-gray-500">Browser</div>
              <div
                v-for="(count, browser) in data.by_browser"
                :key="browser"
                class="flex items-center justify-between gap-2"
              >
                <div class="flex items-center gap-2">
                  <span class="inline-flex h-2 w-2 rounded-full bg-black/40 dark:bg-white/60" />
                  <span>{{ browser }}</span>
                </div>
                <span class="font-medium text-xs">{{ count }}</span>
              </div>
              <div
                v-if="!Object.keys(data.by_browser || {}).length"
                class="text-xs text-gray-500"
              >
                Keine Daten.
              </div>
            </div>

            <!-- Geräte -->
            <div class="space-y-2 text-sm">
              <div class="text-xs font-medium text-gray-500">Geräte</div>
              <div
                v-for="(count, dev) in data.by_device"
                :key="dev"
                class="flex items-center justify-between gap-2"
              >
                <div class="flex items-center gap-2">
                  <span>{{ deviceIcon(dev) }}</span>
                  <span class="text-xs">{{ deviceLabel(dev) }}</span>
                </div>
                <span class="font-medium text-xs">{{ count }}</span>
              </div>
              <div
                v-if="!data.by_device || !Object.keys(data.by_device).length"
                class="text-xs text-gray-500"
              >
                Keine Daten.
              </div>
            </div>
          </div>
        </div>

        <!-- Top Seiten & Länder -->
        <div class="rounded-2xl border bg-white dark:bg-[#0f1424] p-4">
          <div class="text-[11px] uppercase tracking-wide text-gray-400">
            Top Seiten &amp; Länder
          </div>

          <div
            class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2"
          >
            <!-- Top Seiten -->
            <div class="space-y-1 text-sm">
              <div class="text-xs font-medium text-gray-500">Seiten</div>
              <div
                v-for="(count, page) in data.by_page"
                :key="page"
                class="flex items-center justify-between gap-2"
              >
                <span
                  class="truncate max-w-[180px] text-xs sm:text-[13px]"
                  :title="page"
                >
                  {{ page }}
                </span>
                <span class="text-xs font-semibold">{{ count }}</span>
              </div>
              <div
                v-if="!Object.keys(data.by_page || {}).length"
                class="text-xs text-gray-500"
              >
                Keine Daten.
              </div>
            </div>

            <!-- Länder -->
            <div class="space-y-1 text-sm">
              <div class="text-xs font-medium text-gray-500">Länder</div>
              <div
                v-for="(count, cc) in data.by_country"
                :key="cc"
                class="flex items-center justify-between gap-2"
              >
                <span class="text-xs sm:text-[13px]">
                  {{ mapCountry(cc) }}
                </span>
                <span class="text-xs font-semibold">{{ count }}</span>
              </div>
              <div
                v-if="!Object.keys(data.by_country || {}).length"
                class="text-xs text-gray-500"
              >
                Keine Daten.
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Besucher-Liste -->
      <div class="rounded-2xl border bg-white dark:bg-[#0f1424]">
        <div
          class="border-b px-4 py-3 flex items-center justify-between text-sm font-medium"
        >
          <span>Aktive Sessions (letzte {{ data.window_minutes ?? 2 }} Minuten)</span>
          <span class="text-xs text-gray-500">
            {{ visitors.length }} Session<span v-if="visitors.length !== 1">s</span>
          </span>
        </div>

        <!-- Desktop: Tabelle -->
        <div class="hidden md:block max-h-[520px] overflow-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 dark:bg-black/20">
              <tr class="text-xs text-gray-500">
                <th class="px-4 py-2 text-left">Letztes Update</th>
                <th class="px-4 py-2 text-left">Seite</th>
                <th class="px-4 py-2 text-left">Browser</th>
                <th class="px-4 py-2 text-left">Referrer</th>
                <th class="px-4 py-2 text-left">IP / Gerät / Standort</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="v in visitors"
                :key="v.session_id"
                class="border-t border-black/5 hover:bg-black/5 dark:hover:bg-white/5"
              >
                <td class="px-4 py-2 text-xs whitespace-nowrap">
                  {{ new Date(v.last_seen).toLocaleTimeString() }}
                </td>
                <td class="px-4 py-2">
                  <span
                    class="block max-w-[320px] truncate text-xs"
                    :title="v.url"
                  >
                    {{ v.url }}
                  </span>
                </td>
                <td class="px-4 py-2 text-xs">
                  {{ v.user_agent }}
                </td>
                <td class="px-4 py-2 text-xs">
                  <span
                    class="block max-w-[260px] truncate"
                    :title="v.referrer"
                  >
                    {{ v.referrer || 'Direkt' }}
                  </span>
                </td>
                <td class="px-4 py-2 text-xs space-y-1">
                  <div class="flex items-center gap-1">
                    <span>{{ deviceIcon(v.device_type) }}</span>
                    <span class="font-mono text-[11px]">
                      {{ v.ip || '–' }}
                    </span>
                    <span class="text-[11px] text-gray-500">
                      • {{ deviceLabel(v.device_type) }}
                    </span>
                  </div>
                  <div class="text-[11px] text-gray-500">
                    <span v-if="v.country_code">
                      {{ mapCountry(v.country_code) }}
                    </span>
                    <span v-if="v.city">
                      • {{ v.city }}
                    </span>
                    <span v-if="!v.country_code && !v.city">
                      Unbekannt
                    </span>
                  </div>
                </td>
              </tr>
              <tr v-if="!visitors.length">
                <td colspan="5" class="px-4 py-6 text-center text-sm text-gray-500">
                  Aktuell keine Besucher online.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile: Card-Layout -->
        <div
          class="md:hidden max-h-[520px] overflow-auto divide-y divide-black/5 dark:divide-white/10"
        >
          <div
            v-for="v in visitors"
            :key="v.session_id"
            class="px-4 py-3 text-xs space-y-2"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="font-medium truncate max-w-[180px]" :title="v.url">
                {{ v.url }}
              </div>
              <div class="text-[11px] text-gray-500 whitespace-nowrap">
                {{ new Date(v.last_seen).toLocaleTimeString() }}
              </div>
            </div>

            <div class="flex flex-wrap gap-2 items-center">
              <span
                class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px]"
              >
                {{ v.referrer || 'Direkt' }}
              </span>
              <span
                class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px]"
              >
                {{ deviceIcon(v.device_type) }}&nbsp;{{ v.ip || 'IP unbekannt' }}
              </span>
              <span
                class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px]"
              >
                {{ mapCountry(v.country_code) || 'Land ?' }}
                <span v-if="v.city">&nbsp;•&nbsp;{{ v.city }}</span>
              </span>
            </div>

            <div class="text-[11px] text-gray-500">
              {{ v.user_agent }}
            </div>
          </div>

          <div
            v-if="!visitors.length"
            class="px-4 py-6 text-center text-sm text-gray-500"
          >
            Aktuell keine Besucher online.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
