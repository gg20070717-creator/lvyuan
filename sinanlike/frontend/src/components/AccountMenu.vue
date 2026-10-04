<template>
  <div class="acm">
    <button class="acm-user" @click.stop="open = !open" :title="'当前用户：' + store.currentName()">
      <span class="acm-av">{{ char }}
        <i class="conn" :class="{ on: app.backendOnline }"
          :title="app.backendOnline ? '后端已连接' : '离线 · 演示模式'"></i>
      </span>
      <span class="acm-txt">
        <span class="n">{{ store.currentName() }}</span>
        <span class="d">切换 / 新建 / 删除用户</span>
      </span>
      <SIcon class="chev" :name="open ? 'up' : 'right'" :size="11" />
    </button>

    <div v-if="open" class="acm-panel">
      <template v-if="!showNew">
        <div class="acm-title">切换用户</div>
        <button v-for="a in store.accounts" :key="a.id" class="acm-item"
          :class="{ cur: a.id === store.activeId }" @click.stop="pick(a.id)">
          <span class="acm-item-av">{{ (a.name || '账').charAt(0) }}</span>
          <span class="acm-item-name">{{ a.name }}</span>
          <span v-if="a.id === store.activeId" class="acm-cur">当前</span>
        </button>
        <div class="acm-actions">
          <button class="acm-act primary" @click.stop="showNew = true"><SIcon name="plus" :size="12" />新建用户</button>
          <button class="acm-act danger" @click.stop="onClear"><SIcon name="x" :size="12" />清空本用户数据</button>
          <button class="acm-act danger" @click.stop="onRemove"><SIcon name="x" :size="12" />删除本用户</button>
        </div>
        <div class="acm-tip">每个用户的画像、进度、错题、会话、路线互相独立。新建可选择内置「测试画像」一键演示，或从 0 开始。</div>
      </template>

      <template v-else>
        <div class="acm-title">新建用户 · 选择初始画像</div>
        <button class="acm-tpl" @click.stop="onPickProfile(null)">
          <span class="acm-tpl-em">✨</span>
          <span class="acm-tpl-t">
            <b>从 0 开始</b>
            <i>空白账户，进入后完成先验学情画像</i>
          </span>
        </button>
        <button v-for="tp in TEST_PROFILES" :key="tp.id" class="acm-tpl" @click.stop="onPickProfile(tp)">
          <span class="acm-tpl-em">{{ tp.emoji }}</span>
          <span class="acm-tpl-t">
            <b>{{ tp.label }}</b>
            <i>{{ tp.desc }}</i>
          </span>
        </button>
        <div class="acm-actions">
          <button class="acm-act" @click.stop="showNew = false"><SIcon name="back" :size="12" />返回账户列表</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import SIcon from '@/components/SIcon.vue'
import { useAppStore } from '@/stores/app'
import { useAccountsStore } from '@/stores/accounts'
import { TEST_PROFILES } from '@/data/testProfiles'
import type { TestProfile } from '@/data/testProfiles'

const store = useAccountsStore()
const app = useAppStore()
const open = ref(false)
const showNew = ref(false)

const char = computed(() => {
  const n = store.currentName() || '账'
  return n.charAt(0)
})

function pick(id: string) {
  if (id === store.activeId) { open.value = false; return }
  open.value = false
  store.switchTo(id)
}

function onPickProfile(tp: TestProfile | null) {
  open.value = false
  showNew.value = false
  void store.createAccount({ name: tp ? `测试·${tp.label}` : undefined, answers: tp?.answers })
}

async function onClear() {
  open.value = false
  try {
    await ElMessageBox.confirm(
      '将永久删除当前用户在服务器上积累的画像/进度/错题/会话/学习路径等全部数据，并回到初始引导。确定清空吗？',
      '清空本用户数据',
      { type: 'warning', confirmButtonText: '清空并重来', cancelButtonText: '取消' },
    )
  } catch { return }
  store.clearCurrent()
}

async function onRemove() {
  open.value = false
  try {
    await ElMessageBox.confirm(
      '将删除本用户：服务端该账户的全部数据会被清除，且该账户会从列表移除（若只剩它，会自动新建“账户 1”）。确定删除吗？',
      '删除本用户',
      { type: 'warning', confirmButtonText: '删除账户', cancelButtonText: '取消' },
    )
  } catch { return }
  await store.removeCurrent()
}

const onClickOutside = (e: MouseEvent) => {
  const el = document.querySelector('.acm-panel')
  if (el && !el.contains(e.target as Node)) { open.value = false; showNew.value = false }
}
onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.acm { position: relative; padding: 0 8px 10px; }
.acm-user { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 6px; background: transparent; border: none; border-radius: 10px; cursor: pointer; color: $color-text; text-align: left;
  &:hover { background: rgba(255,255,255,.08); }
  .acm-av { position: relative; width: 30px; height: 30px; border-radius: 50%; background: linear-gradient(135deg, $color-accent, $color-accent-d15); color: #fff; font-size: 14px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
    .conn { position: absolute; right: -1px; bottom: -1px; width: 9px; height: 9px; border-radius: 50%; border: 2px solid #fff; background: #c0504d; &.on { background: #3da35a; } } }
  .acm-txt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px;
    .n { font-size: 13px; font-weight: 700; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .d { font-size: 10.5px; color: rgba(255,255,255,.6); white-space: nowrap; } }
  .chev { color: rgba(255,255,255,.7); flex-shrink: 0; } }

.acm-panel { position: absolute; bottom: calc(100% + 6px); left: 8px; right: 8px; max-height: 70vh; overflow-y: auto; background: #fff; border: 1px solid $color-border; border-radius: 12px; box-shadow: $shadow-card-hover; padding: 10px; z-index: 90;
  .acm-title { font-size: 11px; color: $color-text-secondary; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
  .acm-item { display: flex; align-items: center; gap: 8px; width: 100%; padding: 7px 8px; border: none; background: none; border-radius: 8px; cursor: pointer; text-align: left;
    &:hover { background: $color-secondary-bg; }
    &.cur { background: $color-accent-light; }
    .acm-item-av { width: 20px; height: 20px; border-radius: 50%; background: $color-primary; color: #fff; font-size: 11px; display: flex; align-items: center; justify-content: center; }
    .acm-item-name { font-size: 13px; color: $color-text; }
    .acm-cur { margin-left: auto; font-size: 11px; color: $color-accent-d15; font-weight: 600; } }
  .acm-tpl { display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 8px; border: 1px solid $color-border; background: #fff; border-radius: 10px; cursor: pointer; text-align: left; margin-bottom: 6px;
    &:hover { border-color: $color-accent; background: $color-accent-light; }
    .acm-tpl-em { font-size: 20px; width: 28px; text-align: center; flex-shrink: 0; }
    .acm-tpl-t { display: flex; flex-direction: column; gap: 2px;
      b { font-size: 13px; color: $color-text; }
      i { font-style: normal; font-size: 11px; color: $color-text-secondary; } } }
  .acm-actions { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; border-top: 1px solid $color-border; padding-top: 8px;
    .acm-act { display: inline-flex; align-items: center; gap: 6px; border: none; border-radius: 8px; padding: 7px 10px; font-size: 12.5px; cursor: pointer; text-align: left;
      &.primary { background: $color-primary; color: #fff; } &.danger { background: #fdeeee; color: #c0504d; } } }
  .acm-tip { margin-top: 8px; font-size: 11px; color: $color-text-secondary; line-height: 1.6; } }
</style>