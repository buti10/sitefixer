<template>
  <div class="space-y-4">
    <h1 class="text-xl font-semibold">Mail Inbox</h1>
    <div class="rounded-xl border overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-black/5 dark:bg-white/5">
          <tr>
            <th class="p-3 text-left">Betreff</th>
            <th class="p-3 text-left">Von</th>
            <th class="p-3 text-left">Status</th>
            <th class="p-3 text-left">Zeit</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in store.inbox" :key="t.id" class="border-t">
            <td class="p-3">{{ t.subject }}</td>
            <td class="p-3">{{ t.from }}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-xs border">{{ t.status }}</span></td>
            <td class="p-3">{{ t.ts ? new Date(t.ts).toLocaleString() : '—' }}</td>
            <td class="p-3">
              <RouterLink :to="`/mail/${t.id}`" class="text-blue-600">Details</RouterLink>
            </td>
          </tr>
          <tr v-if="!store.inbox.length">
            <td class="p-4 text-center opacity-60" colspan="5">Keine Einträge</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useMailStore } from '@/modules/comms-mail/stores/MailStore'
const store = useMailStore()
onMounted(()=>store.fetchInbox())
</script>
