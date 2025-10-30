<script setup lang="ts">
import { ref, onMounted } from 'vue'

const dark = ref(false)

onMounted(() => {
  dark.value = localStorage.getItem('sf_theme') === 'dark'
  document.documentElement.classList.toggle('dark', dark.value)
})

function toggle() {
  dark.value = !dark.value
  localStorage.setItem('sf_theme', dark.value ? 'dark' : 'light')
  document.documentElement.classList.toggle('dark', dark.value)
}
</script>

<template>
  <button
    class="px-3 py-1 rounded border text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
    @click="toggle"
    :title="dark ? 'Light mode' : 'Dark mode'"
  >
    {{ dark ? '🌙' : '☀️' }}
  </button>
</template>
