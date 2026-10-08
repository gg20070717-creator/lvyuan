<template>
  <div class="main-layout" :class="{ 'route-preserved': route.path === '/app/path' }">
    <AccountFlow />
    <AgentWorkflowFloat />
    <header class="topbar">
      <div class="topbar-inner">
        <router-link to="/app/home" class="brand" aria-label="旅鸢首页">
          <span class="brand-mark"><img :src="logoMark" alt="" /></span><span class="brand-name">旅鸢</span>
        </router-link>
        <nav class="primary-nav" aria-label="学习阶段">
          <router-link v-for="group in learningNavigation" :key="group.id" :to="remembered[group.id]" class="primary-item" :class="{ active: activeNavigation?.section === group.id }" :aria-current="activeNavigation?.section === group.id ? 'true' : undefined">
            <SIcon :name="group.icon" :size="16" /><span>{{ group.label }}</span>
          </router-link>
        </nav>
        <nav class="utility-nav" aria-label="学习工具">
          <router-link v-for="item in utilities" :key="item.path" :to="item.path" :class="{ active: route.path === item.path }" :aria-current="route.path === item.path ? 'page' : undefined"><SIcon :name="item.icon" :size="16" /><span>{{ item.label }}</span></router-link>
        </nav>
        <AccountMenu horizontal />
      </div>
    </header>
    <div class="subbar">
      <div class="subbar-inner">
        <Transition name="submenu" mode="out-in">
          <nav v-if="activeGroup" :key="activeGroup.id" class="secondary-nav" aria-label="具体功能">
            <router-link v-for="item in activeGroup.items" :key="item.id" :to="item.path" :class="{ active: activeNavigation?.item === item.id }" :aria-current="activeNavigation?.item === item.id ? 'page' : undefined">
              <SIcon :name="item.icon" :size="15" />{{ item.label }}
            </router-link>
          </nav>
          <div v-else key="utility" class="utility-location"><router-link to="/app/home">首页</router-link><SIcon name="right" :size="12" /><span>{{ route.meta.title }}</span></div>
        </Transition>
        <LearningStatusBar v-if="route.path !== '/app/path'" compact />
      </div>
    </div>
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <Transition name="page-switch" mode="out-in">
          <keep-alive :key="appStore.userId">
            <component :is="Component" :key="route.name" />
          </keep-alive>
        </Transition>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAccountsStore } from '@/stores/accounts'
import AccountMenu from '@/components/AccountMenu.vue'
import AccountFlow from '@/components/AccountFlow.vue'
import AgentWorkflowFloat from '@/components/AgentWorkflowFloat.vue'
import LearningStatusBar from '@/components/LearningStatusBar.vue'
import { useCooperationStore } from '@/stores/cooperation'
import { useOnboardingStore } from '@/stores/onboarding'
import { learningNavigation, resolveLearningNavigation } from '@/utils/navigation'
import SIcon from '@/components/SIcon.vue'
import logoMark from '@/assets/lvyuan-logo.jpg'

const route = useRoute()
const appStore = useAppStore(), accountsStore = useAccountsStore()
const onb = useOnboardingStore(), cooperation = useCooperationStore()
const utilities = [
  { path: '/app/knowledge', label: '学习资源', icon: 'library' },
  { path: '/app/path', label: '学习路线', icon: 'map' },
  { path: '/app/toolbox', label: '工具箱', icon: 'tool' },
]
const activeNavigation = computed(() => resolveLearningNavigation(route.path, route.query))
const activeGroup = computed(() => learningNavigation.find(group => group.id === activeNavigation.value?.section))
const defaults = { assessment: '/app/home?section=portrait', practice: '/app/home?activity=quiz', integrated: '/app/training?focus=integrated&phase=pre' }
const remembered = reactive({ ...defaults })
watch(() => accountsStore.userId, () => { Object.assign(remembered, defaults); rememberActive() })
function rememberActive() {
  const active = activeNavigation.value
  if (active) {
    const group = learningNavigation.find(group => group.id === active.section)!
    remembered[active.section] = group.items.find(item => item.id === active.item)!.path
  }
}
watch(() => route.fullPath, rememberActive, { immediate:true })
let statusTimer: ReturnType<typeof setInterval> | undefined
watch(() => [accountsStore.userId, appStore.sessionId, route.fullPath], () => void cooperation.refreshLearning())
watch(() => accountsStore.userId, () => {
  if (accountsStore.isSignedIn) {
    if (onb.loadedUserId !== accountsStore.userId) void onb.load(accountsStore.userId)
  } else onb.clearSession()
}, { immediate: true })
onMounted(() => {
  accountsStore.ensureAccounts(); appStore.startHealthCheck(); void cooperation.loadCatalog(); void cooperation.refreshLearning()
  statusTimer = setInterval(() => void cooperation.refreshLearning(), 20000)
})
onUnmounted(() => { appStore.stopHealthCheck(); if (statusTimer) clearInterval(statusTimer) })
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;
.main-layout { display:flex; flex-direction:column; height:100vh; height:100dvh; overflow:hidden; background:$color-bg; }
.topbar { position:relative; z-index:80; flex-shrink:0; color:#fff; background:linear-gradient(105deg,#338ff2,#3c94ed); }
.topbar-inner { min-height:68px; max-width:1440px; padding:0 32px; margin:auto; display:flex; align-items:center; gap:30px; }
.brand { display:flex; align-items:center; gap:10px; flex-shrink:0; color:#fff; text-decoration:none; }
.brand-mark { display:flex; align-items:center; justify-content:center; flex-shrink:0; width:38px; height:38px; background:#fff; border-radius:10px 3px 10px 3px; overflow:hidden; img { display:block; width:100%; height:100%; min-width:0; min-height:0; object-fit:contain; } }
.brand-name { font:600 24px/1.3 $font-serif; letter-spacing:3px; }
.primary-nav { display:flex; align-items:center; gap:5px; flex-shrink:0; }
.primary-item { display:flex; align-items:center; gap:8px; padding:10px 17px; border-radius:10px 3px 10px 3px; text-decoration:none; font-size:14px; color:#f4f9ff; transition:background .25s,color .25s,box-shadow .25s; &:hover { background:rgba(255,255,255,.12); } &.active { color:$color-text-link; background:#fff; box-shadow:0 3px 12px #1e72c216; } }
.utility-nav { display:flex; align-items:center; gap:4px; margin-left:auto; padding:4px; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.28); border-radius:11px; a { display:flex; align-items:center; justify-content:center; gap:7px; min-height:35px; padding:8px 12px; font-size:13px; font-weight:500; color:#fff; text-decoration:none; white-space:nowrap; border-radius:7px; transition:background .2s,color .2s; &:hover { background:rgba(255,255,255,.15); } &.active { background:#fff; color:$color-text-link; box-shadow:0 2px 6px #1f70be14; } } }
.subbar { flex-shrink:0; background:#fff; border-bottom:1px solid #e0ebf5; }
.subbar-inner { min-height:49px; max-width:1120px; margin:auto; padding:0 28px; display:flex; align-items:center; justify-content:space-between; gap:24px; }
.secondary-nav { display:flex; gap:24px; flex-shrink:0; a { display:flex; align-items:center; gap:7px; position:relative; padding:16px 3px; font-size:13px; line-height:17px; color:$color-text-secondary; text-decoration:none; transition:color .22s; &::after { content:''; position:absolute; height:2px; bottom:0; left:3px; right:3px; border-radius:2px; background:#338ff2; transform:scaleX(0); transition:transform .25s ease; } &:hover { color:$color-text-link; } &.active { color:$color-text-link; font-weight:600; &::after { transform:scaleX(1); } } } }
.utility-location { display:flex; align-items:center; gap:12px; font-size:12px; color:$color-text-secondary; a { color:$color-text-link; text-decoration:none; } }
.main-content { flex:1; min-height:0; min-width:0; display:flex; flex-direction:column; position:relative; overflow:hidden; }
.main-layout:not(.route-preserved) .main-content { background:#f5f9fd; }
a:focus-visible { outline:2px solid #a5d3ff; outline-offset:4px; }
.submenu-enter-active { transition:opacity .22s ease,transform .26s ease; }
.submenu-leave-active { transition:opacity .13s ease; }
.submenu-enter-from { opacity:0; transform:translateX(7px); }
.submenu-leave-to { opacity:0; }
@media(max-width:1080px) { .topbar-inner { gap:18px; padding:0 22px; } .primary-item { padding:10px 12px; } .utility-nav { a { padding:8px 9px; font-size:12px; } } .brand-name { font-size:22px; } }
@media(max-width:940px) { .topbar-inner { gap:12px; flex-wrap:wrap; padding:12px 18px 0; } .primary-nav { order:3; width:100%; justify-content:center; padding-bottom:11px; } .utility-nav { margin-left:auto; } .subbar-inner { padding:0 20px; gap:12px; } }
@media(max-width:560px) { .topbar-inner { padding:10px 14px 0; gap:10px; } .brand-mark { width:32px; height:32px; } .brand-name { font-size:20px; letter-spacing:2px; } .utility-nav { order:4; width:100%; margin-bottom:10px; a { flex:1; padding:8px 6px; font-size:12px; } } .topbar-inner :deep(.acm) { margin-left:auto; } .primary-item { padding:9px 14px; font-size:13px; } .subbar-inner { flex-wrap:wrap; gap:0; padding:0 14px; } .secondary-nav { gap:21px; } .subbar-inner :deep(.learning-status-bar) { width:100%; padding:0 0 9px; } }
@media(prefers-reduced-motion:reduce) { .submenu-enter-active,.submenu-leave-active,.primary-item,.secondary-nav a::after { transition:none; } .submenu-enter-from { transform:none; } }
</style>
