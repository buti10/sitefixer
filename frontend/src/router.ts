import { createRouter, createWebHistory } from 'vue-router'
import Login from './pages/Login.vue'
import Dashboard from './pages/Dashboard.vue'
import Users from './pages/Users.vue'
import Settings from './pages/Settings.vue'
import Tickets from './pages/Tickets.vue'
import TicketDetail from './pages/TicketDetail.vue'
import ScanMalware from '@/pages/ScanMalware.vue'
import { useAuth } from './stores/auth'

const MailInbox    = () => import('@/modules/comms-mail/pages/MailInbox.vue')
const ChatInbox   = () => import('@/modules/comms-chat/pages/ChatInbox.vue')
const ChatDetail   = () => import('@/modules/comms-chat/pages/ChatDetail.vue')
const ChatStats   = () => import('@/modules/comms-stats/pages/StatsChat.vue')
const MailStats   = () => import('@/modules/comms-stats/pages/StatsMail.vue')

const VisitorsPage = () => import('@/modules/comms-visitors/pages/Visitors.vue')
const StatsPage    = () => import('@/modules/comms-stats/pages/Stats.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: Dashboard },
    { path: '/users', component: Users },
    { path: '/settings', component: Settings },
    { path: '/tickets', component: Tickets },
    { path: '/tickets/:id', name:'ticket', component: TicketDetail, props: true },
    { path: '/scan/malware/:id', name: 'scan-malware', component: ScanMalware, props: true },
    { path: '/scan/seo/:id', component: () => import('./pages/ScanSeo.vue') },

    // Comms
    // MAIL
    
    { path: '/mail/inbox',  name:'mail-inbox',
      component: () => import('@/modules/comms-mail/pages/MailInbox.vue') },
    { path: '/mail/:id',    name:'mail-detail',
      component: () => import('@/modules/comms-mail/pages/MailDetail.vue'), props:true },

     // CHAT
    { path: '/chat/inbox',  name:'chat-inbox',
      component: () => import('@/modules/comms-chat/pages/ChatInbox.vue') },
    { path: '/chat/:id',    name:'chat-detail',
      component: () => import('@/modules/comms-chat/pages/ChatDetail.vue'), props:true },

    { path: '/stats/visitors',  name:'stats-visitors',  component: () => import('@/modules/comms-stats/pages/StatsVisitors.vue') },
    { path: '/stats/chat', name:'stats-chat', component: () => import('@/modules/comms-stats/pages/StatsChat.vue') },
    { path: '/stats/mail', name:'stats-mail', component: () => import('@/modules/comms-stats/pages/StatsMail.vue') },

    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.inited) { try { await auth.init() } catch {} }
  if (to.meta.public) return (auth.user && to.path === '/login') ? { path: '/', replace: true } : true
  if (!auth.user) return { path: '/login', query: { next: to.fullPath }, replace: true }
  return true
})

export default router
