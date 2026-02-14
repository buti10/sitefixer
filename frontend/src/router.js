import { createRouter, createWebHistory } from 'vue-router' 
import Login from './pages/Login.vue'
import Dashboard from './pages/Dashboard.vue'
import Users from './pages/Users.vue'
import Settings from './pages/Settings.vue'
import ChangePassword from './pages/ChangePassword.vue'
import Tickets from './pages/Tickets.vue'
import TicketDetail from './pages/TicketDetail.vue'
import WootOverview from './pages/WootOverview.vue'
import LiveVisitors from './pages/LiveVisitors.vue'
import TicketSeoScanDetail from '@/pages/TicketSeoScanDetail.vue'
import TicketSeoScans from '@/pages/TicketSeoScans.vue'

const routes = [
  { path: '/login', component: Login, meta:{ public:true } },
  { path: '/', component: Dashboard },
  { path: '/tickets', component: Tickets, meta:{ roles:['admin','supporter'] } },
  { path: '/tickets/:id', name: 'ticket', component: TicketDetail, meta:{ roles:['admin','supporter'] } },
  { path: '/users', component: Users, meta:{ roles:['admin','supporter'] } },
  { path: '/settings', component: Settings, meta:{ roles:['admin','supporter'] } },
  { path: '/account/password', component: ChangePassword },

  { path: '/tickets/:id/repairs', name: 'ticket-repairs', component: () => import('@/pages/TicketRepairs.vue') },

  // Scans
  { path: '/tickets/:id/scans/malware', name: 'scan-malware', component: () => import('./pages/ScanMalware.vue'), props: true },

  // HIER BITTE DIESE ZEILE LÖSCHEN/ENTFERNEN (doppelte Route, brauchen wir nicht):
  // { path: '/tickets/:id/scans/seo', component: () => import('./pages/ScanSeo.vue'), props: true },

  // Neue SEO-Übersicht (die du schon nutzt)
  { path: '/tickets/:id/scans/seo', name: 'TicketSeoScans', component: TicketSeoScans, props: true },

  // NEU: Detail-Route – path VOR dem Fallback
  { path: '/tickets/:id/scans/seo/:scanId', name: 'ticket-seo-scan-detail', component: TicketSeoScanDetail, props: true },

  // Comms
  { path: '/comms/woot', name: 'comms-woot', component: WootOverview, meta:{ roles:['admin','supporter'] } },
  { path: '/live-visitors', name: 'live-visitors', component: LiveVisitors, meta:{ roles:['admin','supporter'] } },
  { path: '/tickets/:id/wp-repair', name: 'wp-repair',component: () => import("@/modules/wpRepair/views/WpRepairWorkspace.vue") },

  // Fallback immer ganz unten
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

// >>> NEU: einfache Guard (optional)
router.beforeEach((to, from, next) => {
  // Login ist öffentlich
  if (to.meta.public) {
    return next()
  }

  // Alle anderen Routen sind "protected".
  // Den eigentlichen Auth-Status prüft dein Backend;
  // wenn das Token abgelaufen ist, sorgt der axios-Interceptor für Redirect.
  return next()
})

export default router
