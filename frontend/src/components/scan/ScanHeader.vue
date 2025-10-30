<template>
  <div class="rounded-xl border bg-white dark:bg-[#0f1424] p-5">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-xl">🛡️</span>
        <h2 class="text-xl font-semibold">Malware-Scan · Ticket #{{ ticketId }}</h2>
      </div>
      <RouterLink
        :to="`/tickets/${ticketId}`"
        class="px-3 py-1.5 rounded-lg border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/10"
      >Zurück</RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ ticketId: number }>();
</script>
