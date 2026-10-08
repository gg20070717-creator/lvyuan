<template>
  <div class="lp-page">
    <header class="lp-head">
      <div class="lp-title">
        <h2>学习路线规划</h2>
        <span v-if="path" class="lp-ver">第 {{ path.version }} 版   {{ fmtTime(path.created_at) }}</span>
      </div>
      <div class="lp-modes">
        <button class="lp-mode" :class="{ on: mode === 'guided' }" @click="mode = 'guided'">导学模式</button>
        <button class="lp-mode" :class="{ on: mode === 'free' }" @click="mode = 'free'">自由浏览</button>
      </div>
      <div class="lp-page-nav" v-if="path">
        <button class="pg" :disabled="page <= 0" @click="page--"><SIcon name="back" :size="12" />上一页</button>
        <span class="pg-info">第 {{ page + 1 }} 页，共 {{ totalPages }} 页   {{ pageSkills.length }} 点</span>
        <button class="pg" :disabled="page >= totalPages - 1" @click="page++">下一页<SIcon name="right" :size="12" /></button>
      </div>
      <button class="lp-refresh" @click="load"><SIcon name="sparkle" :size="13" />刷新</button>
      <button v-if="path" class="lp-ask" @click="openAsk"><SIcon name="msg" :size="13" />向旅鸢提意见</button>
    </header>

    <!-- 向旅鸢提意见：旅鸢结合画像/掌握度重排路线，硬校验通过才落库 -->
    <div v-if="fbOpen" class="fb-mask" @click.self="closeAsk">
      <div class="fb-card">
        <div class="fb-title">向旅鸢提意见   调整学习路线</div>
        <div class="fb-sub">例如：“我想先学文化桥、日本游客接待”“把XX提前”“最近先补应急”——旅鸢会结合你的画像与掌握度重新排序，校验规范后生成新版路线。</div>
        <textarea v-model="fbText" class="fb-input" rows="3" placeholder="说说你想怎么调整学习顺序…" />
        <div class="fb-actions">
          <button class="fb-cancel" @click="closeAsk">取消</button>
          <button class="fb-go" :disabled="fbLoading || !fbText.trim()" @click="submitAsk">
            {{ fbLoading ? '旅鸢排路线中…' : '请旅鸢重新规划' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="lp-empty">正在加载学习路线…</div>
    <div v-else-if="!path" class="lp-empty">
      <p>还没有学习路线。请先在首页完成先验学情画像并生成学习路径。</p>
      <button class="lp-go-home" @click="$router.push('/app/home')">去首页生成</button>
    </div>

    <template v-else>
      <div class="lp-legend">
        <span><i class="dot full"></i>已点亮 100%</span>
        <span><i class="dot mid"></i>掌握中（≥60%）</span>
        <span><i class="dot low"></i>起步、未学</span>
        <span><i class="dot lock"></i>导学锁定</span>
        <span><i class="dot cur"></i>当前位置</span>
        <span class="lp-hint">按住空白拖动平移   点卡片查看、去学习</span>
      </div>

      <div class="lp-stage">
        <div class="lp-canvas" ref="canvasRef" :style="{ width: canvasW + 'px', height: canvasH + 'px' }"
          :class="{ panning }" @mousedown="onDown" @mousemove.prevent="onMove" @mouseup="onUp" @mouseleave="onUp">
          <svg class="lp-svg" :width="canvasW" :height="canvasH">
            <defs>
              <marker id="lpArrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#B8944F" />
              </marker>
            </defs>
            <path v-for="(d, i) in linkDs" :key="'e' + i" :d="d" class="lp-link" marker-end="url(#lpArrow)" />
          </svg>
          <div v-for="(sid, i) in pageSkills" :key="sid"
            class="pn-card" :class="{ locked: lockedOf(sid), cur: sid === currentSkillId, done: pct(mOf(sid)) >= 100 }"
            :style="cardStyle(i)" @click="onCard(sid)">
            <span class="pn-name">{{ nameOf(sid) }}</span>
            <span class="pn-pct">{{ pct(mOf(sid)) }}%</span>
            <SIcon v-if="lockedOf(sid)" name="lock" :size="10" class="pn-lk" />
          </div>
        </div>
        <div class="lp-pos" v-if="mode === 'guided' && currentSkillId">
          <SIcon name="target" :size="12" /> 当前位置：{{ nameOf(currentSkillId) }}
        </div>
      </div>

      <!-- 技能点详情抽屉（与知识技能树一致的口径） -->
      <transition name="fade"><div v-if="sel" class="lp-mask" @click="sel = null"></div></transition>
      <transition name="slide">
        <aside v-if="sel" class="lp-drawer">
          <div class="lp-drawer-top">
            <span class="lp-drawer-badge" :class="sel.lit ? 'on' : 'off'">{{ sel.lit ? '已点亮' : '待点亮' }}</span>
            <button class="lp-drawer-x" @click="sel = null"><SIcon name="x" :size="13" /></button>
          </div>
          <div class="lp-drawer-title">
            <span class="lp-drawer-ic"><SIcon name="circle" :size="16" /></span>
            <span>{{ sel.name }}</span>
          </div>
          <div class="lp-drawer-path">{{ sel.groupTitle || '学习路线规划' }}</div>
          <div class="lp-stats">
            <div class="st"><span class="v">{{ sel.linked_count }}</span><span class="k">关联技能点</span></div>
            <div class="st"><span class="v">{{ sel.qCount }}</span><span class="k">关联题目</span></div>
          </div>
          <div class="lp-bar-block">
            <div class="lb"><span>掌握度进度</span><span class="pct">{{ pct(sel.mastery) }}%</span></div>
            <div class="lp-bar"><u :style="{ width: pct(sel.mastery) + '%' }"></u></div>
          </div>
          <div class="lp-bar-block">
            <div class="lb"><span>掌握度构成</span><span class="pct">{{ pct(sel.mastery) }}%</span></div>
            <div class="br-row"><span>客观题</span><b>{{ roundBreak(sel.mastery_detail, 'objective') }}%</b></div>
            <div class="br-row"><span>管家评估</span><b>{{ roundBreak(sel.mastery_detail, 'concierge') }}%</b></div>
            <div class="br-row"><span>沙盒实战</span><b>{{ roundBreak(sel.mastery_detail, 'sandbox') }}%</b></div>
            <div class="br-row"><span>先验基线</span><b>{{ roundBreak(sel.mastery_detail, 'baseline') }}%</b></div>
          </div>
          <div class="lp-drawer-actions">
            <button v-if="!lockedOf(sel.id)" class="lp-go" @click="goLearn(sel.id)">去首页学习「{{ sel.name }}」</button>
            <div v-else class="lp-lock-hint">🔒 前一技能点掌握度 ≥60% 后解锁</div>
          </div>
        </aside>
      </transition>
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import SIcon from '@/components/SIcon.vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { getKnowledgeSkillTree, getSkillDetail } from '@/api/knowledge'
import type { KSTNode } from '@/api/knowledge'
import { getLatestLearningPath, planLearningPath } from '@/api/onboarding'
import type { LearningRoute } from '@/api/onboarding'

const store = useAppStore()
const router = useRouter()

// 分页画布：每页 7 列 × 10 行 = 70 个技能点
const COLS = 7
const ROWS = 10
const PER = COLS * ROWS
const COL_W = 206
const ROW_H = 84
const PAD = 30
const BOX_W = 158
const BOX_H = 36

const path = ref<{ version: number; created_at?: string; route: LearningRoute } | null>(null)
const loading = ref(true)
const mode = ref<'guided' | 'free'>('guided')
const page = ref(0)
const skillMap = ref<Map<string, KSTNode>>(new Map())
const beforeSet = ref<Set<string>>(new Set())
const seq = ref<string[]>([])
const learningSeq = ref<string[]>([])
const currentSkillId = ref('')
const sel = ref<any>(null)
const detailQ = ref<number>(0)
const canvasRef = ref<HTMLElement | null>(null)
const panning = ref(false)
const moved = ref(false)
const dragStart = ref<{ x: number; y: number; sl: number; st: number } | null>(null)
const fbOpen = ref(false)
const fbText = ref('')
const fbLoading = ref(false)

function openAsk() { fbOpen.value = true; fbText.value = '' }
function closeAsk() { if (!fbLoading.value) { fbOpen.value = false; fbText.value = '' } }
async function submitAsk() {
  const t = fbText.value.trim()
  if (!t || fbLoading.value) return
  fbLoading.value = true
  try {
    const r = await planLearningPath(store.userId, t)
    if (r && r.ok) {
      fbOpen.value = false
      fbText.value = ''
      ElMessage.success('旅鸢已按你的意见重新规划路线')
      await load()
    } else {
      ElMessage.warning((r && (r as any).error) || '你的意见未能通过规范校验，已保留原路线，请换个说法再试')
    }
  } catch (e: any) {
    ElMessage.error('规划失败：' + ((e && (e.message || e.detail)) || '请稍后再试'))
  } finally {
    fbLoading.value = false
  }
}

function pct(v: number | null | undefined): number {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return 0
  return Math.max(0, Math.min(100, Number(v)))
}
function mOf(id: string): number | null {
  const n = skillMap.value.get(id)
  return n && typeof n.mastery === 'number' ? n.mastery : null
}
function nameOf(id: string): string {
  return skillMap.value.get(id)?.name || id
}
function fmtTime(t?: string): string {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}
function collectSkills(nodes: KSTNode[] | undefined, map: Map<string, KSTNode>) {
  for (const n of nodes || []) {
    if (n.type === 'skill') map.set(n.id, n)
    if (n.children?.length) collectSkills(n.children, map)
  }
}

const totalPages = computed(() => Math.max(1, Math.ceil(seq.value.length / PER)))
const pageSkills = computed(() => {
  const s = page.value * PER
  return seq.value.slice(s, s + PER)
})

function posOf(local: number): { x: number; y: number } {
  const row = Math.floor(local / COLS)
  const k = local % COLS
  const col = row % 2 === 0 ? k : COLS - 1 - k
  return { x: PAD + BOX_W / 2 + col * COL_W, y: PAD + row * ROW_H }
}
const canvasW = computed(() => PAD * 2 + (COLS - 1) * COL_W + BOX_W)
const canvasH = computed(() => PAD * 2 + (ROWS - 1) * ROW_H + BOX_H)

function cardStyle(local: number): Record<string, string> {
  const p = posOf(local)
  const sid = pageSkills.value[local]
  const st: Record<string, string> = { left: p.x + 'px', top: p.y + 'px' }
  const v = pct(mOf(sid))
  const gold = '#F3E0AC' // 不透明淡金
  if (lockedOf(sid)) {
    st.background = '#F3EFE7' // 锁定：不透明浅卡纸色
    return st
  }
  if (sid === currentSkillId.value) { // 当前位置：白底 + 金环
    st.background = '#ffffff'
    return st
  }
  st.background = v >= 100
    ? `linear-gradient(90deg, ${gold} 0%, ${gold} 100%)`
    : `linear-gradient(90deg, ${gold} ${v}%, #ffffff ${v}%)`
  return st
}

const linkDs = computed<string[]>(() => {
  const out: string[] = []
  const GAP = 4 // 留出空隙，箭头在卡片之间、不被盖住
  for (let i = 0; i < pageSkills.value.length - 1; i++) {
    const a = posOf(i); const b = posOf(i + 1)
    const row = Math.floor(i / COLS)
    const nextRow = Math.floor((i + 1) / COLS)
    if (row === nextRow) {
      // 行内（分左右方向，箭头始终落在两卡之间的空隙、不穿过卡片）
      if (b.x > a.x) {
        out.push(`M ${a.x + BOX_W / 2 + GAP} ${a.y} L ${b.x - BOX_W / 2 - GAP} ${b.y}`)
      } else {
        out.push(`M ${a.x - BOX_W / 2 - GAP} ${a.y} L ${b.x + BOX_W / 2 + GAP} ${b.y}`)
      }
    } else {
      // 换行：从上卡下缘到下卡上缘（箭头在竖向空隙）
      const gapY = (ROW_H - BOX_H) / 2
      out.push(`M ${a.x} ${a.y + BOX_H / 2 + GAP} L ${a.x} ${a.y + gapY} L ${a.x} ${b.y - gapY} L ${a.x} ${b.y - BOX_H / 2 - GAP}`)
    }
  }
  return out
})

function unlockedOf(sid: string): boolean {
  if (mode.value === 'free') return true
  if (beforeSet.value.has(sid)) return true
  const i = learningSeq.value.indexOf(sid)
  if (i <= 0) return true
  return pct(mOf(learningSeq.value[i - 1])) >= 60
}
function lockedOf(sid: string): boolean {
  return mode.value === 'guided' && !beforeSet.value.has(sid) && !unlockedOf(sid)
}

function pageOf(sid: string): number {
  const i = seq.value.indexOf(sid)
  return i < 0 ? 0 : Math.floor(i / PER)
}

async function load() {
  loading.value = true
  sel.value = null
  try {
    const lp = await getLatestLearningPath(store.userId)
    if (!lp.found || !lp.route) { path.value = null; return }
    path.value = { version: lp.version!, created_at: lp.created_at, route: lp.route! }
    const route = lp.route
    beforeSet.value = new Set(route.before_start_skill_ids || [])
    seq.value = [...(route.before_start_skill_ids || []), ...(route.path_skill_ids || [])]
    learningSeq.value = route.path_skill_ids || []
    try {
      const tree = await getKnowledgeSkillTree(store.userId)
      const map = new Map<string, KSTNode>()
      collectSkills(tree.branches, map)
      skillMap.value = map
    } catch { skillMap.value = new Map() }
    const ls = learningSeq.value
    let cur = ''
    for (let i = 0; i < ls.length; i++) {
      const sid = ls[i]
      const un = i === 0 || pct(mOf(ls[i - 1])) >= 60
      if (un && pct(mOf(sid)) < 100) { cur = sid; break }
    }
    currentSkillId.value = cur
    page.value = cur ? pageOf(cur) : 0
    await nextTick()
  } finally {
    loading.value = false
  }
}

watch(page, () => { sel.value = null })

// 画布拖拽平移
function onDown(e: MouseEvent) {
  dragStart.value = { x: e.clientX, y: e.clientY, sl: canvasRef.value?.scrollLeft ?? 0, st: canvasRef.value?.scrollTop ?? 0 }
  moved.value = false
  panning.value = true
}
function onMove(e: MouseEvent) {
  if (!panning.value || !dragStart.value || !canvasRef.value) return
  const dx = e.clientX - dragStart.value.x
  const dy = e.clientY - dragStart.value.y
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved.value = true
  canvasRef.value.scrollLeft = dragStart.value.sl - dx
  canvasRef.value.scrollTop = dragStart.value.st - dy
}
function onUp() {
  panning.value = false
  window.setTimeout(() => { moved.value = false }, 0)
}

async function onCard(sid: string) {
  if (moved.value) return
  const n = skillMap.value.get(sid)
  if (!n) return
  detailQ.value = 0
  try {
    const d = await getSkillDetail(sid)
    detailQ.value = d.questions?.length || 0
  } catch { /* ignore */ }
  sel.value = {
    id: sid,
    name: n.name || sid,
    lit: !!n.lit,
    linked_count: n.linked_count ?? 0,
    qCount: detailQ.value,
    mastery: typeof n.mastery === 'number' ? n.mastery : 0,
    mastery_detail: n.mastery_detail || {},
    groupTitle: '',
  }
}

function goLearn(sid: string) {
  const n = skillMap.value.get(sid)
  const sessionId = store.sessionForSkill(sid)
  store.activateSession(sessionId)
  router.push({ path: '/app/home', query: { learn: sid } })
  sel.value = null
}

function roundBreak(detail: Record<string, any> | undefined, key: string): number {
  const v = detail?.[key]
  if (typeof v === 'number') return Math.round(v)
  if (typeof v === 'string') return Math.round(Number(v) || 0)
  return 0
}

onMounted(load)
</script>
<style lang="scss" scoped>
@use '@/styles/tokens-legacy' as *;

.lp-page { height: 100%; display: flex; flex-direction: column; overflow: hidden; background: $color-bg; }
.lp-head { display: flex; align-items: center; gap: 14px; padding: 10px 18px; background: #fff; border-bottom: 1px solid $color-border; flex-wrap: wrap;
  .lp-title { display: flex; align-items: baseline; gap: 8px; h2 { margin: 0; font-size: 17px; color: $color-text; } .lp-ver { font-size: 11.5px; color: $color-text-secondary; } }
  .lp-modes { display: inline-flex; border: 1px solid $color-border; border-radius: 999px; overflow: hidden;
    .lp-mode { border: none; background: #fff; padding: 5px 14px; font-size: 12.5px; color: $color-text-secondary; cursor: pointer;
      &.on { background: $color-primary; color: #fff; } } }
  .lp-page-nav { display: inline-flex; align-items: center; gap: 8px; margin-left: auto;
    .pg { border: 1px solid $color-border; background: #fff; color: $color-primary; border-radius: 999px; padding: 5px 12px; font-size: 12.5px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; &:disabled { opacity: .45; cursor: not-allowed; } &:hover:not(:disabled) { background: $color-accent-light; } }
    .pg-info { font-size: 12px; color: $color-text-secondary; } }
  .lp-refresh { border: 1px solid $color-border; background: #fff; border-radius: 999px; padding: 5px 12px; color: $color-primary; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
}
.lp-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: $color-text-secondary;
  .lp-go-home { background: $color-primary; color: #fff; border: none; border-radius: 999px; padding: 8px 20px; cursor: pointer; } }
.lp-legend { display: flex; gap: 16px; align-items: center; font-size: 12px; color: $color-text-secondary; padding: 8px 18px 0; flex-wrap: wrap;
  .dot { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 5px; vertical-align: -1px;
    &.full { background: #F3E0AC; border: 1px solid #e2c27f; } &.mid { background: #fff; border: 1px solid $color-border; }
    &.low { background: #fff; border: 1px solid $color-border; } &.lock { background: $color-muted-bg; }
    &.cur { background: $color-primary; border-radius: 50%; box-shadow: 0 0 0 3px rgba(24,58,99,.18); } }
  .lp-hint { margin-left: auto; color: $color-text-secondary; font-size: 12px; } }

.lp-stage { position: relative; flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; padding: 10px 16px 4px; }
.lp-canvas { position: relative; overflow: auto; border: 1px solid $color-border; border-radius: 12px; background:
  radial-gradient(circle at 1px 1px, rgba(24,58,99,.045) 1px, transparent 0) 0 0/22px 22px, #fff; cursor: grab;
  &.panning { cursor: grabbing; } }
.lp-svg { position: absolute; top: 0; left: 0; z-index: 0; pointer-events: none; }
.lp-link { fill: none; stroke: #C9A86A; stroke-width: 3.2; opacity: .95; }
.lp-pos { position: absolute; bottom: 14px; left: 50%; transform: translateX(-50%); background: $color-primary; color: #fff; font-size: 12px; padding: 5px 14px; border-radius: 999px; display: inline-flex; align-items: center; gap: 6px; z-index: 5; box-shadow: $shadow-card; }

.pn-card { position: absolute; transform: translate(-50%, -50%); z-index: 1;
  width: 158px; height: 36px; display: flex; align-items: center; gap: 6px;
  border: 1.5px solid rgba(24,58,99,.22); border-radius: 10px; padding: 0 10px;
  box-shadow: 0 1px 3px rgba(24,58,99,.08); cursor: pointer; color: $color-primary; font-size: 12px;
  background: #fff; transition: box-shadow .15s, transform .12s;
  &:hover { box-shadow: $shadow-card-hover; transform: translate(-50%, -50%) translateY(-1px); }
  .pn-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
  .pn-pct { font-size: 11px; color: $color-primary; font-weight: 800; flex-shrink: 0; }
  .pn-lk { color: $color-text-secondary; flex-shrink: 0; }
  &.locked { opacity: 1; border-style: dashed; }
  &.done { border-color: $color-accent; }
  &.cur { border-color: $color-accent; box-shadow: 0 0 0 4px rgba(201,168,106,.85), $shadow-card-hover; background: #fff; }
}

.lp-mask { position: fixed; inset: 0; background: rgba(10,25,41,.35); z-index: 60; }
.lp-drawer { position: fixed; top: 0; right: 0; bottom: 0; width: 340px; max-width: 94vw; background: #fff; z-index: 61; box-shadow: -8px 0 30px rgba(0,0,0,.15); padding: 16px 18px; overflow-y: auto;
  .lp-drawer-top { display: flex; align-items: center; margin-bottom: 10px; }
  .lp-drawer-badge { font-size: 11px; padding: 2px 10px; border-radius: 999px; font-weight: 600;
    &.on { background: rgba(201,168,106,.18); color: #8a6d2f; } &.off { background: $color-secondary-bg; color: $color-text-secondary; } }
  .lp-drawer-x { margin-left: auto; border: none; background: none; cursor: pointer; color: $color-text-secondary; }
  .lp-drawer-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 800; color: $color-text;
    .lp-drawer-ic { color: $color-primary; } }
  .lp-drawer-path { font-size: 12px; color: $color-text-secondary; margin: 4px 0 12px; }
  .lp-stats { display: flex; gap: 8px; margin-bottom: 12px; .st { flex: 1; background: $color-secondary-bg; border-radius: 8px; text-align: center; padding: 6px 4px; .v { display: block; font-size: 15px; font-weight: 800; color: $color-primary; } .k { font-size: 10.5px; color: $color-text-secondary; } } }
  .lp-bar-block { margin-bottom: 10px;
    .lb { display: flex; justify-content: space-between; font-size: 12px; color: $color-text-secondary; margin-bottom: 4px; .pct { color: $color-primary; font-weight: 700; } }
    .lp-bar { height: 10px; border-radius: 999px; background: $color-muted-bg; overflow: hidden; u { display: block; height: 100%; background: linear-gradient(90deg, $color-primary, $color-accent); border-radius: 999px; } }
    .br-row { display: flex; justify-content: space-between; font-size: 12.5px; color: $color-text-secondary; padding: 3px 0; b { color: $color-text; } } }
  .lp-drawer-actions { margin-top: 12px; .lp-go { width: 100%; background: $color-primary; color: #fff; border: none; border-radius: 999px; padding: 11px 14px; cursor: pointer; font-size: 13px; } .lp-lock-hint { font-size: 12.5px; color: $color-text-secondary; } } }

.fade-enter-active, .fade-leave-active { transition: opacity .18s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.slide-enter-active, .slide-leave-active { transition: transform .2s; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }

/* 向旅鸢提意见弹窗 */
.lp-ask { border: 1px solid rgba(201,168,106,.45); background: rgba(201,168,106,.12); color: #8A6D2F;
  border-radius: 10px; padding: 8px 14px; font-size: 12.5px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
.lp-ask:hover { background: rgba(201,168,106,.2); }
.fb-mask { position: fixed; inset: 0; background: rgba(15,23,32,.45); z-index: 99; display: flex; align-items: center; justify-content: center; padding: 20px; }
.fb-card { background: #fffdf8; border-radius: 16px; max-width: 560px; width: 100%; padding: 20px 22px; box-shadow: 0 18px 50px rgba(0,0,0,.25); }
.fb-title { font-size: 16px; font-weight: 700; color: #183A63; }
.fb-sub { font-size: 12px; color: #8a816e; line-height: 1.7; margin: 6px 0 12px; }
.fb-input { width: 100%; border: 1px solid #d9d0bf; border-radius: 10px; padding: 10px 12px; font-size: 13px; resize: none; outline: none; background: #fff; }
.fb-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }
.fb-go { border: 0; border-radius: 10px; padding: 9px 18px; font-size: 13.5px; cursor: pointer; background: linear-gradient(135deg, #C9A86A, #b28c46); color: #fff; }
.fb-go:disabled { opacity: .55; cursor: not-allowed; }

.fb-cancel { border: 1px solid #d9d0bf; background: #fff; color: #6b6455; border-radius: 10px;
  padding: 9px 18px; font-size: 13.5px; cursor: pointer; transition: all .15s; }
.fb-cancel:hover { border-color: #C9A86A; color: #8A6D2F; background: rgba(201,168,106,.08); }

</style>
