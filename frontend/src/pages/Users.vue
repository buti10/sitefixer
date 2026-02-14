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
              <th class="py-2 pr-2">E-Mail</th>
              <th class="py-2 pr-2">Rolle</th>
              <th class="py-2 pr-2">Aktiv</th>
              <th class="py-2 pr-2">Chatwoot-ID</th>
              <th class="py-2 pr-2 w-40"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="u in users"
              :key="u.id"
              class="border-t border-black/10 dark:border-white/10"
            >
              <td class="py-2 pr-2">{{ u.id }}</td>
              <td class="py-2 pr-2">{{ u.name }}</td>
              <td class="py-2 pr-2 truncate max-w-[260px]">{{ u.email }}</td>
              <td class="py-2 pr-2 capitalize">{{ u.role }}</td>
              <td class="py-2 pr-2">
                <span
                  class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px]"
                  :class="u.active
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
                    : 'bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-400'"
                >
                  <span
                    class="mr-1 inline-block h-1.5 w-1.5 rounded-full"
                    :class="u.active ? 'bg-emerald-500' : 'bg-gray-400'"
                  />
                  {{ u.active ? 'aktiv' : 'inaktiv' }}
                </span>
              </td>
              <td class="py-2 pr-2">
                <span class="font-mono text-xs">
                  {{ u.woot_user_id ?? '—' }}
                </span>
              </td>
              <td class="py-2 pr-2 text-right space-x-3">
                <button
                  class="text-brand"
                  @click="openEditUser(u)"
                >
                  Bearbeiten
                </button>
                <button
                  class="text-brand"
                  @click="resetPass(u)"
                >
                  Passwort
                </button>
                <button
                  class="text-red-600"
                  @click="removeUser(u)"
                >
                  Löschen
                </button>
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
    <div
      v-if="openNew"
      class="fixed inset-0 z-30 grid place-items-center bg-black/30"
    >
      <UiCard class="w-full max-w-md">
        <h3 class="font-medium mb-4">Neuer Benutzer</h3>
        <form @submit.prevent="create" class="space-y-3">
          <UiInput label="Name" v-model="formNew.name" />
          <UiInput label="E-Mail" v-model="formNew.email" type="email" />
          <UiInput
            label="Passwort"
            v-model="formNew.password"
            type="password"
          />
          <UiInput
            label="Chatwoot-ID (optional)"
            v-model="formNew.woot_user_id"
            type="number"
            min="1"
          />

          <div class="flex gap-2 mt-2">
            <UiButton>Speichern</UiButton>
            <button
              type="button"
              class="px-4 py-2 text-sm"
              @click="openNew = false"
            >
              Abbrechen
            </button>
          </div>
          <p v-if="errNew" class="text-red-600 text-sm mt-2">{{ errNew }}</p>
        </form>
      </UiCard>
    </div>

    <!-- Dialog Benutzer bearbeiten -->
    <div
      v-if="openEdit && editUser"
      class="fixed inset-0 z-30 grid place-items-center bg-black/30"
    >
      <UiCard class="w-full max-w-md">
        <h3 class="font-medium mb-4">
          Benutzer bearbeiten (#{{ editForm.id }})
        </h3>

        <form @submit.prevent="saveEdit" class="space-y-3 text-sm">
          <UiInput label="Name" v-model="editForm.name" />
          <UiInput label="E-Mail" v-model="editForm.email" type="email" disabled />

          <div>
            <label class="block text-xs font-medium mb-1">Rolle</label>
            <select
              v-model="editForm.role"
              class="border rounded px-2 py-1 w-full bg-white dark:bg-[#141827] border-gray-300 dark:border-white/20"
            >
              <option value="admin">admin</option>
              <option value="agent">agent</option>
              <option value="viewer">viewer</option>
            </select>
          </div>

          <div class="flex items-center gap-2">
            <input
              id="edit-active"
              type="checkbox"
              v-model="editForm.active"
            />
            <label for="edit-active" class="text-xs">Benutzer ist aktiv</label>
          </div>

          <UiInput
            label="Chatwoot-ID"
            v-model="editForm.woot_user_id"
            type="number"
            min="1"
            placeholder="z.B. 17"
          />

          <div class="flex gap-2 mt-2">
            <UiButton :disabled="savingEdit">Speichern</UiButton>
            <button
              type="button"
              class="px-4 py-2 text-sm"
              @click="closeEdit"
            >
              Abbrechen
            </button>
          </div>
          <p v-if="errEdit" class="text-red-600 text-sm mt-2">{{ errEdit }}</p>
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

// Neu-Dialog
const openNew = ref(false)
const formNew = ref({
  name: '',
  email: '',
  password: '',
  woot_user_id: '' as string | number | '',
})
const errNew = ref('')

// Edit-Dialog
const openEdit = ref(false)
const editUser = ref<any | null>(null)
const editForm = ref<{
  id: number | null
  name: string
  email: string
  role: string
  active: boolean
  woot_user_id: string | number | ''
}>({
  id: null,
  name: '',
  email: '',
  role: 'agent',
  active: true,
  woot_user_id: '',
})
const errEdit = ref('')
const savingEdit = ref(false)

async function load () {
  try {
    const r = await api.get('/users/')
    users.value = Array.isArray(r.data) ? r.data : []
  } finally {
    loaded.value = true
  }
}

function openEditUser (u: any) {
  editUser.value = u
  editForm.value = {
    id: u.id,
    name: u.name,
    email: u.email,
    role: u.role,
    active: !!u.active,
    woot_user_id: u.woot_user_id ?? '',
  }
  errEdit.value = ''
  openEdit.value = true
}

function closeEdit () {
  openEdit.value = false
  editUser.value = null
}

async function saveEdit () {
  if (!editForm.value.id) return
  savingEdit.value = true
  errEdit.value = ''
  try {
    await api.patch(`/users/${editForm.value.id}`, {
      name: editForm.value.name,
      role: editForm.value.role,
      active: editForm.value.active,
      woot_user_id: editForm.value.woot_user_id || null,
    })
    // lokale Liste aktualisieren
    const idx = users.value.findIndex(u => u.id === editForm.value.id)
    if (idx !== -1) {
      users.value[idx] = {
        ...users.value[idx],
        name: editForm.value.name,
        role: editForm.value.role,
        active: editForm.value.active,
        woot_user_id: editForm.value.woot_user_id || null,
      }
    }
    closeEdit()
  } catch (e: any) {
    errEdit.value = e?.response?.data?.msg || e?.response?.data?.error || 'Fehler beim Speichern'
  } finally {
    savingEdit.value = false
  }
}

async function resetPass (u: any) {
  const p = prompt('Neues Passwort:')
  if (!p) return
  await api.patch(`/users/${u.id}`, { password: p })
  alert('gesetzt')
}

async function create () {
  errNew.value = ''
  try {
    await api.post('/users/', {
      name: formNew.value.name,
      email: formNew.value.email,
      password: formNew.value.password,
      ...(formNew.value.woot_user_id
        ? { woot_user_id: formNew.value.woot_user_id }
        : {}),
    })
    openNew.value = false
    formNew.value = { name: '', email: '', password: '', woot_user_id: '' }
    await load()
  } catch (e: any) {
    errNew.value = e?.response?.data?.msg || e?.response?.data?.error || 'Fehler'
  }
}

async function removeUser (u: any) {
  if (!confirm('Benutzer löschen?')) return
  await api.delete(`/users/${u.id}`)
  await load()
}

onMounted(load)
</script>
