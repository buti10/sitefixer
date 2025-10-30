<template>
  <div class="rounded-xl border bg-white dark:bg-[#0f1424] p-4">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2"><span>📂</span><h3 class="font-semibold">SFTP Explorer</h3></div>
      <span class="text-xs opacity-70">{{ sidRef ? 'verbunden' : 'nicht verbunden' }}</span>
    </div>

    <div class="grid sm:grid-cols-4 gap-2 mb-3 text-sm">
      <input class="rounded border px-3 py-2 bg-transparent" :value="host" disabled placeholder="Host" />
      <input class="rounded border px-3 py-2 bg-transparent" :value="username" disabled placeholder="User" />
      <input class="rounded border px-3 py-2 bg-transparent" :value="passwordMasked" disabled placeholder="Passwort" />
      <div class="flex gap-2">
        <button class="px-3 py-2 rounded border hover:bg-black/5 w-full sm:w-auto" @click="connect" :disabled="!!sidRef || connecting">
          {{ connecting ? 'Verbinde…' : 'Verbinden' }}
        </button>
        <button class="px-3 py-2 rounded border hover:bg-black/5 w-full sm:w-auto" @click="disconnect" :disabled="!sidRef">
          Trennen
        </button>
      </div>
    </div>

    <div class="border rounded-lg">
      <div v-if="error" class="p-3 text-sm text-red-700 bg-red-50">{{ error }}</div>
      <div v-else-if="!sidRef" class="p-3 text-sm opacity-70">Bitte verbinden.</div>
      <div v-else class="p-2 h-100 overflow-auto">
        <ul class="text-sm">
          <SftpTreeNode
            :sid="sidRef"
            :path="rootNode.path"
            :name="rootNode.name"
            type="dir"
            :level="0"
            :load-children="loadChildren"
            :children-map="childrenMap"
            :expanded-set="expanded"
            :selected-path="selectedPath"
            @choose="onChooseFromNode"
          />
        </ul>
      </div>
    </div>

    <div class="flex items-center justify-between mt-3 text-sm">
      <div class="opacity-70">
        Pfad: <span class="font-mono">{{ selectedPath || currentPath }}</span>
      </div>
      <div class="flex gap-2">
        <button class="px-3 py-2 border rounded" @click="goUp" :disabled="!sidRef || currentPath==='/'">▲ Ebene hoch</button>
        <button class="px-3 py-2 bg-green-600 text-white rounded" @click="selectHere" :disabled="!sidRef">
          Diesen Ordner als Root verwenden
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue"
import SftpTreeNode from "./SftpTreeNode.vue"
import { sftpCreateSession, sftpList, sftpClose, type SftpEntry } from "@/api"

const props = defineProps<{
  ticketId: number
  initialPath?: string
  host?: string
  username?: string
  password?: string
  port?: number
  autoConnect?: boolean
  sid?: string
}>()

// v-model:path  (Parent kontrolliert den Pfad)
const pathModel = defineModel<string>('path', { default: '/' })

const emit = defineEmits<{
  (e:"connected", sid:string): void
}>()

// interne States
const sidRef = ref<string>(props.sid || "")
watch(() => props.sid, v => { sidRef.value = v || "" })

const connecting = ref(false)
const error = ref<string|null>(null)
const currentPath = ref<string>(props.initialPath || pathModel.value || "/")
watch(() => props.initialPath, p => { if (!sidRef.value && p) currentPath.value = normalize(p) })
watch(pathModel, p => { if (p) currentPath.value = normalize(p) }, { immediate:true })

const childrenMap = ref<Record<string, SftpEntry[]>>({})
const expanded = ref<Set<string>>(new Set())
const selectedPath = ref<string>("")
const rootNode = computed(() => ({ name:"/", path: "/" }))

const host = computed(() => props.host ?? "")
const username = computed(() => props.username ?? "")
const passwordMasked = computed(() => (props.password ? "••••••••" : "—"))

function normalize(p:string){ return ("/"+(p||"/")).replace(/\/+/g,"/") }

async function connect() {
  if (sidRef.value) return
  if (!host.value || !username.value || !props.password) { error.value = "Zugangsdaten unvollständig"; return }
  error.value = null; connecting.value = true
  try {
    sidRef.value = await sftpCreateSession({
      ticket_id: props.ticketId,
      host: host.value,
      username: username.value,
      password: props.password,
      port: props.port,
      root: pathModel.value || "/",
    })
    // Wichtig: Pfad NICHT auf "/" zurücksetzen → mit aktuellem pathModel laden
    await loadChildren(pathModel.value || "/", true)
    emit("connected", sidRef.value)
  } catch (e:any) {
    error.value = e?.response?.data?.message || e?.message || "SFTP Verbindung fehlgeschlagen"
  } finally {
    connecting.value = false
  }
}

async function disconnect() {
  if (!sidRef.value) return
  try { await sftpClose(sidRef.value) } catch {}
  sidRef.value = ""
  childrenMap.value = {}
  expanded.value.clear()
  emit("connected", "")
}

// Tree/Navi
async function loadChildren(path:string, expand=false){
  if (!sidRef.value) return
  const p = normalize(path)
  const list = await sftpList(sidRef.value, p)
  childrenMap.value[p] = list
    .map(x => ({ ...x, path: normalize(x.path || (p==='/' ? `/${x.name}` : `${p}/${x.name}`)) }))
    .sort((a,b)=> (a.type===b.type ? a.name.localeCompare(b.name) : a.type==='dir' ? -1 : 1))
  if (expand) expanded.value.add(p)
  currentPath.value = p
}

function onChooseFromNode(path:string){ selectedPath.value = path }
function selectHere(){
  const p = normalize(selectedPath.value || currentPath.value || "/")
  // Parent aktualisieren
  pathModel.value = p
  currentPath.value = p
}

function goUp(){
  if (currentPath.value === "/") return
  const up = currentPath.value.replace(/\/*$/,"").replace(/\/[^/]*$/,"") || "/"
  // Parent aktualisieren
  pathModel.value = up
  currentPath.value = up
}

onMounted(async () => {
  if (props.autoConnect && host.value && username.value && props.password) {
    await connect()
  }
})
</script>
