<!-- frontend/src/pages/Users.vue -->
<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">Benutzer</h2>
      <UiButton @click="openNew = true">Neu</UiButton>
    </div>

    <UiCard>
      <template v-if="loaded && users.length">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left">
              <th class="py-2 pr-2">ID</th>
              <th class="py-2 pr-2">Name</th>
              <th class="py-2 pr-2">E‑Mail</th>
              <th class="py-2 pr-2">Rolle</th>
              <th class="py-2 pr-2">Aktiv</th>
              <th class="py-2 pr-2 w-40"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" class="border-t border-black/10 dark:border-white/10">
              <td class="py-2 pr-2">{{ u.id }}</td>
              <td class="py-2 pr-2">
                <input v-model="u.name" @change="save(u)"
                       class="border rounded px-2 py-1 w-44 bg-white dark:bg-[#141827] border-gray-300 dark:border-white/20"/>
              </td>
              <td class="py-2 pr-2 truncate max-w-[260px]">{{ u.email }}</td>
              <td class="py-2 pr-2">
                <select v-model="u.role" @change="save(u)"
                        class="border rounded px-2 py-1 bg-white dark:bg-[#141827] border-gray-300 dark:border-white/20">
                  <option value="admin">admin</option>
                  <option value="agent">agent</option>
                  <option value="viewer">viewer</option>
                </select>
              </td>
              <td class="py-2 pr-2">
                <input type="checkbox" v-model="u.active" @change="save(u)" />
              </td>
              <td class="py-2 pr-2 text-right">
                <button class="text-brand mr-3" @click="resetPass(u)">Passwort</button>
                <button class="text-red-600" @click="removeUser(u)">Löschen</button>
              </td>
            </tr>
          </tbody>
        </table>
      </template>

      <template v-else-if="loaded && !users.length">
        <div class="text-sm opacity-70">Keine Benutzer vorhanden.</div>
      </template>

      <template v-else>
        <div class="text-sm opacity-70">Lade…</div>
      </template>
    </UiCard>

    <!-- Dialog Neuer Benutzer -->
    <div v-if="openNew" class="fixed inset-0 z-30 grid place-items-center bg-black/30">
      <UiCard class="w-full max-w-md">
        <h3 class="font-medium mb-4">Neuer Benutzer</h3>
        <form @submit.prevent="create" class="space-y-3">
          <UiInput label="Name" v-model="form.name" />
          <UiInput label="E‑Mail" v-model="form.email" type="email" />
          <UiInput label="Passwort" v-model="form.password" type="password" />
          <div class="flex gap-2">
            <UiButton>Speichern</UiButton>
            <button type="button" class="px-4 py-2" @click="openNew=false">Abbrechen</button>
          </div>
          <p v-if="err" class="text-red-600 text-sm">{{ err }}</p>
        </form>
      </UiCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api'
import UiCard from '../components/UiCard.vue'
import UiButton from '../components/UiButton.vue'
import UiInput from '../components/UiInput.vue'

const users = ref<any[]>([])
const loaded = ref(false)
const openNew = ref(false)
const form = ref({ name: '', email: '', password: '' })
const err = ref('')

async function load () {
  try {
    const r = await api.get('/users/')
    users.value = Array.isArray(r.data) ? r.data : []
  } finally {
    loaded.value = true
  }
}
async function save (u: any) {
  await api.patch(`/users/${u.id}`, { name: u.name, role: u.role, active: u.active })
}
async function resetPass (u: any) {
  const p = prompt('Neues Passwort:')
  if (!p) return
  await api.patch(`/users/${u.id}`, { password: p })
  alert('gesetzt')
}
async function create () {
  err.value = ''
  try {
    await api.post('/users/', form.value)
    openNew.value = false
    form.value = { name: '', email: '', password: '' }
    await load()
  } catch (e: any) {
    err.value = e?.response?.data?.msg || 'Fehler'
  }
}
async function removeUser (u: any) {
  if (!confirm('Benutzer löschen?')) return
  await api.delete(`/users/${u.id}`)
  await load()
}
onMounted(load)
</script>
