<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getTickets, getTicket } from '../api'

type Ticket = { ticket_id:number; name:string; email:string; domain:string }
const rows = ref<Ticket[]>([])
const loading = ref(true)
const detail = ref<any|null>(null)
const showDetail = ref(false)
const err = ref<string>("")

onMounted(async () => {
  try {
    const raw = await getTickets()
    rows.value = raw.map((r:any) => ({
      ticket_id: Number(r.id ?? r.ticket_id ?? r.entry_id),
      name: r.customer_name ?? r.name ?? '',
      email: r.email ?? '',
      domain: r.domain ?? ''
    }))
  } catch(e:any){ err.value = e?.message || 'Error' }
  finally { loading.value = false }
})


async function openDetail(id:number){
  detail.value = null; showDetail.value = true
  try { detail.value = await getTicket(id) } catch(e:any){ err.value = e?.message || 'Error' }
}
</script>

<template>
  <div class="p-6">
    <h1 class="text-2xl font-semibold mb-4">Kunden-Tickets</h1>
    <div v-if="err" class="text-red-600 mb-3">{{ err }}</div>
    <div v-if="loading">Lade…</div>

    <table v-else class="min-w-full text-sm border">
      <thead class="bg-gray-100">
        <tr>
          <th class="p-2 text-left">Ticket</th>
          <th class="p-2 text-left">Name</th>
          <th class="p-2 text-left">E-Mail</th>
          <th class="p-2 text-left">Domain</th>
          <th class="p-2"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.ticket_id" class="border-t">
          <td class="p-2">{{ r.ticket_id }}</td>
          <td class="p-2">{{ r.name }}</td>
          <td class="p-2">{{ r.email }}</td>
          <td class="p-2">{{ r.domain }}</td>
          <td class="p-2">
            <button class="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300"
                    @click="openDetail(r.ticket_id)">
              Details
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="showDetail" class="fixed inset-0 bg-black/30 flex items-center justify-center">
      <div class="bg-white rounded-xl p-6 w-[520px] max-w-full">
        <h2 class="text-xl font-semibold mb-3">Ticket-Details</h2>
        <div v-if="!detail">Lade…</div>
        <div v-else class="space-y-1">
          <div><b>Ticket:</b> {{ detail.ticket_id }}</div>
          <div><b>Name:</b> {{ detail.name }}</div>
          <div><b>Email:</b> {{ detail.email }}</div>
          <div><b>Domain:</b> {{ detail.domain }}</div>
          <div class="mt-3 font-semibold">Zugänge</div>
          <div><b>FTP Host:</b> {{ detail.ftp_host }}</div>
          <div><b>FTP User:</b> {{ detail.ftp_user }}</div>
          <div><b>FTP Pass:</b> {{ detail.ftp_pass }}</div>
          <div><b>WP User:</b> {{ detail.website_user }}</div>
          <div><b>WP Pass:</b> {{ detail.website_pass }}</div>
        </div>
        <div class="mt-5 text-right">
          <button class="px-4 py-1 rounded bg-gray-200" @click="showDetail=false">Schließen</button>
        </div>
      </div>
    </div>
  </div>
</template>
