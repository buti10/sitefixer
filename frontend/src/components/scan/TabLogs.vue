<template>
  <div class="text-sm">
    <div v-if="!scan" class="opacity-70">Kein Scan aktiv.</div>
    <div v-else>
      <pre class="whitespace-pre-wrap text-xs bg-black/5 dark:bg-white/10 p-3 rounded">{{ scan.log_tail || '—' }}</pre>
    </div>
  </div>
</template>
<script setup lang="ts">
import type { Scan } from '@/api';
defineProps<{ scan: Scan|null }>()
</script>
SftpTreeNode.vue