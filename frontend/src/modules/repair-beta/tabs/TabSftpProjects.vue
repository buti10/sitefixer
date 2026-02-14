<template>
  <div class="space-y-4">
    <div class="grid gap-4 lg:grid-cols-2">
      <!-- Connect -->
      <div class="rounded-xl border border-black/5 dark:border-white/10 p-4 space-y-3">
        <div class="flex items-center justify-between">
          <div class="font-medium text-sm">SFTP Verbindung</div>
          <span class="text-xs px-2 py-1 rounded-full border"
            :class="w.sessionId ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-gray-200 bg-gray-50 text-gray-700'">
            {{ w.sessionId ? 'verbunden' : 'nicht verbunden' }}
          </span>
        </div>

        <div class="flex gap-2">
          <button class="px-3 py-2 rounded-md bg-violet-600 text-white text-sm disabled:opacity-50"
            :disabled="w.connecting" @click="w.connectSftp()">
            {{ w.connecting ? 'Verbinde…' : 'Verbinden' }}
          </button>

          <button class="px-3 py-2 rounded-md border text-sm disabled:opacity-50"
            :disabled="!w.sessionId || w.connecting" @click="w.refreshProjects()">
            Projekte neu suchen
          </button>
        </div>

        <div v-if="w.connectError" class="text-xs text-red-600">{{ w.connectError }}</div>
        <div v-if="w.connectInfo" class="text-xs text-emerald-600">{{ w.connectInfo }}</div>
      </div>

      <!-- Projects -->
      <div class="rounded-xl border border-black/5 dark:border-white/10 p-4 space-y-3">
        <div class="font-medium text-sm">WordPress Projekte</div>

        <select v-model="w.selectedProject" class="w-full rounded-md border px-2 py-2 text-sm"
          :disabled="!w.sessionId || w.projectsLoading">
          <option :value="null">– Projekt wählen –</option>
          <option v-for="p in w.projects" :key="p.root_path" :value="p.root_path">
            {{ p.label || p.root_path }}{{ p.wp_version ? ` · WP ${p.wp_version}` : '' }}
          </option>
        </select>

        <div class="flex gap-2">
          <button class="px-3 py-2 rounded-md bg-emerald-600 text-white text-sm disabled:opacity-50"
            :disabled="!w.selectedProject || w.savingRoot" @click="save()">
            {{ w.savingRoot ? 'Speichert…' : 'Als Root setzen' }}
          </button>

          <button class="px-3 py-2 rounded-md border text-sm"
            :disabled="!w.selectedProject" @click="$emit('go','overview')">
            Übersicht
          </button>
        </div>

        <div v-if="w.projectsLoading" class="text-xs opacity-70">Suche Projekte…</div>
        <div v-if="w.projectsError" class="text-xs text-red-600">{{ w.projectsError }}</div>
        <div v-if="w.rootSaved" class="text-xs text-emerald-600">Root gespeichert. Weiter: Diagnose.</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ w: any }>();
defineEmits<{ (e: "go", k: any): void }>();

async function save() {
  await props.w.saveRoot();
  // UX wie vorher:
  // nach Root setzen zurück zur Übersicht
  // (wenn du es lieber im Composable machst: dort $emit ist nicht möglich, daher hier)
}
</script>
