<template>
  <div class="space-y-3">
    <div v-if="!items?.length" class="text-sm opacity-70">Noch keine Findings…</div>

    <div v-for="(group, path) in grouped" :key="path" class="border rounded-lg">
      <!-- Kopfzeile pro Datei -->
      <div class="flex items-center justify-between px-3 py-2 bg-black/5 dark:bg-white/10 rounded-t-lg">
        <div class="flex items-center gap-2 min-w-0">
          <span class="text-xs px-2 py-0.5 rounded bg-slate-200/70 dark:bg-slate-700/50 font-mono">{{ group.length }}</span>
          <span class="font-mono text-xs break-all truncate">{{ path }}</span>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <!-- Severity der Gruppe (höchste) -->
          <span
            class="text-[10px] uppercase tracking-wide px-2 py-1 rounded"
            :class="severityClass(groupSeverity(group))">
            {{ groupSeverity(group) === 'high' ? 'Gefährlich' : 'Verdächtig' }}
          </span>

          <button class="text-xs underline" @click="copy(path)">kopieren</button>
          <button class="text-xs underline" @click="toggle(path)">
            {{ isOpen(path) ? 'einklappen' : 'ausklappen' }}
          </button>
        </div>
      </div>

      <!-- Findings der Datei -->
      <transition name="fade">
        <div v-show="isOpen(path)" class="divide-y">
          <div v-for="f in group" :key="f.id" class="p-3 flex items-start justify-between">
            <div class="pr-4 min-w-0">
              <div class="text-xs">
                <span class="font-medium">{{ prettyKind(f.kind) }}</span>
                <span class="opacity-60 ml-2">{{ f.detected_at }}</span>
              </div>

              <div v-if="parsed(f).line || parsed(f).snippet" class="mt-1">
                <div v-if="parsed(f).line" class="text-xs opacity-70">Zeile {{ parsed(f).line }}</div>
                <pre v-if="parsed(f).snippet"
                     class="mt-1 text-xs bg-white dark:bg-[#0b1222] border rounded p-2 overflow-auto whitespace-pre-wrap">
{{ parsed(f).snippet }}
                </pre>
              </div>
            </div>

            <div class="shrink-0 text-right">
              <span
                class="text-[10px] uppercase tracking-wide px-2 py-1 rounded"
                :class="severityClass(f.severity)">
                {{ f.severity === 'high' ? 'Gefährlich' : 'Verdächtig' }}
              </span>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{ items: any[] | undefined }>()

/* Gruppierung nach Pfad */
const grouped = computed<Record<string, any[]>>(() => {
  const out: Record<string, any[]> = {}
  for (const f of (props.items || [])) {
    const p = f.path || '—'
    if (!out[p]) out[p] = []
    out[p].push(f)
  }
  // neueste zuerst je Datei
  for (const k of Object.keys(out)) out[k].sort((a,b)=>+new Date(b.detected_at) - +new Date(a.detected_at))
  return out
})

/* Expand-Zustand pro Datei – standardmäßig ZU (collapsed) */
const open = ref<Record<string, boolean>>({})
function isOpen(path: string){ return open.value[path] ?? false }
function toggle(path: string){ open.value[path] = !isOpen(path) }

/* Severity: 'high' wenn irgendein Fund high, sonst 'medium' */
function groupSeverity(items: any[]): 'high'|'medium' {
  return items.some(i => i.severity === 'high') ? 'high' : 'medium'
}

/* Helpers */
function parsed(f: any) {
  const d = typeof f.detail === 'string' ? safeParse(f.detail) : (f.detail || {})
  return { line: d.line ?? d.ln ?? null, snippet: d.snippet ?? d.code ?? null }
}
function safeParse(s: string){ try { return JSON.parse(s) } catch { return {} } }
function prettyKind(k: string){ return (k||'').replaceAll('_',' ') }
function severityClass(s: string){
  return s === 'high'
    ? 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200'
    : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200'
}
async function copy(text: string){
  try { await navigator.clipboard.writeText(text) } catch {}
}
</script>

<style scoped>
.fade-enter-active,.fade-leave-active{ transition: opacity .15s ease }
.fade-enter-from,.fade-leave-to{ opacity: 0 }
</style>
