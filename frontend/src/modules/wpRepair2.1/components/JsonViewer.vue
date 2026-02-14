<script setup lang="ts">
import { computed } from "vue";
const props = defineProps<{ value: any }>();
const formatted = computed(() =>
  JSON.stringify(props.value, null, 2)
);
</script>

<template>
  <pre class="text-xs overflow-auto max-h-80 p-2 bg-black text-green-300 rounded">
{{ formatted }}
  </pre>
</template>
