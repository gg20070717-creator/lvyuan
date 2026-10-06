import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'welcome',
    component: () => import('@/views/WelcomeView.vue'),
    meta: { title: '旅鸢' },
  },
  {
    path: '/app',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/app/home',
    children: [
      {
        path: 'home',
        name: 'home',
        component: () => import('@/views/HomeView.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('@/views/KnowledgeBaseView.vue'),
        meta: { title: '定制学习资源' },
      },
      {
        path: 'knowledge-tree',
        name: 'knowledge-tree',
        component: () => import('@/views/KnowledgeSkillTreeView.vue'),
        meta: { title: '知识技能树' },
      },
      {
        path: 'path',
        name: 'learning-path',
        component: () => import('@/views/LearningPathView.vue'),
        meta: { title: '学习路线' },
      },
      {
        path: 'training',
        name: 'training',
        component: () => import('@/views/TrainingGroundView.vue'),
        meta: { title: '训练场' },
      },
      {
        path: 'toolbox',
        name: 'toolbox',
        component: () => import('@/views/ToolboxView.vue'),
        meta: { title: '工具箱' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '学情中心' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 首页可自由浏览，个人学习模块由用户主动登录或完善画像后进入。
import { useOnboardingStore } from '@/stores/onboarding'
import { useAccountsStore } from '@/stores/accounts'

router.beforeEach(async (to) => {
  const isAppModule = to.path.startsWith('/app/')
  if (!isAppModule || to.path === '/app/home') return true
  try {
    const accounts = useAccountsStore()
    if (!accounts.isSignedIn) { accounts.openAccess(to.fullPath); return { path: '/app/home' } }
    const st = useOnboardingStore()
    if (!st.loaded || st.loadedUserId !== accounts.userId) await st.load(accounts.userId)
    if (!st.done) {
      accounts.openOnboarding(to.fullPath)
      return { path: '/app/home' }
    }
  } catch { /* pinia 未就绪则放行 */ }
  return true
})

// 全局标题守卫
router.afterEach((to) => {
  const title = (to.meta.title as string) || '旅鸢'
  document.title = title === '旅鸢' ? '旅鸢——中国入境游旅行定制师多智能体协同实训平台' : `${title} · 旅鸢`
})

export default router
