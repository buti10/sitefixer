#ScanStartForm.vue
<template>
  <div class="rounded-xl border bg-white dark:bg-[#0f1424] p-4">
    <div class="flex items-center gap-2 mb-2"><span>🚀</span><h3 class="font-semibold">Scan starten</h3></div>

    <form class="space-y-3" @submit.prevent="submit">
      <label class="block text-sm">
        <span class="opacity-70">Root-Pfad</span>
        <div class="flex gap-2 mt-1">
          <input v-model="root_path" type="text" class="flex-1 rounded border px-3 py-2 bg-transparent" placeholder="/var/www/html" />
          <button type="button" class="px-3 py-2 rounded border hover:bg-black/5" @click="openBrowser">Browse (SFTP)</button>
        </div>
      </label>

      <div class="flex items-center gap-4 text-sm">
        <label class="inline-flex items-center gap-2"><input type="checkbox" v-model="quick"/> Quick-Scan</label>
        <label class="inline-flex items-center gap-2"><input type="checkbox" v-model="overwrite_baseline"/> Baseline neu schreiben</label>
      </div>

      <div class="flex gap-2">
        <button :disabled="busy" class="px-4 py-2 rounded-lg bg-green-600 text-white disabled:opacity-60">Start</button>
        <div class="text-xs opacity-60">SID: {{ sftpSid || '—' }}</div>
      </div>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    </form>

    <div v-if="showBrowser" class="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div class="bg-white dark:bg-[#0f1424] rounded-xl border w-full max-w-3xl p-4">
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-semibold">SFTP Browser</h4>
          <button class="px-2 py-1 border rounded" @click="closeBrowser">✖</button>
        </div>
        <SftpBrowser :ticket-id="ticket?.id || 0" :initial-path="root_path || '/'" @selected="onSelected" @cancel="closeBrowser" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import SftpBrowser from './SftpBrowser.vue';
import type { Ticket } from '@/api';

const props = defineProps<{ ticket: Ticket|null; defaults: { root_path?: string }; busy?: boolean }>();
const emit = defineEmits<{ (e: 'start', v: { root_path: string; quick: boolean; overwrite_baseline: boolean }): void }>();

const root_path = ref<string>('');
const quick = ref(false);
const overwrite_baseline = ref(false);
const showBrowser = ref(false);
const error = ref<string|undefined>();

onMounted(() => {
  root_path.value = props.defaults?.root_path || props.ticket?.access?.root_path || '/';
});

watch(() => props.defaults, (d) => {
  root_path.value = d?.root_path || root_path.value;
}, { deep: true });

function submit() {
  error.value = undefined;
  if (!root_path.value) { error.value = 'Root-Pfad erforderlich'; return; }
  emit('start', { root_path: root_path.value, quick: quick.value, overwrite_baseline: overwrite_baseline.value });
}

function openBrowser() { showBrowser.value = true; }
function closeBrowser() { showBrowser.value = false; }
function onSelected(path: string) { root_path.value = path; closeBrowser(); }
</script>
