<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import { useAuth } from './stores/auth'
import Layout from './layouts/Layout.vue'

const auth = useAuth()
auth.restore()
const route = useRoute()
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 dark:text-gray-100">
    <!-- Login ohne Layout -->
    <RouterView v-if="route.path === '/login'" />

    <!-- Alle anderen Seiten IMMER im Layout -->
    <Layout v-else>
      <RouterView />
    </Layout>
  </div>
</template>
