// AIMETA P=路由配置_所有页面路由定义|R=路由表_导航守卫_权限控制|NR=不含组件实现|E=router:index|X=internal|A=router实例|D=vue-router|S=none|RD=./README.ai
import { createRouter, createWebHistory } from 'vue-router'
import WorkspaceEntry from '../views/WorkspaceEntry.vue'
import NovelWorkspace from '../views/NovelWorkspace.vue'
import InspirationMode from '../views/InspirationMode.vue'
import WritingDesk from '../views/WritingDesk.vue'
import NovelDetail from '../views/NovelDetail.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'workspace-entry',
      component: WorkspaceEntry,
      meta: { requiresAuth: true },
    },
    {
      path: '/workspace',
      name: 'novel-workspace',
      component: NovelWorkspace,
      meta: { requiresAuth: true },
    },
    {
      path: '/inspiration',
      name: 'inspiration-mode',
      component: InspirationMode,
      meta: { requiresAuth: true },
    },
    {
      path: '/detail/:id',
      name: 'novel-detail',
      component: NovelDetail,
      props: true,
      meta: { requiresAuth: true },
    },
    {
      path: '/novel/:id',
      name: 'writing-desk',
      component: WritingDesk,
      props: true,
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      redirect: '/',
    },
    {
      path: '/register',
      redirect: '/',
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/novel/:id',
      name: 'admin-novel-detail',
      component: () => import('../views/AdminNovelDetail.vue'),
      props: true,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  if (authStore.token && !authStore.user) {
    await authStore.fetchUser()
  }

  const requiresAdmin = to.matched.some(record => record.meta.requiresAdmin)
  const isAdmin = authStore.user?.is_admin ?? true

  if (to.path === '/login' || to.path === '/register') {
    return { path: '/' }
  }

  if (requiresAdmin && !isAdmin) {
    return { path: '/' }
  }

  return true
})

export default router
