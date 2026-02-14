<!-- frontend/src/modules/repair-beta/tabs/TabExplorer.vue -->
<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <div class="text-sm font-medium">SFTP Explorer</div>

      <div class="flex items-center gap-2">
        <label class="text-xs flex items-center gap-2 select-none">
          <input type="checkbox" v-model="w.showAllInExplorer" />
          Alles anzeigen
        </label>

        <button
          class="px-3 py-2 rounded-md border text-sm disabled:opacity-50"
          :disabled="!w.sessionId || w.lsLoading"
          @click="w.ls(w.currentPath)"
        >
          {{ w.lsLoading ? "Lade…" : "Aktualisieren" }}
        </button>

        <button
          class="px-3 py-2 rounded-md border text-sm disabled:opacity-50"
          :disabled="!w.canSetRootHere || w.savingRootFromExplorer"
          @click="w.setRootFromExplorer()"
        >
          {{ w.savingRootFromExplorer ? "Speichert…" : "Als Root setzen" }}
        </button>
      </div>
    </div>

    <div v-if="!w.sessionId" class="p-3 rounded-md bg-amber-50 text-amber-800 text-sm">
      Bitte zuerst im Tab “SFTP & Projekte” verbinden.
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-3">
      <div class="rounded-xl border p-3">
        <div class="flex items-center justify-between mb-2">
          <div class="text-xs font-semibold opacity-80">Ordner</div>
          <button class="text-xs px-2 py-1 rounded border" :disabled="w.currentPath === '/'" @click="w.goUp()">
            ↑ hoch
          </button>
        </div>

        <div class="text-[11px] opacity-70 mb-2">Pfad: <span class="font-mono">{{ w.currentPath }}</span></div>

        <div v-if="w.lsLoading" class="text-xs opacity-70">Lade…</div>
        <div v-else-if="w.lsError" class="text-xs text-red-600">{{ w.lsError }}</div>

        <div v-else class="space-y-1 max-h-[22rem] overflow-y-auto pr-1">
          <button
            v-for="d in w.filteredDirs"
            :key="d.name"
            class="w-full text-left px-2 py-1 rounded-md text-sm hover:bg-black/5"
            @click="w.goToPath(w.join(w.currentPath, d.name))"
          >
            📁 {{ d.name }}
          </button>
        </div>
      </div>

      <div class="lg:col-span-2 rounded-xl border p-3">
        <div class="flex items-center justify-between mb-2">
          <div class="text-xs font-semibold opacity-80">Dateien</div>
          <div class="text-[11px] opacity-70">
            {{ w.filteredFiles?.length || 0 }} Datei(en)
          </div>
        </div>

        <div v-if="w.lsLoading" class="text-xs opacity-70">Lade…</div>
        <div v-else-if="w.lsError" class="text-xs text-red-600">{{ w.lsError }}</div>

        <div v-else class="space-y-1 max-h-[22rem] overflow-y-auto pr-1">
          <div
            v-for="f in w.filteredFiles"
            :key="f.name"
            class="px-2 py-1 rounded-md text-sm border flex items-center justify-between gap-2"
          >
            <div class="min-w-0">
              <div class="truncate">{{ f.name }}</div>
              <div class="text-[11px] opacity-60" v-if="f.size != null">
                {{ w.formatBytes?.(f.size) }}
              </div>
            </div>

            <div class="flex items-center gap-2 shrink-0">
              <button class="text-xs px-2 py-1 rounded border" @click="w.copyToClipboard(w.join(w.currentPath, f.name), 'sftp')">
                Pfad kopieren
              </button>
            </div>
          </div>

          <div v-if="!w.filteredFiles?.length" class="text-xs opacity-70">
            Keine Dateien im aktuellen Pfad.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from "vue";
const props = defineProps<{ w: any }>();

// beim Öffnen direkt einmal listen (wenn Session schon da ist)
onMounted(() => {
  if (props.w.sessionId) props.w.ls(props.w.currentPath || "/");
});

// wenn Session neu gesetzt wird: automatisch / listen
watch(
  () => props.w.sessionId,
  (sid: string) => {
    if (sid) {
      props.w.currentPath = props.w.currentPath || "/";
      props.w.ls(props.w.currentPath);
    }
  }
);
</script>
