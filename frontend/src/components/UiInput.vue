<template>
  <div class="space-y-1">
    <label v-if="label" class="text-sm text-gray-600 dark:text-gray-300">{{ label }}</label>
    <input
      :type="type"
      v-model="model"
      :placeholder="placeholder"
      class="w-full rounded-xl border border-gray-300 dark:border-white/20
             bg-white dark:bg-[#141827] text-gray-900 dark:text-gray-100
             px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand"
    />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ modelValue: string, label?: string, type?: string, placeholder?: string }>()
const emit = defineEmits(['update:modelValue'])
const model = computed({ get: () => props.modelValue, set: v => emit('update:modelValue', v as string) })
</script>
