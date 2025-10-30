<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import UiCard from '../components/UiCard.vue'
import UiButton from '../components/UiButton.vue'
import UiInput from '../components/UiInput.vue'
import api from '../api'

const email = ref('')
const password = ref('')
const router = useRouter()
const auth = useAuth()
const err = ref('')

onMounted(async () => {
  try { const r = await api.get('/users/me'); auth.user = r.data; router.push('/') } catch {}
})

async function submit () {
  try {
    await api.post('/auth/login', { email: email.value, password: password.value })
    const r = await api.get('/users/me'); auth.user = r.data
    localStorage.setItem('sf_user', JSON.stringify(r.data))
    router.push('/')
  } catch { err.value = 'Login fehlgeschlagen' }
}
</script>
<template>
  <div class="min-h-screen grid place-items-center bg-gray-50 dark:bg-[#121526]">
    <UiCard class="w-full max-w-md">
      <h1 class="text-xl font-semibold mb-4">Anmelden</h1>
      <form @submit.prevent="submit" class="space-y-4">
        <UiInput label="E‑Mail" v-model="email" type="email" />
        <UiInput label="Passwort" v-model="password" type="password" />
        <UiButton>Login</UiButton>
        <p v-if="err" class="text-red-600 text-sm">{{ err }}</p>
      </form>
    </UiCard>
  </div>
</template>
