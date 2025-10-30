# TicketRepairs.vue
<template>
  <div class="space-y-6">
    <div v-if="busyAny" class="fixed top-3 right-3 z-50 flex items-center gap-2 px-3 py-2 rounded-md border bg-white/90 dark:bg-[#0f1424]/90 text-xs shadow">
      <svg class="animate-spin w-4 h-4" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" opacity=".25"/>
        <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" stroke-width="3" fill="none"/>
      </svg>
      arbeitet…
    </div>

    <!-- Kopf -->
    <div class="flex items-center justify-between">
      <RouterLink :to="`/tickets/${tid}`" class="text-sm text-blue-600 hover:underline">← Zurück zu Ticket #{{ tid }}</RouterLink>
      <div class="flex items-center gap-3 text-xs">
        <span class="opacity-60">Repair-Session:</span>
        <span class="px-2 py-0.5 rounded bg-black/5 dark:bg-white/10">{{ sessionId ?? '—' }}</span>
      </div>
    </div>

    <!-- Kundendaten + Zugänge -->
    <div class="grid xl:grid-cols-3 gap-4">
      <!-- Kundendaten -->
      <div class="rounded-2xl border bg-white dark:bg-[#0f1424] p-4 shadow-sm">
        <div class="flex items-center gap-2 mb-3">
          <svg viewBox="0 0 24 24" class="w-5 h-5 text-black/60 dark:text-white/70"><path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5Zm0 2c-5 0-9 2.5-9 5v1h18v-1c0-2.5-4-5-9-5Z" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
          <h3 class="font-semibold">Kundendaten</h3>
        </div>
        <div class="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
          <div class="opacity-60">Ticket-ID</div><div>#{{ tid }}</div>
          <div class="opacity-60">Name</div><div>{{ ticketName }}</div>
          <div class="opacity-60">E-Mail</div><div>{{ ticketEmail }}</div>
          <div class="opacity-60">Domain</div>
          <div class="flex items-center gap-2">
            <a v-if="ticketDomain" :href="ticketDomain" target="_blank" class="text-blue-600 hover:underline">{{ ticketDomain }}</a>
            <span v-else>—</span>
            <button v-if="ticketDomain" class="px-2 py-1 rounded border text-xs" @click="testDomain">testen</button>
          </div>
          <div class="opacity-60">Status</div><div>{{ ticketStatus }}</div>
          <div class="opacity-60">Prio</div><div>{{ ticketPrio || '—' }}</div>
        </div>
      </div>

      <!-- Zugänge -->
      <div class="rounded-2xl border bg-white dark:bg-[#0f1424] p-4 shadow-sm xl:col-span-2">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <svg viewBox="0 0 24 24" class="w-5 h-5 text-black/60 dark:text-white/70"><path d="M21 7l-2 2m-6.5 6.5L17 11m-4.5 4.5 2.5 2.5H18v2h2v2h2" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
            <h3 class="font-semibold">Zugänge</h3>
          </div>
          <div class="flex items-center gap-2 text-xs">
            <span class="opacity-60">SFTP</span>
            <span :class="['inline-flex items-center gap-1 px-2 py-0.5 rounded border',
                          sftpState==='ok'    ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                          sftpState==='busy'  ? 'bg-amber-50  text-amber-700  border-amber-200'  :
                                                'bg-rose-50    text-rose-700    border-rose-200']">
              <span :class="['w-2 h-2 rounded-full',
                            sftpState==='ok' ? 'bg-emerald-500' : sftpState==='busy' ? 'bg-amber-500' : 'bg-rose-500']"></span>
              {{ sftpLabel }}
            </span>
          </div>
        </div>

        <div class="grid md:grid-cols-4 gap-2 text-sm">
          <input v-model="conn.host" class="rounded border px-3 py-2 bg-transparent" placeholder="SFTP Host" />
          <input v-model="conn.user" class="rounded border px-3 py-2 bg-transparent" placeholder="User" />
          <input :type="showPw ? 'text' : 'password'" v-model="conn.password" class="rounded border px-3 py-2 bg-transparent" placeholder="Passwort" />
          <div class="flex gap-2">
            <input v-model.number="conn.port" class="w-24 rounded border px-3 py-2 bg-transparent" placeholder="22" />
            <button @click="showPw = !showPw" class="px-3 py-2 rounded border">{{ showPw ? 'Verbergen' : 'Anzeigen' }}</button>
          </div>
        </div>
        <div class="mt-2 grid md:grid-cols-[1fr_auto_auto] gap-2 text-sm items-center">
          <input v-model="root" class="rounded border px-3 py-2 bg-transparent" placeholder="Webroot z. B. /htdocs/www oder /" />
          <button @click="connectAndStart" class="px-4 py-2 rounded-md bg-black text-white">SFTP verbinden + Session starten</button>
          <button @click="reconnect" class="px-3 py-2 rounded border">Neu verbinden</button>
        </div>
        <div class="mt-1 text-xs opacity-70">SFTP-SID: {{ sid || '—' }}</div>
        <div v-if="formErr" class="mt-2 text-xs text-rose-700">{{ formErr }}</div>
      </div>
    </div>

    <!-- Explorer + Viewer -->
    <div class="grid xl:grid-cols-2 gap-4">
      <!-- Tree -->
      <div class="rounded-2xl border bg-white dark:bg-[#0f1424] shadow-sm">
        <div class="px-4 py-3 border-b text-sm font-medium flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="opacity-70">Remote:</span>
            <span class="font-mono">{{ root || '/' }}</span>
            <button class="ml-2 px-2 py-1 rounded border text-xs" @click="goUp" :disabled="root==='/'">Zurück</button>
            <button class="px-2 py-1 rounded border text-xs" @click="applyRootFromSelection" :disabled="!selected?.isDir">Als Root setzen</button>
          </div>
          <div class="flex gap-2 text-xs">
            <input v-model="leftPathInput" class="rounded border px-2 py-1 bg-transparent w-64" placeholder="/pfad" />
            <button @click="gotoLeft(leftPathInput)" class="px-2 py-1 rounded border">Gehe</button>
            <button @click="reloadLeft" class="px-2 py-1 rounded border" :disabled="busy.list">{{ busy.list ? 'lädt…' : 'Neu laden' }}</button>
            <button class="px-2 py-1 rounded border" :disabled="binary || !viewPath" @click="saveView">Speichern</button>
          </div>
        </div>

        <div class="grid grid-cols-file px-3 py-2 sticky top-[var(--stick,0)] bg-white dark:bg-[#0f1424] text-xs font-medium border-y select-none">
          <div>Name</div><div class="text-right pr-2">Größe</div><div class="text-right pr-2">Rechte</div><div class="text-right">Geändert</div><div class="text-right pr-2">Aktionen</div>
        </div>

        <div class="max-h-[480px] overflow-auto text-sm">
          <div
            v-for="row in flatTree"
            :key="row.key"
            class="border-b hover:bg-black/5 dark:hover:bg-white/5"
            :class="isSelected(row) ? 'bg-emerald-50 dark:bg-emerald-900/10' : ''"
            @click="selectRow(row)"
          >
            <div class="grid grid-cols-file items-center px-3 relative">
              <div class="flex items-center truncate">
                <div :style="{width: `${row.depth*14}px`}"></div>
                <button v-if="row.isDir" class="w-5 h-5 mr-1 text-black/60 dark:text-white/70" @click.stop="toggle(row.path)">
                  <svg viewBox="0 0 24 24" class="w-4 h-4" :class="expanded.has(row.path)?'rotate-90':''"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                </button>
                <svg v-if="row.isDir" viewBox="0 0 24 24" class="w-4 h-4 mr-2 text-amber-600 shrink-0"><path d="M3 6h6l2 2h10v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6z" fill="currentColor"/></svg>
                <svg v-else viewBox="0 0 24 24" class="w-4 h-4 mr-2 text-slate-600 shrink-0"><path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="currentColor"/></svg>
                <button class="py-2 text-left hover:underline truncate" @click.stop="row.isDir ? toggle(row.path) : openFile(row.path)">{{ row.name }}</button>
              </div>

              <div class="text-right pr-2 tabular-nums">{{ row.isDir ? '' : fmtSize(row.size) }}</div>
              <div class="text-right pr-2 tabular-nums">{{ fmtPerm(row.mode) }}</div>
              <div class="text-right tabular-nums">{{ fmtTime(row.mtime) }}</div>

              <div class="w-full flex justify-end pr-2 relative" @click.stop>
                <button class="px-2 py-1 rounded border text-xs" @click="toggleMenu(row.key)">⋮</button>
                <div v-if="menuOpen===row.key" class="absolute right-2 top-7 z-20 w-56 rounded-md border bg-white dark:bg-[#0f1424] shadow">
                  <button v-if="row.isDir" class="w-full text-left px-3 py-2 text-xs hover:bg-black/5 dark:hover:bg-white/10" @click="setRootFromSelection(row.path); closeMenu()">Als Root setzen</button>
                  <button class="w-full text-left px-3 py-2 text-xs hover:bg-black/5 dark:hover:bg-white/10" @click="openReplaceDialog(row); closeMenu()">Ersetzen (aus Core)</button>
                  <button class="w-full text-left px-3 py-2 text-xs hover:bg-black/5 dark:hover:bg-white/10" @click="renamePath(row); closeMenu()">Umbenennen</button>
                  <button class="w-full text-left px-3 py-2 text-xs hover:bg-black/5 dark:hover:bg-white/10" @click="chmodPath(row); closeMenu()">Rechte anpassen</button>
                  <button class="w-full text-left px-3 py-2 text-xs text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-900/20" @click="deletePath(row); closeMenu()">Löschen</button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!flatTree.length" class="p-4 text-xs opacity-60">Keine Einträge</div>
        </div>

        <div class="px-4 py-3 border-t flex flex-wrap gap-2">
          <button class="px-3 py-2 rounded border" @click="detectCMS">CMS erkennen</button>
          <button class="px-3 py-2 rounded border" @click="loadCacheIndex">Core-Index laden</button>
          <button class="px-3 py-2 rounded-md bg-emerald-600 text-white" @click="runDiagnose" :disabled="busy.diagnose">{{ busy.diagnose ? 'Diagnose läuft…' : 'Diagnose starten' }}</button>
          <button class="px-3 py-2 rounded border" @click="fetchOpsLog">Aktions-Log</button>
          <button class="px-3 py-2 rounded border" @click="fixPerms" :disabled="!sid || busy.fixPerms">{{ busy.fixPerms ? 'Rechte werden gesetzt…' : 'Rechte reparieren' }}</button>
        </div>
      </div>

      <!-- Viewer -->
<!-- Viewer -->
      <div class="rounded-2xl border bg-white dark:bg-[#0f1424] shadow-sm">
        <div class="px-4 py-3 border-b text-sm font-medium flex items-center justify-between">
          <span>Viewer</span>
          <div class="flex items-center gap-2 text-xs">
            <span class="opacity-70">Pfad: <span class="font-mono">{{ viewPath || '—' }}</span></span>
            <button type="button" class="px-2 py-1 rounded border" :disabled="binary || !viewPath" @click="reloadView">Neu laden</button>
            <button type="button" class="px-2 py-1 rounded border" :disabled="binary || !viewText" @click="scanCurrentFile">KI prüfen</button>
            <button type="button" class="px-2 py-1 rounded border" :disabled="binary || !viewText" @click="saveView">Speichern</button>
          </div>
        </div>

        <div v-if="viewLoading" class="p-4 text-sm">lädt…</div>

        <div v-else-if="!binary" class="editor-wrap relative">
    <!-- Gutter -->
          <div ref="gutter" class="editor-gutter" :style="{height: editorHeight+'px'}">
            <div class="font-mono text-[11px] tabular-nums leading-5 select-none">
              <div v-for="(_,idx) in lineCount" :key="idx"
                :class="['px-2', (idx+1)===currentLine ? 'bg-yellow-100/70 dark:bg-yellow-900/30' : '']">
                {{ idx+1 }}
              </div>
            </div>
          </div>
    <!-- Textarea -->
          <textarea
            ref="editor"
            v-model="viewText"
            class="editor-textarea font-mono text-xs leading-5"
            spellcheck="false"
            @scroll="syncScroll"
            @click="updateCurrentLine"
            @keyup="updateCurrentLine"></textarea>
        </div>

        <div v-else class="p-4 text-sm">Binärdatei ({{ sizeHint }} Bytes). Vorschau unterdrückt.</div>

        <div class="mt-2 text-xs opacity-60">
          Truncated: {{ truncated }}, mtime: {{ mtime || '—' }}
        </div>

          <div v-if="fileFindings.length" class="mt-3 text-xs">
            <div class="font-medium mb-1">Heuristische Befunde</div>
            <ul class="list-disc pl-5 space-y-1">
              <li v-for="f in fileFindings" :key="f.code">
                <span class="font-mono">{{ f.code }}</span> — {{ f.title }}
                <span v-if="f.severity" class="ml-1 px-1 rounded text-[10px]"
                  :class="f.severity==='high'?'bg-rose-100 text-rose-700':f.severity==='med'?'bg-amber-100 text-amber-700':'bg-slate-100 text-slate-700'">
                  {{ f.severity }}
                </span>
                <div v-if="f.detail" class="opacity-70">{{ f.detail }}</div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Status -->
    <div class="rounded-2xl border bg-white dark:bg-[#0f1424] p-3 space-y-3">
      <ol class="flex gap-4 text-xs">
        <li :class="stepClass('root')">1) Root <span v-if="!!rootSet">✔</span></li>
        <li :class="stepClass('cache')">2) Core-Index <span v-if="run.cache==='ok'">✔</span><span v-else-if="run.cache==='busy'">…</span></li>
        <li :class="stepClass('diag')">3) Diagnose <span v-if="run.diag==='ok'">✔</span><span v-else-if="run.diag==='busy'">…</span></li>
      </ol>

      <div v-if="ui.msg" class="text-xs p-2 rounded border" :class="ui.msgType==='err'?'border-rose-300 text-rose-700':'border-emerald-300 text-emerald-700'">
        {{ ui.msg }}
      </div>

      <div class="flex gap-2 text-xs">
        <button class="px-2 py-1 rounded border" :class="ui.tab==='cache'?'bg-black text-white':''" @click="ui.tab='cache'">Core-Index</button>
        <button class="px-2 py-1 rounded border" :class="ui.tab==='diag'?'bg-black text-white':''"  @click="ui.tab='diag'">Diagnose</button>
        <button class="px-2 py-1 rounded border" :class="ui.tab==='log'?'bg-black text-white':''"   @click="ui.tab='log'">Aktions-Log</button>
      </div>

      <div v-if="ui.tab==='cache'">
        <div v-if="!cacheIndex">Noch nichts geladen.</div>
        <table v-else class="w-full text-xs">
          <thead><tr class="border-b"><th class="text-left py-1">CMS</th><th class="text-left">Version</th><th class="text-left">Pfad</th></tr></thead>
          <tbody>
            <tr v-for="row in cacheIndex.items" :key="row.key" class="border-b">
              <td class="py-1">{{ row.cms }}</td>
              <td>{{ row.version }}</td>
              <td class="truncate font-mono">{{ row.path }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="ui.tab==='diag'">
  <div v-if="!diagnose">Noch nicht gestartet.</div>
  <div v-else class="space-y-3">
    <div class="text-xs opacity-70">CMS: {{ diagnose.cms || 'unbekannt' }} · Root: {{ diagnose.root }}</div>

    <ul class="space-y-2">
      <li v-for="f in diagnose.findings" :key="f.code" class="rounded border p-2">
        <div class="text-sm font-medium">
          <span class="font-mono">{{ f.code }}</span> — {{ f.title }}
          <span v-if="f.severity" class="ml-1 px-1 rounded text-[10px]"
            :class="f.severity==='high'?'bg-rose-100 text-rose-700':f.severity==='med'?'bg-amber-100 text-amber-700':'bg-slate-100 text-slate-700'">
            {{ f.severity }}
          </span>
        </div>

        <div v-if="f.detail" class="text-xs opacity-70 mt-1">{{ f.detail }}</div>

        <!-- Einzelpfad/Modus -->
        <div v-if="f.path || f.mode" class="mt-1 text-xs font-mono">
          <div v-if="f.path">Pfad: {{ f.path }}</div>
          <div v-if="f.mode">Modus: {{ f.mode }}<span v-if="f.expect"> · erwartet: {{ f.expect }}</span></div>
        </div>

        <!-- Mehrere Items: Pfad + Zeile + Snippet -->
        <div v-if="f.items && f.items.length" class="mt-2">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b">
                <th class="text-left py-1">Pfad</th>
                <th class="text-left">Zeile</th>
                <th class="text-left">Ausschnitt</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in f.items" :key="it.path+'-'+it.line" class="border-b align-top">
                <td class="font-mono truncate max-w-[420px]" :title="it.path">{{ it.path }}</td>
                <td class="whitespace-nowrap">{{ it.line }}</td>
                <td class="font-mono">{{ it.snippet }}</td>
                <td class="text-right">
                  <button class="px-2 py-1 rounded border text-xs" @click="openFile(it.path).then(()=>jumpToLine(it.line))">Öffnen</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </li>
    </ul>
  </div>
</div>


      <div v-if="ui.tab==='log'">
        <div v-if="!opsLog.length" class="text-xs">Noch keine Einträge.</div>
        <ul v-else class="text-xs space-y-1 max-h-40 overflow-auto">
          <li v-for="e in opsLog" :key="e.ts" class="font-mono">
            {{ new Date(e.ts*1000).toLocaleString() }} · {{ e.action }} · {{ e.note || '' }}
          </li>
        </ul>
      </div>
    </div>

    <!-- Ersetzen-Dialog -->
    <div v-if="replaceDlg.open" class="fixed inset-0 bg-black/40 grid place-items-center z-50">
      <div class="w-[880px] max-w-[95vw] rounded-xl border bg-white dark:bg-[#0f1424] p-4 space-y-3">
        <div class="text-sm font-medium">Aus Core ersetzen</div>
        <div class="text-xs opacity-70">
          Ziel: <span class="font-mono">{{ replaceDlg.targetPath }}</span> · Quelle: <span class="font-mono">{{ CORE_ROOT_LABEL }}</span>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <!-- Core-Baum -->
          <div class="rounded-xl border overflow-hidden">
            <div class="px-3 py-2 text-xs font-medium border-b bg-black/5 dark:bg-white/10">Core-Baum</div>
            <div class="p-2 max-h-[380px] overflow-auto text-sm">
              <div v-if="!core.ready" class="text-xs opacity-60">lädt…</div>
              <template v-else>
                <div class="font-mono text-[11px] opacity-60 mb-1">{{ CORE_ROOT_LABEL }}</div>
                <div v-for="row in core.flat" :key="row.key"
                     class="px-1 py-1 rounded hover:bg-black/5 dark:hover:bg-white/10 cursor-default flex items-center"
                     :class="core.sel===row.path ? 'bg-emerald-50 dark:bg-emerald-900/20' : ''"
                     @click="core.sel = row.path">
                  <div :style="{marginLeft: `${row.depth*14}px`}" class="shrink-0"></div>
                  <button v-if="row.isDir" class="w-5 h-5 mr-1 text-slate-600 inline-flex items-center justify-center"
                          @click.stop="toggleCore(row.path)">
                    <svg viewBox="0 0 24 24" class="w-4 h-4" :class="core.exp.has(row.path)?'rotate-90':''">
                      <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.5"/>
                    </svg>
                  </button>
                  <div v-else class="w-5 h-5 mr-1"></div>
                  <svg v-if="row.isDir" viewBox="0 0 24 24" class="w-4 h-4 text-amber-600 shrink-0"><path d="M3 6h6l2 2h10v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6z" fill="currentColor"/></svg>
                  <svg v-else viewBox="0 0 24 24" class="w-4 h-4 text-slate-600 shrink-0"><path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="currentColor"/></svg>
                  <span class="ml-2 truncate">{{ row.name }}</span>
                </div>
              </template>
            </div>
          </div>

          <!-- Auswahl -->
          <div class="rounded-xl border overflow-hidden">
            <div class="px-3 py-2 text-xs font-medium border-b bg-black/5 dark:bg-white/10">Auswahl</div>
            <div class="p-3 text-xs space-y-3">
              <div>Gewählt: <span class="font-mono break-all">{{ core.sel || '—' }}</span></div>
              <div class="opacity-60">Ersetzt den Ziel <b>Ordner oder die Datei</b> durch den gewählten Core-Eintrag. Alt wird nach <span class="font-mono">.quarantine/…</span> verschoben.</div>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-2">
          <button class="px-3 py-1.5 rounded border" @click="replaceDlg.open=false">Abbrechen</button>
          <button class="px-3 py-1.5 rounded bg-black text-white"
                  :disabled="!core.sel"
                  @click="performReplaceSimple">Ersetzen</button>
        </div>
      </div>
    </div>
</template>

<script setup>
import axios from "axios"
import { onMounted, onUnmounted, ref, computed, watch } from "vue"
import { useRoute, RouterLink } from "vue-router"

const busy = ref({
  connect:false, diagnose:false, fixPerms:false, chmod:false, list:false
})
const busyAny = computed(()=> Object.values(busy.value).some(Boolean))
let logTimer = null
function startLogPolling(){ if(logTimer) return; logTimer = setInterval(fetchOpsLog, 2500) }
function stopLogPolling(){ if(logTimer){ clearInterval(logTimer); logTimer=null } }
watch(busyAny,(v)=> v ? startLogPolling() : stopLogPolling())

const route = useRoute()
const tid = Number(route.params.id || route.query.id || 0)
const api = axios.create({ baseURL: "/api", headers: { "Content-Type": "application/json" } })

/* Ticket */
function getStored(){ try { return JSON.parse(sessionStorage.getItem("sf_last_ticket")||"null") } catch { return null } }
const ticket = ref((history.state && history.state.ticket) || getStored() || null)
async function fetchTicket(){ try{ const {data}=await api.get(`/wp/tickets/${tid}`); ticket.value={...(ticket.value||{}),...(data||{})}; sessionStorage.setItem("sf_last_ticket", JSON.stringify(ticket.value)) }catch{} }
const ticketName=computed(()=>ticket.value?.name||"—")
const ticketEmail=computed(()=>ticket.value?.email||"—")
const ticketDomain=computed(()=>{const d=ticket.value?.domain; return d? (/^https?:\/\//i.test(d)?d:`http://${d}`):""})
const ticketStatus=computed(()=>ticket.value?.status||"—")
const ticketPrio=computed(()=>ticket.value?.prio||"—")

/* UI + Workflow */
const ui = ref({ tab: 'cache', msg: '', msgType: 'ok' })
const run = ref({ root:'idle', cache: 'idle', diag: 'idle' })
function stepClass(k){ return run.value[k]==='ok'?'text-emerald-700': run.value[k]==='busy'?'text-amber-700':'opacity-60' }

/* SFTP + Session */
const conn = ref({host:"",user:"",password:"",port:22})
const showPw=ref(false)
const root=ref("/")
const rootSet = computed(()=> !!root.value)
const sid=ref("")
const sessionId=ref(null)
const sftpState=ref("idle")
const sftpLabel=computed(()=>sftpState.value==="ok"?"verbunden":sftpState.value==="busy"?"verbinde…":sftpState.value==="fail"?"fehlgeschlagen":"nicht verbunden")
const formErr=ref("")
function prefillConn(){ const d=ticket.value||{}; conn.value.host=d.ftp_host||d.ftp_server||d.zugang_ftp_host||""; conn.value.user=d.ftp_user||d.zugang_ftp_user||""; conn.value.password=d.ftp_pass||d.zugang_ftp_pass||""; conn.value.port=Number(d.ftp_port||22); root.value=d.webroot||d.access?.webroot||"/" }

async function connectAndStart(){
  if(!conn.value.host || !conn.value.user || !conn.value.password){ formErr.value="Host, User und Passwort sind erforderlich."; return }
  try{
    sftpState.value="busy"
    const r1=await api.post("/sftp/session",{host:conn.value.host,username:conn.value.user,password:conn.value.password||"",port:conn.value.port||22})
    sid.value=r1.data.sid
    const r2=await api.post("/repair/session",{ticket_id:tid,sid:sid.value,root:root.value||"/"})
    sessionId.value=r2.data.session_id
    sftpState.value="ok"
    await gotoLeft(root.value||"/")
  }catch(e){
    sftpState.value="fail"; formErr.value=e?.response?.data?.error||e?.message||"Verbindung fehlgeschlagen."
  }
}
async function reconnect(){
  if(!sid.value){ await connectAndStart(); return }
  try{
    const r2=await api.post("/repair/session",{ticket_id:tid,sid:sid.value,root:root.value||"/"})
    sessionId.value=r2.data.session_id
    await gotoLeft(root.value||"/")
  }catch{ await connectAndStart() }
}

/* Remote-Tree */
const nodes = ref({})
const expanded = ref(new Set())
const leftPathInput = ref("/")
const selected = ref(null)
const menuOpen = ref('')

function selectRow(row){ selected.value=row }
function isSelected(row){ return selected?.value?.path===row.path }
function toggleMenu(key){ menuOpen.value = (menuOpen.value===key ? '' : key) }
function closeMenu(){ menuOpen.value='' }

const flatTree = computed(()=>{
  const out=[]
  function walk(p, depth){
    const list = nodes.value[p] || []
    for(const n of list){
      const isDir = n.type === "dir"
      const rowPath = n.path || joinPath(p, n.name)
      out.push({ key: rowPath, name: n.name, path: rowPath, isDir, size: n.size, mode: n.mode, mtime: n.mtime, depth })
      if(isDir && expanded.value.has(rowPath)) walk(rowPath, depth+1)
    }
  }
  walk(root.value || "/", 0)
  return out
})

const joinPath=(a,b)=> (a && a!=="/"? `${a.replace(/\/$/,"")}/${b}`:`/${b}`).replace("//","/")

async function gotoLeft(path){
  if(!sessionId.value){ formErr.value="Repair-Session fehlt"; return }
  busy.value.list = true
  try{
    const {data}=await api.get("/repair/sftp/list",{params:{session_id:sessionId.value,path}})
    nodes.value[path] = (data.items||[]).map(it => ({...it, path: it.full_path || joinPath(path, it.name)}))
    expanded.value.add(path)
    leftPathInput.value = path
  } finally {
    busy.value.list = false
  }
}

async function reloadLeft(){ if(sessionId.value) await gotoLeft(root.value||"/") }
async function toggle(path){
  if (expanded.value.has(path)) { expanded.value.delete(path); return }
  nodes.value[path] = []
  await gotoLeft(path)
  expanded.value.add(path)
}
function goUp(){
  if (root.value==='/' ) return
  const parent = root.value.replace(/\/[^/]+\/?$/,'') || '/'
  root.value = parent
  run.value.root='ok'
  gotoLeft(root.value)
}

/* Root setzen */
async function setRootFromSelection(path){
  if(!path) return
  root.value = path
  run.value.root='ok'
  await gotoLeft(root.value)
}
async function applyRootFromSelection(){
  if(!selected?.value?.isDir){ ui.value={...ui.value,msg:'Bitte Ordner wählen', msgType:'err'}; return }
  await setRootFromSelection(selected.value.path)
}

/* Viewer */
const viewPath=ref("")
const viewText=ref("")
const viewLoading=ref(false)
const binary=ref(false)
const truncated=ref(false)
const sizeHint=ref(0)
const mtime=ref(null)
const fileFindings = ref([])

async function openFile(path){
  if(!sid.value){ ui.value={...ui.value,msg:'SFTP nicht verbunden.',msgType:'err'}; return }
  viewLoading.value=true; viewPath.value=path
  try{
    const {data}=await api.get("/repair/file/view", {
      params:{ sftp_sid: sid.value, session_id: sessionId.value, path, max_bytes: 400000 }
    })
    binary.value=!!data.binary
    truncated.value=!!data.truncated
    sizeHint.value=data.size_hint||0
    mtime.value=(data.mtime??null)
    viewText.value=data.binary ? "" : (data.text || "")
  }catch(e){
    ui.value={...ui.value,msg:(e?.response?.data?.error||e.message),msgType:'err'}
    // Felder zurücksetzen, damit „leer“ nicht wie Erfolg aussieht
    binary.value=false; truncated.value=false; sizeHint.value=0; mtime.value=null; viewText.value=""
  }finally{
    viewLoading.value=false
  }
} 
/*
async function testDomain(){
  try{
    const dom = (ticket.value?.domain || "").trim()
    if(!dom){ ui.value={...ui.value,msg:'Keine Domain im Ticket.',msgType:'err'}; return }
    const {data} = await api.get("/repair/http_check",{ params:{ domain: dom } })
    const parts = data.results.map(r=>{
      const tls = r.tls ? ` · TLS: ${r.tls.issuer||''} → ${r.tls.subject||''}` : ''
      return `${r.scheme.toUpperCase()} ${r.status||r.error||'—'} (${r.server||'?'}, ${r.content_type||''}, ${r.rt_ms||'?'}ms, redirects:${r.redirects||0})${tls}`
    })
    ui.value = {...ui.value, msg:`${data.domain} [${data.ip||'—'}] · ${parts.join(' · ')}`, msgType:'ok'}
  }catch(e){
    ui.value={...ui.value,msg:(e?.response?.data?.error||e.message),msgType:'err'}
  }
}*/


async function reloadView(){ if(viewPath.value) await openFile(viewPath.value) }

/* Datei/Ordner Aktionen */
async function renamePath(row){
  const nv = prompt("Neuer Name für:\n"+row.path, row.name)
  if(!nv || nv===row.name) return
  await api.post("/repair/fs/rename",{ session_id: sessionId.value, path: row.path, new_name: nv })
  await reloadLeft()
}
async function chmodPath(row){
  const nv = prompt("Neue Rechte (z. B. 755 oder 644):", fmtPerm(row.mode)||"755")
  if(!nv) return
  await api.post("/repair/fs/chmod",{ sftp_sid: sid.value, path: row.path, mode: nv })
  await reloadLeft()
}
async function deletePath(row){
  if(!confirm("Wirklich löschen?\n"+row.path)) return
  await api.post("/repair/fs/delete",{ session_id: sessionId.value, path: row.path })
  await reloadLeft()
}

/* Core-Index optional */
const cacheIndex = ref(null)
async function loadCacheIndex(){
  run.value.cache='busy'; ui.value.msg=''
  try{
    const {data} = await api.get("/cms-core/index")
    cacheIndex.value = data
    run.value.cache='ok'; ui.value={...ui.value,msg:'Core-Index geladen.',msgType:'ok'}; ui.value.tab='cache'
  }catch(e){
    run.value.cache='err'; ui.value={...ui.value,msg:(e?.response?.data?.error || e.message),msgType:'err'}
  }
}

/* Diagnose + Log */
const diagnose = ref(null)
const opsLog = ref([])
const detectedCMS = ref("")
async function runDiagnose(){
  if(!sid.value){ ui.value={...ui.value,msg:'SFTP nicht verbunden.',msgType:'err'}; return }
  busy.value.diagnose = true; run.value.diag='busy'; ui.value.msg=''
  try{
    const {data} = await api.post("/repair/diagnose", { sftp_sid: sid.value, session_id: sessionId.value, root: root.value || "/", cms_hint: detectedCMS.value || null })
    diagnose.value = data
    run.value.diag='ok'
    ui.value={...ui.value,msg:'Diagnose abgeschlossen.',msgType:'ok'}; ui.value.tab='diag'
  }catch(e){
    run.value.diag='err'
    const code = e?.response?.data?.error
    if(code === "sftp_session_expired"){ sftpState.value='fail'; ui.value={...ui.value,msg:'SFTP-Session abgelaufen. Bitte neu verbinden.',msgType:'err'} }
    else { ui.value={...ui.value,msg:(e?.response?.data?.error || e.message),msgType:'err'} }
  } finally {
    busy.value.diagnose = false
    fetchOpsLog()
  }
}

async function fetchOpsLog(){
  try{
    const {data} = await api.get("/repair/opslog", { params:{ session_id: sessionId.value }})
    opsLog.value = data.items || []
  }catch{}
}
async function detectCMS(){
  if(!sid.value) return
  try{
    // WICHTIG: sftp_sid senden
    const {data} = await api.get("/repair/detect_cms", { params:{ sftp_sid: sid.value, session_id: sessionId.value, root: root.value||"/" } })
    detectedCMS.value = data?.cms || ""
    ui.value={...ui.value,msg:`CMS: ${detectedCMS.value || 'unbekannt'}`,msgType:'ok'}
  }catch(e){
    ui.value={...ui.value,msg:(e?.response?.data?.error || e.message),msgType:'err'}
  }
}
function updateCurrentLine() {
  if (editor.value) currentLine.value = caretLine(editor.value)
}
function jumpToLine(n){
  if(!editor.value) return
  const lines = (viewText.value || '').split('\n')
  let pos = 0
  for(let i=0;i<Math.max(0,n-1) && i<lines.length;i++) pos += lines[i].length+1
  editor.value.selectionStart = editor.value.selectionEnd = pos
  editor.value.scrollTop = Math.max(0, (n-5) * 20)
  currentLine.value = n
}

/* Domain-Check */
async function testDomain(){
  try{
    const dom = (ticket.value?.domain || "").trim()
    if(!dom){ ui.value={...ui.value,msg:'Keine Domain im Ticket.',msgType:'err'}; return }
    const {data} = await api.get("/repair/http_check",{ params:{ domain: dom } })
    const r = data.results || []
    const http  = r.find(x=>x.scheme==='http')
    const https = r.find(x=>x.scheme==='https')
    ui.value = {...ui.value, msg:`HTTP ${http?.status||http?.error||'—'} · HTTPS ${https?.status||https?.error||'—'} · IP ${data.ip||'—'}`, msgType:'ok'}
  }catch(e){
    ui.value={...ui.value,msg:(e?.response?.data?.error||e.message),msgType:'err'}
  }
}
async function fixPerms(){
  if(!sid.value){ ui.value={...ui.value,msg:'SFTP nicht verbunden.',msgType:'err'}; return }
  busy.value.fixPerms = true
  ui.value = {...ui.value, msg:'Rechte werden gesetzt…', msgType:'ok'}
  try{
    const {data} = await api.post('/repair/fs/fix-perms', {
      sftp_sid: sid.value,
      root: root.value || '/',
      dry_run: false
    })
    const errc = (data.errors||[]).length
    ui.value = {...ui.value, msg:`Rechte repariert: geändert ${data.changed}, geprüft ${data.checked}, Fehler ${errc}`, msgType: errc? 'err':'ok' }
    await reloadLeft()
  }catch(e){
    ui.value={...ui.value,msg:(e?.response?.data?.error || e.message),msgType:'err'}
  } finally {
    busy.value.fixPerms = false
    fetchOpsLog()
  }
}


/* Heuristische Datei-Prüfung im Frontend */
function scanCurrentFile(){
  const txt = viewText.value || ""
  const out = []
  if(!txt){ fileFindings.value = out; return }

  const lines = txt.split(/\r?\n/)

  // riskante Funktionsaufrufe
  const badCall = /(base64_decode|gzinflate|eval|assert|system|shell_exec|passthru|exec|popen|proc_open)\s*\(/
  lines.forEach((l,i)=>{ if(badCall.test(l)) out.push({code:"SUSP_CALL",title:`Auffälliger Aufruf in Zeile ${i+1}: ${l.trim().slice(0,80)}`,severity:"high"}) })

  // extrem lange Zeilen
  const li = lines.findIndex(l=>l.length>4000)
  if(li>=0) out.push({code:"LONG_LINE",title:`Sehr lange Zeile ${li+1}`,severity:"med"})

  // potenzielle Credentials
  if(/(DB_HOST|DB_USER|DB_PASSWORD|mysqli_connect|PDO\s*\()/.test(txt))
    out.push({code:"CRED_HINT",title:"Datenbankzugang im File gefunden",severity:"low"})

  // unsichere Superglobals
  const unsaf = /\$_(GET|POST|REQUEST|COOKIE)\s*\[\s*['"][^'"]+['"]\s*]\s*;/
  if(unsaf.test(txt))
    out.push({code:"INPUT_NO_VALIDATION",title:"Eingaben ohne Prüfung genutzt",severity:"med"})

  // direkte SQL-Strings
  if(/SELECT\s+.+\s+FROM\s+/i.test(txt) && !/prepare\s*\(/i.test(txt))
    out.push({code:"SQL_RAW",title:"SQL ohne Prepared Statements",severity:"med"})

  // Null-Bytes
  if(/\x00/.test(txt)) out.push({code:"BINARY_NULLS",title:"Binär-Nullbytes im Text",severity:"med"})

  fileFindings.value = out
}


/* Replace-Dialog (Core) */
const replaceDlg = ref({ open:false, targetPath:'' })
const CORE_ROOT_LABEL = "/var/www/sitefixer/cms-core"
const core = ref({ ready:false, exp:new Set(), nodes:{}, flat:[], sel:"" })

function openReplaceDialog(row){
  replaceDlg.value = { open:true, targetPath: row.path }
  core.value = { ready:false, exp:new Set(), nodes:{}, flat:[], sel:"" }
  loadCoreLevel("")
}
function mapCoreFlat(){
  const out=[]
  function walk(rel, depth){
    const list = core.value.nodes[rel] || []
    for(const n of list){
      const isDir = n.type === "dir"
      out.push({ key:n.path, name:n.name, path:n.path, isDir, depth })
      if(isDir && core.value.exp.has(n.path)) walk(n.path, depth+1)
    }
  }
  walk("",0)
  core.value.flat = out
}
function joinRel(base, name){
  if(!base) return name
  return `${base.replace(/\/$/,'')}/${name}`
}
async function loadCoreLevel(rel=""){
  try{
    const {data} = await api.get("/cms-core/tree", { params:{ path: rel } })
    const items = (data.items||[]).map(it => ({ ...it, path: joinRel(rel, it.name) }))
    core.value.nodes[rel] = items.sort((a,b)=> (a.type!==b.type) ? (a.type==='dir'?-1:1) : a.name.localeCompare(b.name))
    core.value.exp.add(rel)
    core.value.ready = true
    mapCoreFlat()
  }catch(e){
    ui.value={...ui.value,msg:(e?.response?.data?.error || e.message),msgType:'err'}
  }
}

async function saveView(){
  if(!viewPath.value) return
  try{
    await api.post("/repair/file/save", {
      sftp_sid: sid.value,
      path: viewPath.value,
      text: viewText.value
    })
    ui.value = {...ui.value, msg:"Gespeichert.", msgType:"ok"}
  }catch(e){
    const er = e?.response?.data
    ui.value = {...ui.value, msg: `Speichern fehlgeschlagen: ${er?.error || e.message}`, msgType:"err"}
  }
}

async function toggleCore(rel){
  if(core.value.exp.has(rel)){ core.value.exp.delete(rel); mapCoreFlat(); return }
  if(!core.value.nodes[rel]) await loadCoreLevel(rel)
  else { core.value.exp.add(rel); mapCoreFlat() }
}
async function performReplaceSimple () {
  if (!core.value.sel) return
  if (!sid.value) { ui.value={...ui.value,msg:'SFTP nicht verbunden.',msgType:'err'}; return }
  const srcRel = core.value.sel.replace(/^\/+/, '')
  const payload = { sftp_sid: sid.value, target_path: replaceDlg.value.targetPath, source_path: srcRel }
  try {
    await api.post('/repair/replace-from-core', payload)
    replaceDlg.value.open = false
    await reloadLeft()
    ui.value = {...ui.value, msg:'Ersetzt. Alt in .quarantine verschoben.', msgType:'ok'}
  } catch (e) {
    ui.value = {...ui.value, msg:(e?.response?.data?.error || e.message), msgType:'err'}
  }
}
const editor = ref(null), gutter = ref(null)
const currentLine = ref(1)
const lineCount = computed(() => (viewText.value.match(/\n/g) || []).length + 1)
const editorHeight = 420

function caretLine(el) {
  const pos = el.selectionStart ?? 0
  const s = (el.value || '').slice(0, pos)
  return (s.match(/\n/g)?.length || 0) + 1
}
/*
function updateCurrentLine() {
  if (editor.value) currentLine.value = caretLine(editor.value)
}*/


function syncScroll() {
  if (!editor.value || !gutter.value) return
  gutter.value.scrollTop = editor.value.scrollTop
}

/* Utils */
function fmtSize(n){ if(!n||n<0) return ""; const u=["B","KB","MB","GB"]; let i=0; let x=n; while(x>=1024&&i<u.length-1){x/=1024;i++} return `${x.toFixed(i?1:0)} ${u[i]}` }
function fmtPerm(m){ if(!m) return ""; const s=String(m); const oct = s.startsWith("0o")? s.slice(2): s; return oct.padStart(3,"0") }
function fmtTime(t){ if(!t) return ""; try{ return new Date(t*1000).toLocaleString() }catch{ return String(t) } }

/* init */
let clickHandler=null
onMounted(async ()=>{
  if(ticket.value) prefillConn()
  await fetchTicket(); prefillConn()
  clickHandler = ()=> (menuOpen.value='')
  window.addEventListener('click', clickHandler)
  if(sessionId.value){ await gotoLeft(root.value||"/") }
  fetchOpsLog()
})
onUnmounted(()=>{ if(clickHandler) window.removeEventListener('click', clickHandler) })
</script>

<style scoped>
.grid-cols-file{
  display:grid;
  grid-template-columns: minmax(0,1fr) 110px 84px 170px 72px;
  column-gap: .25rem;
}
.editor-wrap { height: 420px; }
.editor-gutter{
  position:absolute; inset:0 auto 0 0; width:56px;
  overflow:auto; border:1px solid var(--tw-color-border, rgba(0,0,0,.1));
  background: rgba(0,0,0,.03);
  pointer-events:none;           /* Klicks gehen an das Textarea */
  border-radius: .25rem;
}
.editor-textarea{
  position:absolute; inset:0 0 0 0;
  resize:none; overflow:auto; border:1px solid var(--tw-color-border, rgba(0,0,0,.1));
  background: transparent; padding: .5rem .5rem .5rem 64px; /* Platz für Gutter */
  border-radius: .25rem;
  white-space: pre; tab-size: 2;
}
@keyframes spin{to{transform:rotate(360deg)}}
.animate-spin{animation:spin 1s linear infinite}

</style>
