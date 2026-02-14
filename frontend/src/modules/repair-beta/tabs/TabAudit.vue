<template>
  <div v-if="w.showAudit?.value" class="rounded-2xl border bg-white p-3 mt-4">
    <div class="text-xs font-semibold opacity-80 mb-2">Audit / Verlauf</div>
    <div v-if="w.historyBusy?.value" class="text-xs opacity-70">Lädt…</div>
    <pre v-else class="text-[11px] whitespace-pre-wrap bg-black/5 rounded-xl p-2 max-h-[20rem] overflow-auto">{{
      JSON.stringify(w.actionHistory?.value || [], null, 2)
    }}</pre>
  </div>

</template>
