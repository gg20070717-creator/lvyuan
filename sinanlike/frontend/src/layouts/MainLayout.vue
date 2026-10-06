<template>
  <div class="main-layout" :class="{ 'route-preserved': route.path === '/app/path' }">
    <AccountFlow />
    <!-- ── 侧栏导航（官方 logo · 可伸缩 · 参考队友视觉） ── -->
    <aside class="sb" :class="{ collapsed: appStore.sidebarCollapsed }">
      <!-- 品牌区（logo 图形 + 文字标 + 伸缩按钮）；收缩态点击 logo 展开 -->
      <div class="sb-brand" @click="appStore.sidebarCollapsed ? appStore.toggleSidebar() : $router.push('/app/home')">
        <div class="sb-logo"><img :src="logoMark" alt="旅鸢" /></div>
        <div v-if="!appStore.sidebarCollapsed" class="sb-brand-text">
          <div class="sb-name">旅鸢</div>
          
        </div>
        <button
          v-if="!appStore.sidebarCollapsed"
          class="sb-collapse"
          title="收起导航"
          @click.stop="appStore.toggleSidebar()"
        >
          <SIcon name="back" :size="12" />
        </button>
      </div>

      <!-- 导航菜单 -->
      <nav class="sb-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="sb-item"
          :class="{ active: isActive(item.path) }"
          :title="appStore.sidebarCollapsed ? item.label : ''"
        >
          <SIcon :name="item.icon" :size="18" />
          <span v-if="!appStore.sidebarCollapsed" class="t">{{ item.label }}</span>
          <span v-if="isActive(item.path) && !appStore.sidebarCollapsed" class="dot"></span>
        </router-link>
      </nav>

      <!-- 连续学习卡 -->
      <div v-if="!appStore.sidebarCollapsed && accountsStore.isSignedIn" class="sb-streak">
        <div class="streak-card">
          <div class="streak-top">
            <SIcon name="flame" :size="14" color="#338FF2" />
            <span class="label">连续学习</span>
          </div>
          <div class="streak-num"><span class="n">{{ streakDays }}</span><span class="u">天</span></div>
          <div class="streak-dots">
            <div class="sdot on" v-for="i in Math.min(5, streakDays)" :key="i"></div>
            <div class="sdot" v-for="i in Math.max(0, 5 - streakDays)" :key="'o' + i"></div>
          </div>
        </div>
      </div>

      <!-- 用户/账户行：点击切换账户 -->
      <AccountMenu :compact="appStore.sidebarCollapsed" />
    </aside>

    <!-- ── 主内容区（视图自带页头，无全局顶栏） ── -->
    <main class="sb-main">
      <router-view v-slot="{ Component }">
        <keep-alive :key="appStore.userId">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAccountsStore } from '@/stores/accounts'
import AccountMenu from '@/components/AccountMenu.vue'
import AccountFlow from '@/components/AccountFlow.vue'
import { useOnboardingStore } from '@/stores/onboarding'
import SIcon from '@/components/SIcon.vue'
import logoMark from '@/assets/lvyuan-logo.jpg'

const route = useRoute()
const appStore = useAppStore()
const accountsStore = useAccountsStore()
const onb = useOnboardingStore()
watch(() => accountsStore.userId, () => {
  if (accountsStore.isSignedIn) {
    if (onb.loadedUserId !== accountsStore.userId) void onb.load(accountsStore.userId)
  } else onb.clearSession()
}, { immediate: true })

// ── 侧栏导航项（SIcon 线性图标） ──
const navItems = [
  { path: '/app/home',      label: '首页',     icon: 'home' },
  { path: '/app/knowledge', label: '定制学习资源', icon: 'library' },
  { path: '/app/knowledge-tree', label: '知识技能树', icon: 'target' },
  { path: '/app/path',      label: '学习路线规划', icon: 'trend' },
  { path: '/app/training',  label: '训练场',   icon: 'swords' },
  { path: '/app/toolbox',   label: '工具箱',   icon: 'calc' },
  { path: '/app/profile',   label: '学情中心', icon: 'user' },
]

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}

// ── 用户信息（演示名 + 连续学习天数，占位逻辑） ──
const displayName = computed(() => '学员')
const userChar = computed(() => displayName.value.charAt(0))
const streakDays = computed(() => 3)

// ── 启动后端健康检查 ──
onMounted(() => { accountsStore.ensureAccounts(); appStore.startHealthCheck() })
onUnmounted(() => { appStore.stopHealthCheck() })
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.main-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: $color-bg;
}

// ── 侧栏（可伸缩 · 渐变黛蓝） ──
.sb {
  width: 232px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 18px 14px;
  gap: 12px;
  background: linear-gradient(165deg, #1C426E 0%, #338FF2 40%, #122E4F 100%);
  color: #fff;
  transition: width 0.22s ease, padding 0.22s ease;

  &.collapsed {
    width: 72px;
    padding: 18px 10px;

    .sb-brand { padding-bottom: 10px; }
    .sb-item { justify-content: center; padding: 11px 0; gap: 0; }
    .sb-user { justify-content: center; padding: 12px 0; }
  }
}

// ── 品牌区（官方 logo：图形 + 文字标 左右排列） ──
.sb-brand {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 6px 0 14px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  .sb-logo img {
    width: 40px;
    height: 39px;
    display: block;
    flex-shrink: 0;
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.25));
  }
  .sb-brand-text {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    min-width: 0;
    flex: 1;
  }
  .sb-name {
    font-family: $font-serif;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 3px;
    line-height: 1;
    white-space: nowrap;
    color: #F5FAFF;
  }
  .sb-sub {
    font-size: 9.5px;
    letter-spacing: 2.5px;
    line-height: 1;
    white-space: nowrap;
    color: rgba(51, 143, 242, 0.9);
  }

  // 收起态：仅 logo 居中（与导航图标垂直居中对齐）
  .sb.collapsed & {
    justify-content: center;
    align-items: center;
    padding: 6px 0 10px;
    gap: 0;
    width: 100%;
    .sb-logo {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
    }
    .sb-logo img { width: 38px; height: 37px; }
  }
}

// ── 伸缩按钮（品牌区内，文字标右侧） ──
.sb-collapse {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  transition: all 0.18s;

  &:hover { background: rgba(255, 255, 255, 0.15); color: #fff; border-color: rgba(255, 255, 255, 0.28); }
}

// ── 导航 ──
.sb-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.sb-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 14px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.72);
  text-decoration: none;
  transition: all 0.18s;
  position: relative;

  .t { font-size: 13.5px; font-weight: 500; white-space: nowrap; }
  .dot {
    margin-left: auto;
    width: 5px; height: 5px;
    border-radius: 50%;
    background: $color-accent;
  }

  &:hover { background: rgba(255, 255, 255, 0.07); color: #fff; }

  &.active {
    background: rgba(51, 143, 242, 0.16);
    color: $color-accent;
  }
}

// ── 连续学习卡 ──
.streak-card {
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.12);

  .streak-top {
    display: flex; align-items: center; gap: 6px;
    .label { font-size: 11px; color: rgba(255, 255, 255, 0.65); }
  }
  .streak-num {
    margin-top: 6px;
    .n { font-size: 24px; font-weight: 700; color: $color-accent; font-family: 'Liberation Mono', monospace; }
    .u { font-size: 11px; color: rgba(255, 255, 255, 0.6); margin-left: 3px; }
  }
  .streak-dots {
    display: flex; gap: 5px; margin-top: 8px;
    .sdot {
      width: 7px; height: 7px; border-radius: 50%;
      background: rgba(255, 255, 255, 0.18);
      &.on { background: $color-accent; }
    }
  }
}

// ── 用户信息 ──
.sb-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);

  .sb-av {
    position: relative;
    width: 36px; height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #338FF2, #A8893C);
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; font-weight: 700; color: #fff;
    flex-shrink: 0;

    .conn {
      position: absolute;
      right: -1px; bottom: -1px;
      width: 10px; height: 10px;
      border-radius: 50%;
      border: 2px solid #338FF2;
      background: #6B7280;
      &.on { background: #34D399; }
    }
  }
  .sb-un {
    flex: 1; min-width: 0;
    .n { font-size: 13px; font-weight: 600; color: #fff; }
    .d { font-size: 10px; color: rgba(255, 255, 255, 0.55); margin-top: 1px; }
  }
}

// ── 主内容区 ──
.sb-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
