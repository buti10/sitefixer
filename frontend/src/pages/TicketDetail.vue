<!-- src/pages/TicketDetails.vue -->
<template>
  <div class="space-y-6">
    <!-- Header / Summary -->
    <div
      class="rounded-xl bg-white/80 dark:bg-[#0f1424]/80 border border-black/5 dark:border-white/10 shadow-sm p-4 sm:p-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <!-- Links: Titel + Meta -->
      <div class="space-y-1">
        <div class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
            <!-- Ticket-Icon -->
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="4" y="3" width="16" height="18" rx="2" />
              <path d="M9 7h6" />
              <path d="M9 11h6" />
              <path d="M9 15h3" />
            </svg>
          </span>
          <span class="text-xs uppercase tracking-wide">Ticket</span>
        </div>
        <h1 class="text-2xl font-semibold">
          Ticket #{{ data.ticket_id ?? id }}
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Erstellt am {{ fmt(data.created_at) }} · {{ data.name || 'Unbekannter Kunde' }}
        </p>
      </div>

      <!-- Mitte: Domain / Status / Prio -->
      <div class="flex flex-wrap gap-2 items-center">
        <a v-if="data.domain" :href="norm(data.domain)" target="_blank" rel="noopener"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-black/10 dark:border-white/20 text-xs sm:text-sm bg-white dark:bg-[#141827] hover:bg-black/5 dark:hover:bg-white/10">
          <!-- Globe-Icon -->
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18" />
            <path d="M12 3a15.3 15.3 0 0 1 4 9 15.3 15.3 0 0 1-4 9 15.3 15.3 0 0 1-4-9 15.3 15.3 0 0 1 4-9z" />
          </svg>
          <span class="max-w-[12rem] truncate">{{ data.domain }}</span>
        </a>

        <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium capitalize"
          :class="statusPillClass(data.status)">
          {{ data.status || 'Status unbekannt' }}
        </span>

        <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
          :class="prioPillClass(data.prio)">
          {{ data.prio || 'Prio unbekannt' }}
        </span>
      </div>

      <!-- Rechts: Zurück -->
      <div class="flex md:flex-col gap-2 md:items-end">
        <RouterLink to="/"
          class="inline-flex items-center justify-center gap-1 rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs sm:text-sm text-gray-700 dark:text-gray-100 hover:bg-black/5 dark:hover:bg-white/10">
          <span>←</span>
          <span>Zurück zum Dashboard</span>
        </RouterLink>
      </div>
    </div>

    <!-- Fehler / Loading -->
    <div v-if="error" class="p-3 rounded-md bg-red-50 text-red-700 text-sm">
      {{ error }}
    </div>
    <div v-else-if="loading" class="p-4 rounded-xl border bg-white dark:bg-[#0f1424]">
      Lädt…
    </div>

    <!-- Inhalt -->
    <div v-else class="space-y-6">
      <!-- Kundendaten + Verwaltung -->
      <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
        <div class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
          <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
            <!-- User-Icon -->
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="8" r="3" />
              <path d="M6 19c0-2.2 2.1-4 6-4s6 1.8 6 4" />
            </svg>
          </span>
          <span>Kundendaten & Ticket-Verwaltung</span>
        </div>

        <div class="p-4 space-y-4 text-sm">
          <!-- Stammdaten -->
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <div class="text-xs opacity-70 mb-0.5">Ticket-ID</div>
              <div>#{{ data.ticket_id ?? id }}</div>
            </div>
            <div>
              <div class="text-xs opacity-70 mb-0.5">Datum</div>
              <div>{{ fmt(data.created_at) }}</div>
            </div>
            <div>
              <div class="text-xs opacity-70 mb-0.5">Name</div>
              <div>{{ data.name || '—' }}</div>
            </div>
            <div>
              <div class="text-xs opacity-70 mb-0.5">E-Mail</div>
              <div>
                <a v-if="data.email" :href="`mailto:${data.email}`" class="text-blue-600 hover:underline break-all">
                  {{ data.email }}
                </a>
                <span v-else>—</span>
              </div>
            </div>
            <div>
              <div class="text-xs opacity-70 mb-0.5">Domain</div>
              <div>
                <a v-if="data.domain" :href="norm(data.domain)" target="_blank" rel="noopener"
                  class="text-blue-600 hover:underline break-all">
                  {{ data.domain }}
                </a>
                <span v-else>—</span>
              </div>
            </div>
            <div>
              <div class="text-xs opacity-70 mb-0.5">CMS</div>
              <div>{{ data.cms || '—' }}</div>
            </div>
            <div>
              <div class="text-xs opacity-70 mb-0.5">Hoster</div>
              <div>{{ data.hoster || data.hosting_provider || '—' }}</div>
            </div>

            <div class="sm:col-span-2" v-if="data.beschreibung">
              <div class="text-xs opacity-70 mb-0.5">Beschreibung</div>
              <pre
                class="whitespace-pre-wrap text-sm rounded-lg border border-black/5 dark:border-white/10 bg-black/5 dark:bg-white/5 px-3 py-2">
{{ data.beschreibung }}</pre>
            </div>
          </div>

          <!-- PSA + Status -->
          <div class="pt-3 mt-2 border-t border-black/5 dark:border-white/10 grid gap-4 md:grid-cols-2">
            <!-- PSA -->
            <div>
              <div class="text-xs opacity-70 mb-0.5">Persönlicher Ansprechpartner (PSA)</div>
              <div
                class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-black/5 dark:border-white/10 bg-black/5 dark:bg-white/5 mb-2">
                <span class="text-sm font-medium">
                  {{ currentPsaName }}
                </span>
                <span v-if="data.psa_id || psaSelected" class="text-[11px] opacity-60">
                  ID {{ psaSelected || data.psa_id }}
                </span>
              </div>

              <div class="flex flex-col sm:flex-row gap-2">
                <select v-model.number="psaSelected"
                  class="flex-1 rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm">
                  <option :value="null">– PSA wählen –</option>
                  <option v-for="s in supporters" :key="s.id" :value="s.id">
                    {{ s.name }} (#{{ s.id }})
                  </option>
                </select>
                <button type="button"
                  class="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
                  :disabled="!psaSelected || psaSaving" @click="savePsa">
                  {{ psaSaving ? 'Speichert…' : 'PSA speichern' }}
                </button>
              </div>
              <div v-if="psaError" class="mt-1 text-xs text-red-500">
                {{ psaError }}
              </div>
              <div v-if="psaSuccess" class="mt-1 text-xs text-emerald-500">
                PSA gespeichert.
              </div>
            </div>

            <!-- Ticket-Status -->
            <div>
              <div class="text-xs opacity-70 mb-0.5">Ticket-Status</div>
              <div class="flex items-center gap-2 mb-1">
                <span
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize border border-black/10 dark:border-white/20"
                  :class="statusPillClass(statusSelected || data.status)">
                  {{ statusSelected || data.status || '—' }}
                </span>
                <span class="text-[11px] opacity-60">aktuell</span>
              </div>
              <div class="flex flex-col sm:flex-row gap-2">
                <select v-model="statusSelected"
                  class="flex-1 rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm">
                  <option :value="null">– Status wählen –</option>
                  <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
                <button type="button"
                  class="px-3 py-1.5 rounded-md bg-emerald-600 text-white text-sm hover:bg-emerald-700 disabled:opacity-50"
                  :disabled="!statusSelected || statusSaving" @click="saveStatus">
                  {{ statusSaving ? 'Speichert…' : 'Status aktualisieren' }}
                </button>
              </div>
              <div v-if="statusError" class="mt-1 text-xs text-red-500">
                {{ statusError }}
              </div>
              <div v-if="statusSuccess" class="mt-1 text-xs text-emerald-500">
                Status gespeichert.
              </div>
            </div>
          </div>

          <!-- Zugänge einklappbar -->
          <div class="pt-3 mt-2 border-t border-black/5 dark:border-white/10">
            <button type="button" class="w-full flex items-center justify-between text-sm font-medium px-1 py-1.5"
              @click="accessOpen = !accessOpen">
              <div class="flex items-center gap-2">
                <svg class="h-4 w-4 text-gray-500 dark:text-gray-300" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" stroke-width="2">
                  <circle cx="7.5" cy="15.5" r="3.5" />
                  <path d="M10.9 12.1 19 4" />
                  <path d="m15 5 4 4" />
                </svg>
                <span>Zugänge (FTP, Website, Hosting)</span>
              </div>
              <svg class="h-4 w-4 text-gray-500 dark:text-gray-300 transform transition-transform"
                :class="accessOpen ? 'rotate-90' : ''" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="2">
                <path d="M9 6l6 6-6 6" />
              </svg>
            </button>

            <div v-if="accessOpen" class="mt-2 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <!-- FTP -->
              <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
                <div
                  class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
                  <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
                    <!-- Server Icon -->
                    <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="4" width="18" height="6" rx="1" />
                      <rect x="3" y="14" width="18" height="6" rx="1" />
                      <path d="M7 8h.01M7 18h.01" />
                    </svg>
                  </span>
                  <span>FTP</span>
                </div>
                <div class="p-4 grid gap-3 text-sm">
                  <div>
                    <div class="text-xs opacity-70 mb-0.5">Host</div>
                    <div class="break-all">
                      {{ data.ftp_host || data.ftp_server || data.zugang_ftp_host || '—' }}
                    </div>
                  </div>
                  <div>
                    <div class="text-xs opacity-70 mb-0.5">User</div>
                    <div class="break-all">{{ data.ftp_user || data.zugang_ftp_user || '—' }}</div>
                  </div>

                  <div>
                    <div class="text-xs opacity-70 mb-0.5">Passwort</div>
                    <div class="flex items-center gap-2">
                      <span class="select-all">
                        {{ ftpPass ? (show.ftp ? ftpPass : '••••••••') : '—' }}
                      </span>
                      <button type="button"
                        class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                        :disabled="!ftpPass" @click="show.ftp = !show.ftp">
                        {{ show.ftp ? 'Verbergen' : 'Anzeigen' }}
                      </button>
                      <button type="button"
                        class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                        :disabled="!ftpPass" @click="copy(ftpPass)">
                        {{ copied === 'ftp' ? 'Kopiert' : 'Kopieren' }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Website -->
              <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
                <div
                  class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
                  <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
                    <!-- Browser Icon -->
                    <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="4" width="18" height="16" rx="1" />
                      <path d="M3 9h18" />
                    </svg>
                  </span>
                  <span>Website</span>
                </div>
                <div class="p-4 grid gap-3 text-sm">
                  <div>
                    <div class="text-xs opacity-70 mb-0.5">Login</div>
                    <div class="break-all">
                      {{
                        data.website_login ||
                        data.website_user ||
                        data.zugang_website_login ||
                        '—'
                      }}
                    </div>
                  </div>

                  <div>
                    <div class="text-xs opacity-70 mb-0.5">Passwort</div>
                    <div class="flex items-center gap-2">
                      <span class="select-all">
                        {{ webPass ? (show.web ? webPass : '••••••••') : '—' }}
                      </span>
                      <button type="button"
                        class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                        :disabled="!webPass" @click="show.web = !show.web">
                        {{ show.web ? 'Verbergen' : 'Anzeigen' }}
                      </button>
                      <button type="button"
                        class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                        :disabled="!webPass" @click="copy(webPass)">
                        {{ copied === 'web' ? 'Kopiert' : 'Kopieren' }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Hosting -->
              <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
                <div
                  class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
                  <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
                    <!-- Cloud Icon -->
                    <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.7-1.7A4 4 0 1 1 19 18z" />
                    </svg>
                  </span>
                  <span>Hosting</span>
                </div>
                <div class="p-4 grid gap-3 text-sm">
                  <div>
                    <div class="text-xs opacity-70 mb-0.5">URL</div>
                    <div class="break-all">
                      {{ data.hosting_url || data.hoster_url || data.zugang_hosting_url || '—' }}
                    </div>
                  </div>
                  <div>
                    <div class="text-xs opacity-70 mb-0.5">User</div>
                    <div class="break-all">
                      {{ data.hosting_user || data.zugang_hosting_user || '—' }}
                    </div>
                  </div>

                  <div>
                    <div class="text-xs opacity-70 mb-0.5">Passwort</div>
                    <div class="flex items-center gap-2">
                      <span class="select-all">
                        {{ hostPass ? (show.host ? hostPass : '••••••••') : '—' }}
                      </span>
                      <button type="button"
                        class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                        :disabled="!hostPass" @click="show.host = !show.host">
                        {{ show.host ? 'Verbergen' : 'Anzeigen' }}
                      </button>
                      <button type="button"
                        class="px-2 py-0.5 text-xs rounded border border-black/10 dark:border-white/20 disabled:opacity-50"
                        :disabled="!hostPass" @click="copy(hostPass)">
                        {{ copied === 'host' ? 'Kopiert' : 'Kopieren' }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Angebot & Notizen -->
      <div class="grid gap-6 lg:grid-cols-2">
        <!-- Angebot & Zahlungslink -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
          <div
            class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
            <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
              <!-- Euro Icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 7h-5a4 4 0 0 0-4 4v2a4 4 0 0 0 4 4h5" />
                <path d="M9 12h7" />
              </svg>
            </span>
            <span>Angebot & Zahlungslink</span>
          </div>
          <div class="p-4 space-y-4 text-sm">
            <div class="space-y-1">
              <div class="text-xs opacity-70">Aktueller Status</div>
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize border border-black/10 dark:border-white/20"
                  :class="statusPillClass(data.status)">
                  {{ data.status || '—' }}
                </span>
                <span v-if="data.angebot" class="text-xs opacity-70">
                  Angebot: {{ Number(data.angebot).toFixed(2) }} €
                </span>
              </div>
            </div>

            <div class="space-y-1">
              <div class="text-xs opacity-70">Produkt (WooCommerce)</div>
              <select v-model.number="selectedProductId"
                class="w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm">
                <option :value="null">– Produkt wählen –</option>
                <option v-for="p in products" :key="p.id" :value="p.id">
                  {{ p.name }} ({{ p.price.toFixed(2) }} €)
                </option>
              </select>
              <div v-if="productsError" class="mt-1 text-xs text-red-500">
                {{ productsError }}
              </div>
            </div>

            <div>
              <button type="button"
                class="px-4 py-2 rounded-md bg-emerald-600 text-white text-sm hover:bg-emerald-700 disabled:opacity-50 inline-flex items-center gap-1.5"
                :disabled="!selectedProductId || paymentSending" @click="sendPayment">
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 12h7" />
                  <path d="M10 8l4 4-4 4" />
                  <rect x="2" y="3" width="20" height="18" rx="2" />
                </svg>
                <span>{{ paymentSending ? 'Sendet…' : 'Zahlungslink senden' }}</span>
              </button>
              <div v-if="paymentError" class="mt-1 text-xs text-red-500">
                {{ paymentError }}
              </div>
              <div v-if="paymentSuccess" class="mt-1 text-xs text-emerald-500">
                Zahlungslink wurde gesendet.
              </div>
            </div>

            <div v-if="data.stripe || data.payment_link"
              class="border-t border-black/5 dark:border-white/10 pt-3 text-xs">
              <div class="opacity-70 mb-0.5">Aktueller Zahlungslink</div>
              <a :href="data.stripe || data.payment_link" target="_blank" rel="noopener"
                class="break-all text-blue-600 hover:underline">
                {{ data.stripe || data.payment_link }}
              </a>
            </div>
          </div>
        </div>

        <!-- Interne Kommentare / Notizen -->
        <div
          class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm flex flex-col">
          <div
            class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center justify-between gap-2 text-sm">
            <div class="flex items-center gap-2">
              <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
                <!-- Note Icon -->
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 4h16v14H9l-5 4z" />
                </svg>
              </span>
              <span>Interne Notizen</span>
            </div>
            <span class="text-xs opacity-70">nur intern im Team</span>
          </div>
          <div class="p-4 flex-1 flex flex-col gap-3 text-sm">
            <!-- Liste -->
            <div
              class="space-y-2 max-h-64 overflow-y-auto border border-black/5 dark:border-white/10 rounded-lg p-2 bg-black/0 dark:bg-white/0">
              <div v-if="notesLoading" class="text-xs opacity-70 px-1 py-0.5">
                Notizen werden geladen…
              </div>
              <div v-else-if="notesError" class="text-xs text-red-500 px-1 py-0.5">
                {{ notesError }}
              </div>
              <template v-else>
                <div v-if="notes.length" v-for="note in notes" :key="note.id"
                  class="rounded-md border border-black/5 dark:border-white/10 bg-black/5 dark:bg-white/5 px-2.5 py-2">
                  <div class="flex items-center justify-between text-[11px] opacity-70 mb-0.5">
                    <span>{{ note.author_name || 'Unbekannt' }}</span>
                    <span>{{ fmtDateTime(note.created_at) }}</span>
                  </div>
                  <div class="text-xs whitespace-pre-wrap">
                    {{ note.text }}
                  </div>
                  <div v-if="note.remind_at" class="mt-1 text-[11px] text-amber-500 flex items-center gap-1">
                    <span class="inline-block w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                    Wiedervorlage: {{ fmtDateTime(note.remind_at) }}
                  </div>
                </div>

                <div v-if="!notes.length" class="text-xs opacity-70 px-1 py-0.5">
                  Noch keine Notizen vorhanden.
                </div>
              </template>
            </div>

            <!-- Neue Notiz -->
            <form class="space-y-2" @submit.prevent="createNote">
              <div>
                <div class="text-xs opacity-70 mb-0.5">Neue Notiz</div>
                <textarea v-model="newNoteText" rows="3"
                  class="w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm resize-none"
                  placeholder="Interne Notiz zum Ticket…"></textarea>
              </div>

              <div class="grid gap-2 sm:grid-cols-[auto,1fr] items-center">
                <div class="text-xs opacity-70">
                  Wiedervorlage<br />
                  <span class="opacity-60">optional</span>
                </div>
                <input v-model="newNoteRemindAt" type="datetime-local"
                  class="rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-xs" />
              </div>

              <div class="flex justify-end gap-2">
                <button type="submit"
                  class="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
                  :disabled="!newNoteText || noteSaving">
                  {{ noteSaving ? 'Speichert…' : 'Notiz speichern' }}
                </button>
              </div>

              <div v-if="noteError" class="text-xs text-red-500">
                {{ noteError }}
              </div>
            </form>
          </div>
        </div>
      </div>

      <!-- Kunden-Uploads -->
      <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
        <button type="button"
          class="w-full px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center justify-between gap-2 text-sm"
          @click="uploadsOpen = !uploadsOpen">
          <div class="flex items-center gap-2">
            <span class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10">
              <!-- Upload Icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 3v12" />
                <path d="M8 7l4-4 4 4" />
                <rect x="4" y="15" width="16" height="6" rx="2" />
              </svg>
            </span>
            <span>Kunden-Uploads (My Account)</span>
            <span class="text-xs opacity-60" v-if="ticketUploads.length">
              · {{ ticketUploads.length }} Datei(en)
            </span>
          </div>
          <svg class="h-4 w-4 text-gray-500 dark:text-gray-300 transform transition-transform"
            :class="uploadsOpen ? 'rotate-90' : ''" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2">
            <path d="M9 6l6 6-6 6" />
          </svg>
        </button>

        <div v-if="uploadsOpen" class="p-4 text-sm">
          <div v-if="uploadsLoading" class="text-xs opacity-70">
            Uploads werden geladen…
          </div>
          <div v-else-if="uploadsError" class="text-xs text-red-500">
            {{ uploadsError }}
          </div>
          <div v-else-if="!ticketUploads.length" class="text-xs opacity-70">
            Noch keine Dateien hochgeladen.
          </div>
          <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <div v-for="u in ticketUploads" :key="u.id"
              class="rounded-lg border border-black/5 dark:border-white/10 bg-black/5 dark:bg-white/5 p-3 flex gap-3">
              <!-- Thumbnail -->
              <div
                class="w-16 h-16 rounded-md bg-black/10 dark:bg-white/10 overflow-hidden flex items-center justify-center text-[10px] text-gray-600 dark:text-gray-200">
                <img v-if="isImage(u.mime_type)" :src="uploadDownloadUrl(u)" :alt="u.original_filename || 'Upload'"
                  class="w-full h-full object-cover" />
                <div v-else class="px-1 text-center">
                  {{ (u.mime_type || 'Datei').split('/').pop() }}
                </div>
              </div>

              <!-- Inhalte -->
              <div class="flex-1 min-w-0 space-y-1">
                <div class="text-xs font-semibold break-all">
                  {{ u.original_filename || 'Datei' }}
                </div>
                <div class="text-[11px] opacity-70">
                  <span v-if="u.file_size">{{ formatBytes(u.file_size) }}</span>
                  <span v-if="u.file_size && u.mime_type"> · </span>
                  <span v-if="u.mime_type">{{ u.mime_type }}</span>
                </div>
                <div v-if="u.target_page || u.target_section" class="text-[11px] opacity-70">
                  {{ u.target_page || 'Seite unbekannt' }}
                  <span v-if="u.target_section"> · {{ u.target_section }}</span>
                </div>
                <div v-if="u.description" class="text-xs line-clamp-3">
                  {{ u.description }}
                </div>
                <div class="text-[11px] opacity-70" v-if="u.created_at">
                  Hochgeladen: {{ fmtDateTime(u.created_at) }}
                </div>
                <div class="pt-1">
                  <a :href="uploadDownloadUrl(u)" target="_blank" rel="noopener"
                    class="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
                    <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M4 20h16" />
                      <path d="M12 4v11" />
                      <path d="M8 11l4 4 4-4" />
                    </svg>
                    <span>Download</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Aktionen (Scans) -->
      <div class="grid gap-6 lg:grid-cols-4">
        <!-- Malware -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
          <div
            class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
            <span
              class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-200">
              <!-- Virus Icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 2v3" />
                <path d="M12 19v3" />
                <path d="M4.93 4.93 7.05 7.05" />
                <path d="M16.95 16.95 19.07 19.07" />
                <path d="M2 12h3" />
                <path d="M19 12h3" />
                <path d="M4.93 19.07 7.05 16.95" />
                <path d="M16.95 7.05 19.07 4.93" />
              </svg>
            </span>
            <span>Malware-Scan</span>
          </div>
          <div class="p-4">
            <button
              class="w-full px-4 py-2 rounded-md bg-red-600 text-white hover:bg-red-700 text-sm flex items-center justify-center gap-1.5"
              @click="go(`/tickets/${id}/scans/malware`)">
              <span>Scan starten</span>
            </button>
          </div>
        </div>

        <!-- SEO -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
          <div
            class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
            <span
              class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-200">
              <!-- SEO icon (chart) -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 3v18h18" />
                <path d="m7 14 3-3 4 4 5-7" />
              </svg>
            </span>
            <span>SEO-Scan</span>
          </div>
          <div class="p-4">
            <button
              class="w-full px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 text-sm flex items-center justify-center gap-1.5"
              @click="go(`/tickets/${id}/scans/seo`)">
              <span>Scan starten</span>
            </button>
          </div>
        </div>

        <!-- Repair -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
          <div
            class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
            <span
              class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-200">
              <!-- Wrench Icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 3a7 7 0 0 1-9.9 6.3L8 12.4 4.6 16 3 14.4 6.6 11l3.1-3.1A7 7 0 0 1 21 3z" />
                <path d="M3 21h4" />
              </svg>
            </span>
            <span>Repair</span>
          </div>
          <div class="p-4">
            <button
              class="w-full px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 text-sm flex items-center justify-center gap-1.5"
              @click="goRepair()">
              <span>Repair starten</span>
            </button>
          </div>
        </div>

        <!-- Repair Wordpress -->
        <div class="rounded-xl border border-black/5 dark:border-white/10 bg-white dark:bg-[#0f1424] shadow-sm">
          <div
            class="px-4 py-3 border-b border-black/5 dark:border-white/10 font-medium flex items-center gap-2 text-sm">
            <span
              class="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-200">
              <!-- Beaker/Lab Icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 2v6l-5 9a4 4 0 0 0 3.5 6h7A4 4 0 0 0 19 17l-5-9V2" />
                <path d="M8 8h8" />
              </svg>
            </span>

            <div class="flex items-center gap-2">
              <span>Repair</span>
              <span class="text-[11px] px-2 py-0.5 rounded-full bg-black/5 dark:bg-white/10">
                Beta
              </span>
            </div>
          </div>

          <div class="p-4 space-y-2">
            <button
              class="w-full px-4 py-2 rounded-md bg-violet-600 text-white hover:bg-violet-700 text-sm flex items-center justify-center gap-1.5"
              @click="goWpRepair(ticketId)">
              <span>Wordpress Repair starten</span>
            </button>

            <div class="text-xs text-gray-500 dark:text-gray-400 leading-snug">
              Neuer Wizard mit Logs & Undo – läuft parallel zum aktuellen Repair.
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { watch } from 'vue'
import {
  getTicket,
  getSupporters,
  getProducts,
  saveTicketPsa,
  sendPaymentLink,
  getTicketNotes,
  addTicketNote,
  getTicketUploads,
  updateTicketStatus,
} from '../api'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)

// Query/Session als Fallback
function qObj() {
  try {
    const s = String(route.query.s || '')
    return s ? JSON.parse(decodeURIComponent(atob(s))) : null
  } catch {
    return null
  }
}
function ssObj() {
  try {
    return JSON.parse(sessionStorage.getItem('sf_last_ticket') || 'null')
  } catch {
    return null
  }
}

const stateData = ref<any>(qObj() || (history.state as any)?.ticket || ssObj() || { ticket_id: id })
const apiData = ref<any>({})
const data = computed(() => ({ ...stateData.value, ...apiData.value }))

const loading = ref(true)
const error = ref<string | null>(null)

// PSA / Supporter
type Supporter = { id: number; name: string }
const supporters = ref<Supporter[]>([])
const psaSelected = ref<number | null>(null)
const psaSaving = ref(false)
const psaError = ref<string | null>(null)
const psaSuccess = ref(false)
const currentPsaName = computed(() => {
  if (data.value.psa_name) return data.value.psa_name as string
  if (data.value.psa_id && supporters.value.length) {
    const s = supporters.value.find(x => x.id === Number(data.value.psa_id))
    return s?.name || 'Zugewiesen (#' + data.value.psa_id + ')'
  }
  return 'Noch nicht zugewiesen'
})
watch(
  () => data.value.psa_id,
  (val) => {
    psaSelected.value = val != null ? Number(val) : null
  },
  { immediate: true }
)

// Ticket-Status
const statusOptions = [
  { value: 'offen', label: 'Offen' },
  { value: 'angebot', label: 'Angebot gesendet' },
  { value: 'warten', label: 'Wartet auf Kunde' },
  { value: 'bezahlt', label: 'Bezahlt' },
  { value: 'abgeschlossen', label: 'Abgeschlossen' },
]
const statusSelected = ref<string>(data.value.status || 'offen')
const statusSaving = ref(false)
const statusError = ref<string | null>(null)
const statusSuccess = ref(false)
watch(
  () => data.value.status,
  (val) => {
    if (val) statusSelected.value = String(val)
  },
  { immediate: true }
)


// Produkte / Angebot
type Product = { id: number; name: string; price: number }
const products = ref<Product[]>([])
const selectedProductId = ref<number | null>(null)
const productsError = ref<string | null>(null)
const paymentSending = ref(false)
const paymentError = ref<string | null>(null)
const paymentSuccess = ref(false)

// Notizen
const notes = ref<any[]>([])
const notesLoading = ref(true)
const notesError = ref<string | null>(null)
const newNoteText = ref('')
const newNoteRemindAt = ref('')
const noteSaving = ref(false)
const noteError = ref<string | null>(null)

// Kunden-Uploads
type TicketUpload = {
  id: number
  ticket_id?: number
  original_filename?: string
  file_size?: number
  mime_type?: string
  description?: string
  target_page?: string
  target_section?: string
  created_at?: string
  style?: any
}
const ticketUploads = ref<TicketUpload[]>([])
const uploadsLoading = ref(true)
const uploadsError = ref<string | null>(null)

// UI-Flags
const accessOpen = ref(true)
const uploadsOpen = ref(true)

// Anzeige/Kopie UI für Passwörter
const show = reactive({ ftp: false, web: false, host: false })
const copied = ref<'ftp' | 'web' | 'host' | ''>('')

const ftpPass = computed(() => data.value.ftp_pass || data.value.zugang_ftp_pass || '')
const webPass = computed(() => data.value.website_pass || data.value.zugang_website_pass || '')
const hostPass = computed(() => data.value.hosting_pass || data.value.zugang_hosting_pass || '')

onMounted(async () => {
  try {
    const r = await getTicket(id)
    if (r && typeof r === 'object') apiData.value = r
  } catch (e: any) {
    const s = e?.response?.status
    if (s && s !== 404) error.value = e?.response?.data?.msg || e?.message || 'Konnte Ticket nicht laden'
  } finally {
    loading.value = false
  }

  // Supporter laden (für PSA)
  try {
    const s = await getSupporters()
    if (Array.isArray(s)) {
      supporters.value = s.map((u: any) => ({
        id: Number(u.id ?? u.user_id ?? u.ID),
        name: String(u.name ?? u.display_name ?? u.user_login ?? 'Unbekannt'),
      }))
    }
  } catch (e: any) {
    console.warn('getSupporters failed', e)
  }

  // PSA Auswahl initial
  if (data.value.psa_id) {
    psaSelected.value = Number(data.value.psa_id)
  }

  // Produkte laden
  try {
    const p = await getProducts()
    if (Array.isArray(p)) {
      products.value = p.map((x: any) => ({
        id: Number(x.id ?? x.ID),
        name: String(x.name ?? x.post_title ?? 'Produkt'),
        price: Number(x.price ?? x._price ?? 0),
      }))
    }
  } catch (e: any) {
    productsError.value = e?.response?.data?.msg || e?.message || 'Produkte konnten nicht geladen werden'
  }

  // Notizen laden
  await loadNotes()

  // Kunden-Uploads laden
  await loadUploads()
})

async function savePsa() {
  if (!psaSelected.value) return
  psaSaving.value = true
  psaError.value = null
  psaSuccess.value = false
  try {
    const res = await saveTicketPsa(id, psaSelected.value)
    apiData.value = {
      ...apiData.value,
      psa_id: psaSelected.value,
      psa_name: res?.psa_name || currentPsaName.value,
    }
    psaSuccess.value = true
    setTimeout(() => {
      psaSuccess.value = false
    }, 2000)
  } catch (e: any) {
    psaError.value = e?.response?.data?.msg || e?.message || 'PSA konnte nicht gespeichert werden'
  } finally {
    psaSaving.value = false
  }
}

async function saveStatus() {
  if (!statusSelected.value) return
  statusSaving.value = true
  statusError.value = null
  try {
    const res = await updateTicketStatus(id, statusSelected.value)
    apiData.value = {
      ...apiData.value,
      status: res?.status || statusSelected.value,
    }
  } catch (e: any) {
    statusError.value =
      e?.response?.data?.msg || e?.message || 'Status konnte nicht gespeichert werden'
  } finally {
    statusSaving.value = false
  }
}
async function sendPayment() {
  if (!selectedProductId.value) return
  paymentSending.value = true
  paymentError.value = null
  paymentSuccess.value = false
  try {
    const res = await sendPaymentLink(id, selectedProductId.value)
    apiData.value = {
      ...apiData.value,
      stripe: res?.payment_link || apiData.value.stripe || apiData.value.payment_link,
      payment_link: res?.payment_link || apiData.value.payment_link,
      angebot: res?.amount ?? apiData.value.angebot,
      status: res?.status ?? apiData.value.status,
    }
    paymentSuccess.value = true
    setTimeout(() => {
      paymentSuccess.value = false
    }, 2000)
  } catch (e: any) {
    paymentError.value = e?.response?.data?.msg || e?.message || 'Zahlungslink konnte nicht gesendet werden'
  } finally {
    paymentSending.value = false
  }
}

async function loadNotes() {
  notesLoading.value = true
  notesError.value = null
  try {
    const r = await getTicketNotes(id)
    if (Array.isArray(r)) {
      notes.value = r
    } else if (Array.isArray(r?.items)) {
      notes.value = r.items
    } else {
      notes.value = []
    }
  } catch (e: any) {
    notesError.value = e?.response?.data?.msg || e?.message || 'Notizen konnten nicht geladen werden'
  } finally {
    notesLoading.value = false
  }
}

async function createNote() {
  if (!newNoteText.value) return
  noteSaving.value = true
  noteError.value = null
  try {
    const payload: any = { text: newNoteText.value }
    if (newNoteRemindAt.value) payload.remind_at = newNoteRemindAt.value
    await addTicketNote(id, payload)
    newNoteText.value = ''
    newNoteRemindAt.value = ''
    await loadNotes()
  } catch (e: any) {
    noteError.value = e?.response?.data?.msg || e?.message || 'Notiz konnte nicht gespeichert werden'
  } finally {
    noteSaving.value = false
  }
}

async function loadUploads() {
  uploadsLoading.value = true
  uploadsError.value = null
  try {
    const r = await getTicketUploads(id)
    if (Array.isArray(r)) {
      ticketUploads.value = r as TicketUpload[]
    } else if (Array.isArray(r?.items)) {
      ticketUploads.value = r.items as TicketUpload[]
    } else {
      ticketUploads.value = []
    }
  } catch (e: any) {
    uploadsError.value = e?.response?.data?.msg || e?.message || 'Uploads konnten nicht geladen werden'
  } finally {
    uploadsLoading.value = false
  }
}

// Clipboard / Passwörter
async function copy(text: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    if (text === ftpPass.value) copied.value = 'ftp'
    if (text === webPass.value) copied.value = 'web'
    if (text === hostPass.value) copied.value = 'host'
    setTimeout(() => {
      copied.value = ''
    }, 1200)
  } catch {
    // ignore
  }
}

// Helper
function fmt(d?: string | null) {
  if (!d) return '—'
  try {
    return (/^\d{4}-\d{2}-\d{2}/.test(d) ? d : new Date(d).toISOString()).slice(0, 10)
  } catch {
    return String(d).slice(0, 10)
  }
}

function fmtDateTime(d?: string | null) {
  if (!d) return '—'
  try {
    const dt = new Date(d)
    const iso = isNaN(dt.getTime()) ? new Date(String(d)).toISOString() : dt.toISOString()
    return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`
  } catch {
    return String(d)
  }
}

function formatBytes(bytes?: number | null) {
  if (!bytes && bytes !== 0) return ''
  const b = Number(bytes)
  if (b < 1024) return `${b} B`
  const kb = b / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(1)} MB`
}

function isImage(mime?: string | null) {
  return !!mime && /^image\//.test(mime)
}

function uploadDownloadUrl(u: TicketUpload) {
  return `/api/wp/tickets/${id}/uploads/${u.id}/download`
}

// Status/Prio-Badges
function statusPillClass(raw?: string | null) {
  const s = (raw || '').toLowerCase()
  if (['open', 'offen', 'neu', 'pending'].includes(s)) {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200'
  }
  if (['await', 'waiting', 'wartend', 'warten'].includes(s)) {
    return 'bg-sky-100 text-sky-800 dark:bg-sky-500/20 dark:text-sky-200'
  }
  if (['closed', 'done', 'resolved', 'erledigt', 'bezahlt', 'abgeschlossen'].includes(s)) {
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200'
  }
  if (['urgent', 'error', 'fail', 'abgebrochen'].includes(s)) {
    return 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200'
  }
  return 'bg-gray-100 text-gray-800 dark:bg-white/10 dark:text-gray-100'
}

function prioPillClass(raw?: string | null) {
  const v = (raw || '').toLowerCase()
  if (['high', 'hoch', 'urgent', 'prio1', 'p1'].includes(v)) {
    return 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-200'
  }
  if (['medium,', 'mittel', 'prio2', 'p2'].includes(v)) {
    return 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200'
  }
  if (['low', 'niedrig', 'prio3', 'p3'].includes(v)) {
    return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200'
  }
  return 'bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-100'
}

function goRepair() {
  router.push({
    path: `/tickets/${id}/repairs`,
    state: { ticket: data.value },
  })
}

function goWpRepair(ticketId: number) {
  // Fallback speichern (falls user Seite reloadet)
  sessionStorage.setItem("sf_last_ticket", JSON.stringify(data.value));

  router.push({
    name: "wp-repair",
    params: { id: ticketId },
    state: { ticket: data.value }, // <— wichtig
  });
}

function norm(u?: string) {
  return !u ? '#' : /^https?:\/\//i.test(u) ? u : `https://${u}`
}
function go(p: string) {
  if (p.endsWith('/scans/seo') || p.endsWith('/scans/malware')) {
    router.push({
      path: p,
      state: { ticket: data.value },
    })
  } else {
    router.push(p)
  }
}

function goRepairBeta() {
  router.push({
    path: `/tickets/${id}/repairs-beta`,
    state: { ticket: data.value },
  })
}

</script>
