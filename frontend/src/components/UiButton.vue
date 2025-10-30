<template>
  <button class="px-4 py-2 rounded-2xl shadow bg-brand text-white hover:opacity-90 disabled:opacity-50" :disabled="disabled">
    <slot />
  </button>
</template>
<script setup lang="ts">
defineProps<{ disabled?: boolean }>()
</script>
