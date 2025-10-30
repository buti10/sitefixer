<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
const id = useRoute().params.id as string
const thread = ref<any>(null)
const draft = ref('')
onMounted(async ()=>{
  const r = await fetch(`/mock/comms/mail/${id}.json`)
  thread.value = await r.json()
})
function send(){ draft.value='' } // später API
</script>

<template>
  <div v-if="thread" class="grid lg:grid-cols-[1fr_320px] gap-4">
    <div class="rounded-xl border p-4 space-y-4">
      <div v-for="m in thread.messages" :key="m.id" class="rounded-lg border p-3">
        <div class="text-xs opacity-60">
          {{ m.dir==='in'?'Von':'An' }} • {{ new Date(m.ts).toLocaleString() }}
        </div>
        <div class="mt-2" v-html="m.html || m.text"></div>
      </div>
      <form @submit.prevent="send" class="sticky bottom-0 bg-background">
        <textarea v-model="draft" rows="4" class="w-full border rounded-lg p-3" placeholder="Antwort schreiben…" />
        <div class="mt-2 flex justify-end"><button class="px-3 py-1.5 border rounded-lg">Senden</button></div>
      </form>
    </div>
    <aside class="rounded-xl border p-4 space-y-3">
      <div class="text-sm"><b>Status</b><br/>
        <select class="border rounded px-2 py-1 text-sm" :value="thread.status"><option>open</option><option>waiting</option><option>closed</option></select>
      </div>
      <div class="text-sm"><b>Assignee</b><br/><button class="px-2 py-1 border rounded text-sm">Übernehmen</button></div>
      <div class="text-sm"><b>Thema</b><div class="mt-1">{{ thread.subject }}</div></div>
    </aside>
  </div>
</template>
