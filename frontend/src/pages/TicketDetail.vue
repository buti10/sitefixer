<!-- src/pages/TicketDetails.vue -->
<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-semibold">Ticket #{{ id }}</h1>
      <RouterLink to="/" class="text-blue-600 hover:underline text-sm">← Zurück zum Dashboard</RouterLink>
    </div>

    <!-- Fehler / Loading -->
    <div v-if="error" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">{{ error }}</div>
    <div v-else-if="loading" class="p-4 rounded-xl border bg-white dark:bg-[#0f1424]">Lädt…</div>

    <!-- Inhalt -->
    <div v-else class="space-y-6">
      <!-- Kundendaten -->
      <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
        <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium">Kundendaten</div>
        <div class="p-4 grid gap-4 sm:grid-cols-2 text-sm">
          <div>
            <div class="text-xs opacity-70 mb-0.5">Ticket-ID</div>
            <div>#{{ data.ticket_id ?? id }}</div>
          </div>
          <div>
            <div class="text-xs opacity-70 mb-0.5">Datum</div>
            <div>{{ fmt(data.created_at) }}</div>
          </div>
          <div>
            <div class="text-xs opacity-70 mb-0.5">Name</div>
            <div>{{ data.name || '—' }}</div>
          </div>
          <div>
            <div class="text-xs opacity-70 mb-0.5">E-Mail</div>
            <div>
              <a v-if="data.email" :href="`mailto:${data.email}`" class="text-blue-600 hover:underline">{{ data.email }}</a>
              <span v-else>—</span>
            </div>
          </div>
          <div>
            <div class="text-xs opacity-70 mb-0.5">Domain</div>
            <div>
              <a v-if="data.domain" :href="norm(data.domain)" target="_blank" rel="noopener" class="text-blue-600 hover:underline">{{ data.domain }}</a>
              <span v-else>—</span>
            </div>
          </div>
          <div>
            <div class="text-xs opacity-70 mb-0.5">Prio</div>
            <div>{{ data.prio || '—' }}</div>
          </div>
          <div>
            <div class="text-xs opacity-70 mb-0.5">Status</div>
            <div>{{ data.status || '—' }}</div>
          </div>

          <div class="sm:col-span-2" v-if="data.beschreibung">
            <div class="text-xs opacity-70 mb-0.5">Beschreibung</div>
            <pre class="whitespace-pre-wrap">{{ data.beschreibung }}</pre>
          </div>
        </div>
      </div>

      <!-- Zugänge -->
      <div class="space-y-2">
        <div class="font-medium text-sm px-1">Zugänge</div>

        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <!-- FTP -->
          <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
            <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium">FTP</div>
            <div class="p-4 grid gap-3 text-sm">
              <div>
                <div class="text-xs opacity-70 mb-0.5">Host</div>
                <div class="break-all">{{ data.ftp_host || data.ftp_server || data.zugang_ftp_host || '—' }}</div>
              </div>
              <div>
                <div class="text-xs opacity-70 mb-0.5">User</div>
                <div class="break-all">{{ data.ftp_user || data.zugang_ftp_user || '—' }}</div>
              </div>

              <div>
                <div class="text-xs opacity-70 mb-0.5">Passwort</div>
                <div class="flex items-center gap-2">
                  <span class="select-all">
                    {{ ftpPass ? (show.ftp ? ftpPass : '••••••••') : '—' }}
                  </span>
                  <button
                    type="button"
                    class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                    :disabled="!ftpPass"
                    @click="show.ftp = !show.ftp"
                  >
                    {{ show.ftp ? 'Verbergen' : 'Anzeigen' }}
                  </button>
                  <button
                    type="button"
                    class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                    :disabled="!ftpPass"
                    @click="copy(ftpPass)"
                  >
                    {{ copied === 'ftp' ? 'Kopiert' : 'Kopieren' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Website -->
          <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
            <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium">Website</div>
            <div class="p-4 grid gap-3 text-sm">
              <div>
                <div class="text-xs opacity-70 mb-0.5">Login</div>
                <div class="break-all">{{ data.website_login || data.website_user || data.zugang_website_login || '—' }}</div>
              </div>

              <div>
                <div class="text-xs opacity-70 mb-0.5">Passwort</div>
                <div class="flex items-center gap-2">
                  <span class="select-all">
                    {{ webPass ? (show.web ? webPass : '••••••••') : '—' }}
                  </span>
                  <button
                    type="button"
                    class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                    :disabled="!webPass"
                    @click="show.web = !show.web"
                  >
                    {{ show.web ? 'Verbergen' : 'Anzeigen' }}
                  </button>
                  <button
                    type="button"
                    class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                    :disabled="!webPass"
                    @click="copy(webPass)"
                  >
                    {{ copied === 'web' ? 'Kopiert' : 'Kopieren' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Hosting -->
          <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
            <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium">Hosting</div>
            <div class="p-4 grid gap-3 text-sm">
              <div>
                <div class="text-xs opacity-70 mb-0.5">URL</div>
                <div class="break-all">{{ data.hosting_url || data.hoster_url || data.zugang_hosting_url || '—' }}</div>
              </div>
              <div>
                <div class="text-xs opacity-70 mb-0.5">User</div>
                <div class="break-all">{{ data.hosting_user || data.zugang_hosting_user || '—' }}</div>
              </div>

              <div>
                <div class="text-xs opacity-70 mb-0.5">Passwort</div>
                <div class="flex items-center gap-2">
                  <span class="select-all">
                    {{ hostPass ? (show.host ? hostPass : '••••••••') : '—' }}
                  </span>
                  <button
                    type="button"
                    class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                    :disabled="!hostPass"
                    @click="show.host = !show.host"
                  >
                    {{ show.host ? 'Verbergen' : 'Anzeigen' }}
                  </button>
                  <button
                    type="button"
                    class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                    :disabled="!hostPass"
                    @click="copy(hostPass)"
                  >
                    {{ copied === 'host' ? 'Kopiert' : 'Kopieren' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Aktionen -->
      <div class="grid gap-6 lg:grid-cols-2">
        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
          <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium">Malware-Scan</div>
          <div class="p-4">
            <button class="px-4 py-2 rounded-md bg-red-600 text-white hover:bg-red-700" @click="go(`/tickets/${id}/scans/malware`)">
              Starten
            </button>
          </div>
        </div>

        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
          <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium">SEO-Scan</div>
          <div class="p-4">
            <button class="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700" @click="go(`/tickets/${id}/scans/seo`)">
              Starten
            </button>
          </div>
        </div>
       <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
         <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium">Repair</div>
         <div class="p-4">
           <button class="px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700" @click="goRepair()">
             Starten
           </button>
         </div>
       </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTicket } from '../api'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)

// Query/Session als Fallback
function qObj() { try { const s = String(route.query.s || ''); return s ? JSON.parse(decodeURIComponent(atob(s))) : null } catch { return null } }
function ssObj() { try { return JSON.parse(sessionStorage.getItem('sf_last_ticket') || 'null') } catch { return null } }

const stateData = ref<any>(qObj() || (history.state as any)?.ticket || ssObj() || { ticket_id: id })
const apiData   = ref<any>({})
const data      = computed(() => ({ ...stateData.value, ...apiData.value }))

const loading = ref(true)
const error   = ref<string|null>(null)

onMounted(async () => {
  try {
    const r = await getTicket(id)          // 404 okay, wir zeigen Fallback
    if (r && typeof r === 'object') apiData.value = r
  } catch (e:any) {
    const s = e?.response?.status
    if (s && s !== 404) error.value = e?.response?.data?.msg || e?.message || 'Konnte Ticket nicht laden'
  } finally {
    loading.value = false
  }
})

// Anzeige/Kopie UI
const show   = reactive({ ftp: false, web: false, host: false })
const copied = ref<'ftp' | 'web' | 'host' | ''>('')

// Passwort-Strings (mit deinen Fallback-Feldern)
const ftpPass  = computed(() => data.value.ftp_pass     || data.value.zugang_ftp_pass     || '')
const webPass  = computed(() => data.value.website_pass || data.value.zugang_website_pass || '')
const hostPass = computed(() => data.value.hosting_pass || data.value.zugang_hosting_pass || '')

async function copy(text: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    if (text === ftpPass.value)  copied.value = 'ftp'
    if (text === webPass.value)  copied.value = 'web'
    if (text === hostPass.value) copied.value = 'host'
    setTimeout(() => { copied.value = '' }, 1200)
  } catch {}
}

function fmt(d?: string|null){
  if(!d) return '—'
  try { return (/^\d{4}-\d{2}-\d{2}/.test(d) ? d : new Date(d).toISOString()).slice(0,10) }
  catch { return String(d).slice(0,10) }
}
function goRepair(){
  router.push({
    path: `/tickets/${id}/repairs`,
    state: { ticket: data.value }   // Kundendaten + Zugänge mitgeben
  })
}

function norm(u?: string){ return !u ? '#' : /^https?:\/\//i.test(u) ? u : `https://${u}` }
function go(p:string){ router.push(p) }
</script>
