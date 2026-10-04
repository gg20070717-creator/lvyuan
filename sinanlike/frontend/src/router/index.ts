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

// 首登模块锁：未完成先验学情画像前，只能待在首页（对话/答题），其它模块拦截
import { ElMessage } from 'element-plus'
import { useOnboardingStore } from '@/stores/onboarding'

router.beforeEach((to) => {
  const isAppModule = to.path.startsWith('/app/')
  if (!isAppModule || to.path === '/app/home') return true
  try {
    const st = useOnboardingStore()
    // 状态尚未从后端加载且本地也无“已完成”标记 → 先放行一次（Home/Main 加载后会再拦）
    if (!st.loaded && !st.done) return true
    if (!st.done) {
      ElMessage.warning('请先在首页完成“先验学情画像”后再进入该模块')
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
