import { createRouter, createWebHistory } from 'vue-router'
import Login from './pages/Login.vue'
import Dashboard from './pages/Dashboard.vue'
import Users from './pages/Users.vue'
import Settings from './pages/Settings.vue'
import Tickets from './pages/Tickets.vue'
import TicketDetail from './pages/TicketDetail.vue'
import ScanMalware from '@/pages/ScanMalware.vue'
import TicketSeoScans from '@/pages/TicketSeoScans.vue'
import WootOverview from './pages/modules/comms-woot/WootOverview.vue'
import LiveVisitors from './pages/modules/comms-woot/LiveVisitors.vue'
import { useAuth } from './stores/auth'


const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: Dashboard },
    { path: '/users', component: Users },
    { path: '/settings', component: Settings },
    { path: '/tickets', component: Tickets },
    { path: '/tickets/:id', name: 'ticket', component: TicketDetail, props: true },
    { path: '/scan/malware/:id', name: 'scan-malware', component: ScanMalware, props: true },
    

    // Chatwoot / Comms
    { path: '/comms/woot', name: 'comms-woot', component: WootOverview },
    { path: '/live-visitors', name: 'live-visitors', component: LiveVisitors },
    // SEO
   
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.inited) {
    try {
      await auth.init()
    } catch {}
  }
  if (to.meta.public) {
    return auth.user && to.path === '/login'
      ? { path: '/', replace: true }
      : true
  }
  if (!auth.user) {
    return {
      path: '/login',
      query: { next: to.fullPath },
      replace: true,
    }
  }
  return true
})

export default router
