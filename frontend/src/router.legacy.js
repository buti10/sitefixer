import { createRouter, createWebHistory } from 'vue-router'
import Login from './pages/Login.vue'
import Dashboard from './pages/Dashboard.vue'
import Users from './pages/Users.vue'
import Settings from './pages/Settings.vue'
import ChangePassword from './pages/ChangePassword.vue'
import Tickets from './pages/Tickets.vue'
import TicketDetail from './pages/TicketDetail.vue'

const routes = [
  { path: '/login', component: Login, meta:{ public:true } },
  { path: '/', component: Dashboard },
  { path: '/tickets', component: Tickets, meta:{ roles:['admin','supporter'] } },
  { path: '/tickets/:id', name: 'ticket', component: TicketDetail, meta:{ roles:['admin','supporter'] } },
  { path: '/users', component: Users, meta:{ roles:['admin','supporter'] } },
  { path: '/settings', component: Settings, meta:{ roles:['admin','supporter'] } },
  { path: '/account/password', component: ChangePassword },
  { path: '/tickets/:id/repairs', name: 'ticket-repairs',component: () => import('@/pages/TicketRepairs.vue'),},
  // 👉 relative Pfade, da kein Alias vorhanden
  { path: '/tickets/:id/scans/malware', name: 'scan-malware', component: () => import('./pages/ScanMalware.vue'), props: true },
  { path: '/tickets/:id/scans/seo',     component: () => import('./pages/ScanSeo.vue'),     props: true },

  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export default createRouter({ history: createWebHistory(), routes })
