<!-- frontend/src/pages/Settings.vue -->
<template>
  <div class="space-y-6">
    <h2 class="text-lg font-semibold">Einstellungen</h2>

    <!-- System Settings (dein bestehender Block) -->
    <UiCard>
      <div class="grid md:grid-cols-2 gap-4">
        <UiInput label="SITE_NAME" v-model="s.SITE_NAME" />
        <UiInput label="SUPPORT_EMAIL" v-model="s.SUPPORT_EMAIL" />
      </div>
      <div class="mt-4 flex gap-2">
        <UiButton @click="save">Speichern</UiButton>
        <span v-if="saved" class="text-xs opacity-70 self-center">gespeichert</span>
      </div>
    </UiCard>
        <!-- Mail-Vorlage: Angebot & Zahlungslink -->
    <UiCard>
      <h3 class="font-medium mb-3">Mail-Vorlage: Angebot & Zahlungslink</h3>
      <p class="text-xs opacity-70 mb-4">
        Diese Vorlage wird verwendet, wenn du aus dem Ticket heraus den Zahlungslink verschickst.
        Du kannst Platzhalter verwenden:
        <code class="font-mono bg-black/5 dark:bg-white/10 px-1 rounded">
          {{ '{ticket_id}' }}, {{ '{customer_name}' }}, {{ '{amount}' }}, {{ '{payment_link}' }}
        </code>
      </p>

      <div class="space-y-4">
        <!-- Betreff -->
        <UiInput
          label="Betreff"
          v-model="s.OFFER_MAIL_SUBJECT"
          placeholder="Ihr Sitefixer-Angebot zu Ticket #{ticket_id}"
        />

        <!-- Mail-Text -->
        <div>
          <label class="text-xs font-medium block mb-1">Mail-Text</label>
          <textarea
            v-model="s.OFFER_MAIL_BODY"
            rows="6"
            class="w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm font-mono"
            placeholder="Hallo {customer_name},&#10;&#10;vielen Dank für Ihre Anfrage..."
          ></textarea>
          <p class="mt-1 text-[11px] opacity-60">
            Verwende <code class="font-mono bg-black/5 dark:bg-white/10 px-1 rounded">{payment_link}</code>, um den Link einzufügen.
          </p>
        </div>

        <!-- Signatur -->
        <div>
          <label class="text-xs font-medium block mb-1">Signatur</label>
          <textarea
            v-model="s.OFFER_MAIL_SIGNATURE"
            rows="3"
            class="w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm font-mono"
            placeholder="Sitefixer Support-Team&#10;support@sitefixer.de"
          ></textarea>
        </div>

        <div class="flex gap-2">
          <UiButton @click="save">Speichern</UiButton>
          <span v-if="saved" class="text-xs opacity-70 self-center">gespeichert</span>
        </div>
      </div>
    </UiCard>

    <!-- Core-Cache (CMS-Versionen) -->
    <UiCard>
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-medium">Core-Cache (CMS-Versionen)</h3>
        <div class="text-xs opacity-70 font-mono">
          Root: {{ rootLabel }}
        </div>
      </div>

      <div class="grid lg:grid-cols-3 gap-4">
        <!-- Explorer -->
        <div class="lg:col-span-1">
          <div class="flex items-center gap-2 mb-2">
            <UiButton size="sm" variant="secondary" @click="reload()">Neu laden</UiButton>
            <UiButton size="sm" variant="secondary" @click="promptMkdir()">Neuer Ordner</UiButton>
            <UiButton size="sm" variant="secondary" :disabled="!selected" @click="promptRename()">Umbenennen</UiButton>
            <UiButton size="sm" variant="destructive" :disabled="!selected" @click="remove()">Löschen</UiButton>
          </div>

          <div class="h-80 overflow-auto rounded border border-black/5 dark:border-white/10 p-2 bg-black/5 dark:bg-white/5">
            <ExplorerNode
              v-if="tree"
              :node="tree"
              @load="loadChildren"
              @select="selectNode"
            />
            <div v-else class="text-sm opacity-70">Lade…</div>
          </div>
        </div>

        <!-- Details & Upload -->
        <div class="lg:col-span-2">
          <div class="rounded border border-black/5 dark:border-white/10 p-3 mb-4">
            <div class="text-sm">
              <div class="font-medium mb-1">Auswahl</div>
              <div>
                Pfad:
                <span class="font-mono">{{ selected?.path || '—' }}</span>
              </div>
              <div>
                Typ:
                <span class="uppercase">{{ selected?.type || '—' }}</span>
              </div>
            </div>
          </div>

          <div class="rounded border border-black/5 dark:border-white/10 p-3">
            <div class="font-medium mb-2">Upload</div>
            <div class="text-xs opacity-70 mb-2">
              Zielordner: <span class="font-mono">{{ uploadTarget || '/' }}</span>
            </div>

            <div class="flex flex-col sm:flex-row gap-3 items-start sm:items-end">
              <input type="file" multiple ref="fileInput" />
              <label class="inline-flex items-center gap-2 text-sm">
                <input type="checkbox" v-model="extractArchive" />
                Archive automatisch entpacken
              </label>
              <UiButton :disabled="uploading" @click="upload()">
                {{ uploading ? 'Lädt hoch…' : 'Hochladen' }}
              </UiButton>
            </div>

            <div v-if="lastMessage" class="text-xs mt-2" :class="lastMessageOk ? 'text-emerald-600' : 'text-red-600'">
              {{ lastMessage }}
            </div>
          </div>
        </div>
      </div>
    </UiCard>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineComponent, computed } from 'vue'
import axios from 'axios'
import api from '../api'
import UiCard from '../components/UiCard.vue'
import UiButton from '../components/UiButton.vue'
import UiInput from '../components/UiInput.vue'

/* ---------------------------------------------------------
 * 1) Deine bestehenden Settings
 * ------------------------------------------------------- */
const s = ref<any>({})
const saved = ref(false)

/* ---------------------------------------------------------
 * 2) Core-Cache Explorer – API Wrapper
 *    -> Passe Pfade an dein Backend an
 * ------------------------------------------------------- */
const coreApi = {
  // path = '' (Root), 'Hallo', 'wordpress/6.6'
  tree:   (path = '') =>
    api.get('/cms-core/tree', { params: { path } }).then(r => r.data),

  mkdir:  (parentPath: string, name: string) =>
    api.post('/cms-core/mkdir', { path: parentPath || '', name }),

  rename: (srcPath: string, newName: string) => {
    const base = (srcPath || '').split('/').slice(0, -1).join('/')
    const dst  = (base ? base + '/' : '') + newName
    return api.post('/cms-core/rename', { src: srcPath, dst })
  },

  remove: (path: string) =>
    api.delete('/cms-core/rm', { params: { path } }),

  upload: (path: string, files: File[], extract: boolean) => {
    const fd = new FormData()
    fd.append('files', files[0])
    fd.append('path', path || '')
    fd.append('extract', extract ? '1' : '0')
    return api.post('/cms-core/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
}

async function loadSettings () {
  const { data } = await api.get('/settings')
  s.value = {
    SITE_NAME: '',
    SUPPORT_EMAIL: 'support@sitefixer.de',
    OFFER_MAIL_SUBJECT: 'Ihr Sitefixer-Angebot zu Ticket #{ticket_id}',
    OFFER_MAIL_BODY:
      'Hallo {customer_name},\n\n' +
      'vielen Dank für Ihre Anfrage.\n' +
      'Hier ist der Zahlungslink zu Ihrem Angebot über {amount} €:\n' +
      '{payment_link}\n\n' +
      'Mit freundlichen Grüßen,\n' +
      '{signature}',
    OFFER_MAIL_SIGNATURE: 'Sitefixer Support-Team\nsupport@sitefixer.de',
    ...(data || {})
  }
}


async function save () {
  saved.value = false
  await api.post('/settings', s.value)
  saved.value = true
}


/* ---------------------------------------------------------
 * 3) Explorer State / Logic
 * ------------------------------------------------------- */
type Node = { name: string; path: string; type: 'dir'|'file'; open?: boolean; loaded?: boolean; children?: Node[] }

const tree = ref<Node | null>(null)
const selected = ref<Node | null>(null)
const uploading = ref(false)
const extractArchive = ref(true)
const fileInput = ref<HTMLInputElement | null>(null)
const lastMessage = ref('')
const lastMessageOk = ref(true)

const rootLabel = '/cms-core'
const uploadTarget = computed(() => {
  const sel = selected.value
  if (!sel) return ''
  if (sel.type === 'dir') return sel.path || ''
  const p = (sel.path || '').split('/').slice(0, -1).join('/')
  return p
})

function mapItems(items: Array<{name:string; path:string; type:'dir'|'file'}> = []) {
  return items.map(it => ({
    name: it.name,
    path: it.path,  // jetzt z.B. "Hallo" oder "wordpress/6.6"
    type: it.type === 'dir' ? 'dir' : 'file',
    open: false,
    loaded: it.type !== 'dir',
    children: it.type === 'dir' ? [] : undefined
  }))
}

async function reload (path = '') {
  lastMessage.value = ''
  const data = await coreApi.tree(path)
  tree.value = {
    name: data.root || '/',
    path: '',          // Root hat immer path = '' (relativ)
    type: 'dir',
    open: true,
    loaded: true,
    children: mapItems(data.items || [])
  }
  selected.value = tree.value
}

async function loadChildren (n: Node) {
  if (n.type === 'file') return
  const data = await coreApi.tree(n.path || '')
  n.children = mapItems(data.items || [])
  n.loaded = true
  n.open = true
}


function selectNode (n: Node) {
  selected.value = n
}

async function promptMkdir () {
  const base = selected.value?.type === 'dir'
    ? (selected.value?.path || '/')
    : ((((selected.value?.path) || '').split('/').slice(0, -1).join('/')) || '/')
  const name = window.prompt('Neuer Ordner-Name:', '')
  if (!name) return
  await coreApi.mkdir(base, name)
  lastMessageOk.value = true
  lastMessage.value = `Ordner „${name}“ angelegt.`
  await reload(base)
}

async function promptRename () {
  if (!selected.value) return
  const newName = window.prompt('Neuer Name:', selected.value.name)
  if (!newName || newName === selected.value.name) return
  await coreApi.rename(selected.value.path, newName)
  lastMessageOk.value = true
  lastMessage.value = `„${selected.value.name}“ → „${newName}“`
  const base = ((((selected.value?.path) || '').split('/').slice(0, -1).join('/')) || '/')
  await reload(base)
}


async function remove () {
  if (!selected.value) return
  if (!window.confirm(`„${selected.value.name}“ wirklich löschen?`)) return
  await coreApi.remove(selected.value.path)
  lastMessageOk.value = true
  lastMessage.value = `„${selected.value.name}“ gelöscht.`
  const base = ((((selected.value?.path) || '').split('/').slice(0, -1).join('/')) || '/')
  await reload(base)
}

async function upload () {
  if (!fileInput.value || !fileInput.value.files || fileInput.value.files.length === 0) {
    lastMessageOk.value = false
    lastMessage.value = 'Bitte Datei(en) wählen.'
    return
  }
  try {
    uploading.value = true
    const files = Array.from(fileInput.value.files)
    const target = uploadTarget.value || '/'

    // Versuch #1: ?path=&extract= + Feld "file"
    try {
      await coreApi.upload(target, [files[0]], extractArchive.value)
    } catch (e1:any) {
      // Fallback Versuch #2: multipart: path, extract, files[]
      const fd = new FormData()
      fd.append('path', target)
      fd.append('extract', extractArchive.value ? '1' : '0')
      files.forEach(f => fd.append('files', f))
      await api.post('/cms-core/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    }

    lastMessageOk.value = true
    lastMessage.value = 'Upload abgeschlossen.'
    fileInput.value.value = ''
    await reload(target)
  } catch (e:any) {
    lastMessageOk.value = false
    lastMessage.value = e?.response?.data?.msg || e?.message || 'Upload fehlgeschlagen.'
  } finally {
    uploading.value = false
  }
}


/* ---------------------------------------------------------
 * 4) Lokale rekursive Explorer-Komponente
 * ------------------------------------------------------- */
import { defineComponent, h } from 'vue'

const ExplorerNode = defineComponent({
  name: 'ExplorerNode',
  props: { node: { type: Object, required: true } },
  emits: ['load','select'],
  setup(props, { emit }) {
    const toggle = () => {
      const n: any = props.node
      if (n.type === 'file') { emit('select', n); return }
      if (!n.loaded) emit('load', n)
      else n.open = !n.open
      emit('select', n)
    }
    const choose = () => emit('select', props.node as any)

    return () => {
      const n: any = props.node
      return h('div', { class: 'pl-2 text-gray-900 dark:text-gray-200' }, [
        h('div', { class: 'flex items-center gap-2 py-0.5' }, [
          n.type === 'dir'
            ? h('button',
                { class: 'text-[11px] leading-none px-1 rounded border border-black/20 dark:border-white/25', onClick: toggle },
                n.open ? '–' : '+')
            : null,
          h('span',
            {
              class: 'font-mono text-xs cursor-pointer ' + (n.type === 'dir' ? 'font-semibold' : ''),
              onClick: choose
            },
            n.name)
        ]),
        n.open
          ? (n.children && n.children.length
              ? h('div', { class: 'pl-4' },
                  n.children.map((c: any) =>
                    h(ExplorerNode, {
                      node: c,
                      onLoad: (x: any) => emit('load', x),
                      onSelect: (x: any) => emit('select', x),
                      key: c.path
                    })))
              : (n.type === 'dir' && n.loaded
                  ? h('div', { class: 'pl-6 text-[11px] opacity-60' }, 'leer')
                  : null))
          : null
      ])
    }
  }
})


/* ---------------------------------------------------------
 * 5) Init
 * ------------------------------------------------------- */
onMounted(async () => {
  await loadSettings()
  await reload('')   // Core-Cache laden (Root)
})
</script>
