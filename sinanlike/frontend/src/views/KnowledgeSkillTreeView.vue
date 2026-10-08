<template>
  <div class="kst-page">
    <div class="kst-inner">
      <header class="ph">
        <div class="ph-left">
          <h2 class="ph-title">知识学习</h2>
          <p class="ph-desc">按具体知识点学习、做题，查看每项技能的掌握情况</p>
        </div>
        <div class="ph-right"><span class="pill">已点亮 {{ litCount }} 个，共 {{ totalNodes }} 个</span></div>
      </header>

      <div class="kst-counts">
        <div class="c"><b>{{ counts.books }}</b><span>知识域</span></div>
        <div class="c"><b>{{ counts.parts }}</b><span>分组</span></div>
        <div class="c"><b>{{ counts.chapters }}</b><span>维度</span></div>
        <div class="c"><b>{{ counts.sections }}</b><span>主题</span></div>
        <div class="c"><b>{{ counts.skills }}</b><span>技能点</span></div>
      </div>

      <div class="kst-search">
        <SIcon name="search" :size="15" color="#70869B" />
        <input v-model="q" class="kst-input"
          placeholder="输入节点名检索，如：免签240小时产品设计、外卡支付、客诉处理"
          @keyup.enter="doSearch" />
        <el-button size="small" type="primary" :loading="searching" @click="doSearch">检索</el-button>
      </div>
      <div v-if="results.length" class="kst-results">
        <div v-for="r in results" :key="r.id" class="rs-item" @click="expandTo(r)">
          <SIcon name="link" :size="12" color="#338FF2" />
          <span class="rs-path">{{ r.path.slice(1).join('、') }}</span>
          <span class="rs-cnt">{{ r.skills.length }} 技能点</span>
        </div>
      </div>

      <!-- 总览 -->
      <section class="ov-tree" v-loading="loading">
        <svg class="ov-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
          <path v-for="(b, i) in tree" :key="'ovl-' + b.id" :d="`M 50 10 C 50 30, ${ovPos(i).x} ${ovPos(i).y - 14}, ${ovPos(i).x} ${ovPos(i).y}`"
            class="ov-line" :class="{ on: activeDomain && activeDomain.id === b.id }" />
        </svg>
        <div class="ov-core"><SIcon name="globe" :size="15" color="#FFFFFF" /><span>知识学习</span></div>
        <button v-for="(b, i) in tree" :key="'ovn-' + b.id" class="ov-branch"
          :class="{ on: activeDomain && activeDomain.id === b.id }"
          :style="{ left: ovPos(i).x + '%', top: ovPos(i).y + '%' }" @click="selectDomain(b)">
          <span class="ob-ic"><SIcon :name="iconOf(b.type)" :size="14" /></span>
          <span class="ob-name">{{ b.name }}</span>
        </button>
        <div class="ov-hint"><SIcon name="sparkle" :size="11" color="#338FF2" /> 点击知识域展开思维导图</div>
      </section>

      <!-- 展开域：整齐树（叶子固定间距，父节点居中于子节点） -->
      <section v-if="activeDomain" class="sub-tree">
        <div class="sub-head">
          <span class="sub-ic"><SIcon :name="iconOf(activeDomain.type)" :size="15" /></span>
          <h3 class="sub-title">{{ activeDomain.name }}</h3>
          <span class="sub-meta">{{ domainLit }}   {{ activeDomain.linked_count }} 关联技能点</span>
        </div>
        <div class="sub-canvas" ref="canvasRef" :class="{ panning }"
          @mousedown="onCanvasDown" @mousemove.prevent="onCanvasMove" @mouseup="onCanvasUp" @mouseleave="onCanvasUp">
          <div class="sub-inner" :style="{ width: canvasW + 'px', height: canvasH + 'px' }">
            <svg class="sub-svg" :width="canvasW" :height="canvasH">
              <path v-for="v in visible.filter(o => o.depth > 0)" :key="'e-' + v.node.id" :d="linkOf(v)"
                class="sub-line" :class="{ on: v.node.lit }" />
            </svg>
            <div v-for="v in visible" :key="'n-' + v.node.id" class="sb-node"
              :class="[v.node.type, { lit: v.node.lit, sel: selV && selV.node.id === v.node.id }]"
              :style="nodeStyle(v)" @click="onNodeClick(v)">
              <span class="sn-status">
                <SIcon v-if="v.node.lit" name="check" :size="11" color="#338FF2" />
                <SIcon v-else name="lock" :size="10" color="#B5B0A6" />
              </span>
              <span class="sn-ic"><SIcon :name="iconOf(v.node.type)" :size="13" /></span>
              <span class="sn-name">{{ v.node.name }}</span>
              <span class="sn-pct">{{ Math.round(v.node.mastery ?? 0) }}%</span>
              <span class="sn-exp" v-if="v.node.children && v.node.children.length">
                <SIcon :name="expanded.has(v.node.id) ? 'up' : 'right'" :size="10" />
              </span>
            </div>
          </div>
        </div>
        <div class="sub-legend">
          <span class="lg"><i class="dot lit"></i>完全点亮（100%）</span>
          <span class="lg"><i class="dot mid"></i>掌握中（50-99%）</span>
          <span class="lg"><i class="dot low"></i>起步（1-49%）</span>
          <span class="lg"><i class="dot line"></i>连接线</span>
        </div>
      </section>
    </div>

    <!-- 节点详情 -->
    <div v-if="selV" class="st-mask" @click.self="selV = null"></div>
    <aside class="st-drawer" :class="{ open: !!selV }">
      <template v-if="selV">
        <div class="sd-head">
          <span class="sd-badge" :class="selV.node.lit ? 'on' : 'off'">
            {{ selV.node.lit ? '已点亮' : '待点亮' }}</span>
          <button class="sd-x" @click="selV = null"><SIcon name="x" :size="13" /></button>
        </div>
        <div class="sd-title-row">
          <span class="sd-ic"><SIcon :name="iconOf(selV.node.type)" :size="18" /></span>
          <h3 class="sd-title">{{ domainName }}   {{ selV.node.name }}</h3>
        </div>
        <p class="sd-desc">{{ typeDesc(selV.node) }}</p>

        <div class="sd-stats">
          <div class="st"><span class="v">{{ selV.depth + 1 }}</span><span class="k">层级</span></div>
          <div class="st"><span class="v">{{ selV.node.linked_count }}</span><span class="k">关联技能点</span></div>
          <div class="st"><span class="v">{{ qCount }}</span><span class="k">关联题目</span></div>
        </div>

        <div class="sd-prog">
          <div class="lb"><span>掌握度进度</span><span class="pct">{{ selV.node.mastery ?? 0 }}%</span></div>
          <div class="bar"><div class="fill" :style="{ width: (selV.node.mastery ?? 0) + '%' }"></div></div>
        </div>

        <div v-if="selV.node.mastery_detail" class="sd-break">
          <div class="lb"><span>掌握度构成</span><span class="pct">{{ selV.node.mastery_detail.mastery ?? 0 }}%</span></div>
          <div class="br-row"><span>客观题</span><b>{{ selV.node.mastery_detail.objective ?? 0 }}%</b>
            <em v-if="selV.node.mastery_detail.objective_total">（已完成 {{ selV.node.mastery_detail.objective_done ?? 0 }} 题，共 {{ selV.node.mastery_detail.objective_total }} 题）</em></div>
          <div class="br-row"><span>管家评估</span><b>{{ selV.node.mastery_detail.concierge ?? 0 }}%</b></div>
          <div class="br-row"><span>沙盒实战</span><b>{{ selV.node.mastery_detail.sandbox ?? 0 }}%</b></div>
        </div>

        <div v-if="selV.node.lit" class="sd-reason">
          <SIcon name="check" :size="13" :stroke-width="3" /> {{ selV.node.reason || '掌握度自动达标' }}
        </div>
        <div v-else class="sd-pending">
          <SIcon name="clock" :size="13" /> 在首页让旅鸢讲这个技能、去训练场练到掌握，节点会自动点亮
        </div>

        <button class="sd-learn" @click="goLearn(selV.node.id)">
          <SIcon name="msg" :size="13" color="#fff" /> 去首页学习「{{ selV.node.name }}」
        </button>
      </template>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import SIcon from '@/components/SIcon.vue'
import { useAppStore } from '@/stores/app'
import {
  getKnowledgeSkillTree, treeSearch, getSkillDetail,
  type KSTNode, type TreeSearchResult, type SkillDetail,
} from '@/api/knowledge'

const store = useAppStore()
const router = useRouter()
const loading = ref(false)
const searching = ref(false)
const tree = ref<KSTNode[]>([])
const counts = ref({ books: 0, parts: 0, chapters: 0, sections: 0, skills: 0 })
const activeDomain = ref<KSTNode | null>(null)
const expanded = ref<Set<string>>(new Set())
const q = ref('')
const results = ref<TreeSearchResult[]>([])
const selV = ref<VNode | null>(null)
const detail = ref<SkillDetail | null>(null)
const canvasRef = ref<HTMLElement | null>(null)
const panning = ref(false)
const moved = ref(false)
const dragStart = ref<{ x: number; y: number; sl: number; st: number } | null>(null)

// ── 画布拖动平移（按住空白/卡片拖动画布，像思维导图工具） ──
function onCanvasDown(e: MouseEvent) {
  dragStart.value = { x: e.clientX, y: e.clientY, sl: canvasRef.value?.scrollLeft ?? 0, st: canvasRef.value?.scrollTop ?? 0 }
  moved.value = false
  panning.value = true
}
function onCanvasMove(e: MouseEvent) {
  if (!panning.value || !dragStart.value || !canvasRef.value) return
  const dx = e.clientX - dragStart.value.x
  const dy = e.clientY - dragStart.value.y
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved.value = true
  canvasRef.value.scrollLeft = dragStart.value.sl - dx
  canvasRef.value.scrollTop = dragStart.value.st - dy
}
function onCanvasUp() {
  panning.value = false
  window.setTimeout(() => { moved.value = false }, 0)
}

const iconOf = (t: string) =>
  ({ book: 'book', part: 'star', chapter: 'filetext', section: 'link', skill: 'circle' }[t] || 'circle')

// ── 布局常量 ──
const COL_W = 240
const ROW_H = 64
const PAD = 28
const BOX_W = 190
const BOX_H = 34

function ovPos(i: number): { x: number; y: number } {
  if (i < 4) return { x: 20 + i * 20, y: 45 }
  return { x: 30 + (i - 4) * 20, y: 78 }
}

interface VNode { node: KSTNode; depth: number; parent?: VNode }
const visible = computed<VNode[]>(() => {
  const out: VNode[] = []
  const walk = (nodes: KSTNode[], depth: number, parent?: VNode) => {
    for (const n of nodes) {
      const v: VNode = { node: n, depth, parent }
      out.push(v)
      if (n.children?.length && expanded.value.has(n.id)) walk(n.children, depth + 1, v)
    }
  }
  if (activeDomain.value) walk([activeDomain.value], 0)
  return out
})

// ── 整齐树布局：叶子固定间距，父节点 y = 子节点中点 ──
const layoutMap = computed(() => {
  const map = new Map<string, { x: number; y: number }>()
  let nextY = PAD
  const layout = (v: VNode, depth: number) => {
    const kids = visible.value.filter(o => o.parent === v)
    if (!kids.length) {
      map.set(v.node.id, { x: PAD + BOX_W / 2 + depth * COL_W, y: nextY })
      nextY += ROW_H
      return
    }
    for (const k of kids) layout(k, depth + 1)
    const first = map.get(kids[0].node.id)!
    const last = map.get(kids[kids.length - 1].node.id)!
    map.set(v.node.id, { x: PAD + BOX_W / 2 + depth * COL_W, y: (first.y + last.y) / 2 })
  }
  if (activeDomain.value) {
    const root = visible.value.find(v => v.depth === 0)
    if (root) layout(root, 0)
  }
  return map
})

const maxDepth = computed(() => visible.value.reduce((m, v) => Math.max(m, v.depth), 0))
const canvasW = computed(() => maxDepth.value * COL_W + BOX_W + PAD * 2 + BOX_W)
const canvasH = computed(() => {
  let maxY = 0
  layoutMap.value.forEach(p => { maxY = Math.max(maxY, p.y) })
  return maxY + BOX_H / 2 + PAD
})

function nodeStyle(v: VNode): Record<string, string> {
  const p = layoutMap.value.get(v.node.id)!
  const st: Record<string, string> = { left: p.x + 'px', top: p.y + 'px' }
  if (selV.value && selV.value.node.id === v.node.id) return st
  const pct = Math.min(100, Math.max(0, v.node.mastery ?? 0))
  // 整个框 = 进度条：左侧淡金按百分比填充(不透明硬切)，其余透白
  const gold = '#DCEEFF'
  st.background = pct >= 100
    ? `linear-gradient(90deg, ${gold} 0%, ${gold} 100%)`
    : `linear-gradient(90deg, ${gold} ${pct}%, #ffffff ${pct}%)`
  return st
}


function linkOf(v: VNode): string {
  if (!v.parent) return ''
  // 卡片中心定位（translate(-50%,-50%)），连线直接对准中心
  const p = layoutMap.value.get(v.parent.node.id)!
  const c = layoutMap.value.get(v.node.id)!
  const mx = (p.x + c.x) / 2
  return `M ${p.x} ${p.y} C ${mx} ${p.y}, ${mx} ${c.y}, ${c.x} ${c.y}`
}

const totalNodes = computed(() => visible.value.length)
const litCount = computed(() => visible.value.filter(v => v.node.lit).length)
const domainLit = computed(() => (activeDomain.value?.lit ? '已点亮' : '未点亮'))
const domainName = computed(() => (selV.value ? activeDomain.value?.name ?? '' : ''))
const qCount = computed(() => {
  if (selV.value?.node.type === 'skill') return detail.value ? detail.value.questions.length : '…'
  return '—'
})
const typeDesc = (n: KSTNode) => {
  const t = { book: '知识域', part: '分组', chapter: '维度', section: '主题', skill: '技能点' }[n.type] || '节点'
  return `${t}   ${n.linked_count} 个关联技能点`
}

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await getKnowledgeSkillTree(store.userId)
    tree.value = res.branches ?? []
    counts.value = res.counts ?? counts.value
    if (tree.value.length) selectDomain(tree.value[0])
  } catch {
    ElMessage.error('知识学习加载失败，请确认后端已启动')
  } finally {
    loading.value = false
  }
}

function selectDomain(b: KSTNode) {
  activeDomain.value = b
  expanded.value = new Set([b.id])
  selV.value = null
  detail.value = null
}

function onNodeClick(v: VNode) {
  if (moved.value) return   // 刚拖动过画布，忽略本次点击
  if (v.node.type === 'skill') {
    openSkill(v)
    return
  }
  const s = new Set(expanded.value)
  if (s.has(v.node.id)) s.delete(v.node.id)
  else s.add(v.node.id)
  expanded.value = s
}

async function doSearch() {
  const query = q.value.trim()
  if (!query) return
  searching.value = true
  try {
    const res = await treeSearch(query)
    results.value = res.results ?? []
    if (!results.value.length) ElMessage.info('未命中知识库节点，可尝试输入主题、章节名')
  } catch {
    ElMessage.error('检索失败')
  } finally {
    searching.value = false
  }
}

function expandTo(r: TreeSearchResult) {
  const bookTitle = r.path[1] ?? r.path[0]
  const domain = tree.value.find(b => b.name === bookTitle)
  if (!domain) return
  activeDomain.value = domain
  const s = new Set<string>([domain.id])
  const find = (nodes: KSTNode[], id: string): boolean => {
    for (const n of nodes) {
      if (n.id === id) return true
      if (n.children?.length && find(n.children, id)) { s.add(n.id); return true }
    }
    return false
  }
  find([domain], r.id)
  expanded.value = s
  results.value = []
  q.value = ''
  const hit = visible.value.find(v => v.node.id === r.id)
  if (hit) openSkill(hit)
}

async function openSkill(v: VNode) {
  selV.value = v
  detail.value = null
  try {
    detail.value = await getSkillDetail(v.node.id)
  } catch {
    /* 详情加载失败不阻塞 */
  }
}

function goLearn(id: string) {
  router.push({ path: '/app/home', query: { learn: id } })
}
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

$BOX_W: 190px;
$BOX_H: 34px;

.kst-page { height: 100%; overflow-y: auto; }
.kst-inner { max-width: 1080px; margin: 0 auto; padding: 28px 32px 40px; }
.ph-title { font-family: $font-serif; font-size: 19px; font-weight: 700; color: $color-text-link; }
.ph-desc { margin-top: 6px; font-size: 12.5px; color: $color-text-secondary; }
.ph { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 14px; }
.pill { background: $color-accent-light; color: $color-text-link; font-size: 12px; padding: 4px 12px; border-radius: 999px; }

.kst-counts { display: flex; gap: 10px; margin: 14px 0; flex-wrap: wrap; }
.kst-counts .c { background: $color-surface; border: 1px solid $color-border; border-radius: 10px; padding: 8px 14px; display: flex; align-items: baseline; gap: 6px; }
.kst-counts .c b { font-size: 19px; color: $color-text-link; }
.kst-counts .c span { font-size: 12px; color: $color-text-secondary; }

.kst-search { display: flex; align-items: center; gap: 8px; background: $color-surface; border: 1px solid $color-border; border-radius: 10px; padding: 8px 12px; margin-bottom: 10px; }
.kst-input { flex: 1; border: none; outline: none; font-size: 13.5px; background: transparent; }
.kst-results { background: $color-secondary-bg; border: 1px solid $color-border; border-radius: 10px; padding: 8px 12px; margin-bottom: 14px; }
.rs-item { display: flex; align-items: center; gap: 6px; padding: 6px 0; cursor: pointer; font-size: 12.5px; color: $color-text-link; }
.rs-item + .rs-item { border-top: 1px dashed $color-border; }
.rs-path { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rs-cnt { color: $color-text-link; font-size: 12px; }

/* ── 总览 ── */
.ov-tree { position: relative; background: $color-surface; border: 1px solid $color-border; border-radius: $radius-lg; padding: 18px; margin-bottom: 16px; height: 230px; }
.ov-svg { position: absolute; inset: 0; width: 100%; height: 100%; z-index: 0; pointer-events: none; }
.ov-line { stroke: #B8D8F5; stroke-width: 0.4; fill: none; }
.ov-line.on { stroke: $color-accent; }
.ov-core { position: absolute; left: 50%; top: 10%; transform: translate(-50%, -50%); background: $color-primary; color: #fff; display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 999px; font-size: 12.5px; box-shadow: $shadow-card; z-index: 1; white-space: nowrap; }
.ov-branch { position: absolute; transform: translate(-50%, -50%); display: flex; align-items: center; gap: 6px; background: $color-surface; border: 1px solid $color-border; border-radius: 999px; padding: 6px 12px; cursor: pointer; font-size: 12.5px; color: $color-text; box-shadow: $shadow-card; transition: all .15s; z-index: 1; white-space: nowrap; }
.ov-branch:hover { border-color: $color-accent; }
.ov-branch.on { border-color: $color-accent; background: #E4F0FC; color: $color-text-link; font-weight: 600; }
.ob-ic { color: $color-text-link; display: inline-flex; }
.ov-hint { position: absolute; left: 50%; bottom: 8px; transform: translateX(-50%); font-size: 11px; color: $color-text-secondary; display: flex; align-items: center; gap: 4px; z-index: 1; white-space: nowrap; }

/* ── 展开域：整齐树 ── */
.sub-tree { background: $color-surface; border: 1px solid $color-border; border-radius: $radius-lg; overflow: hidden; }
.sub-head { display: flex; align-items: center; gap: 8px; padding: 14px 18px; border-bottom: 1px solid $color-border; }
.sub-ic { color: $color-text-link; display: inline-flex; }
.sub-title { font-family: $font-serif; font-size: 16px; color: $color-text-link; margin: 0; }
.sub-meta { margin-left: auto; font-size: 12px; color: $color-text-secondary; }
.sub-canvas { position: relative; overflow: auto; max-height: 640px; cursor: grab; user-select: none; }
.sub-canvas.panning { cursor: grabbing; }
.sub-inner { position: relative; }
.sub-svg { position: absolute; top: 0; left: 0; z-index: 0; pointer-events: none; }
.sub-line { stroke: #B8D8F5; stroke-width: 1.5; fill: none; }
.sub-line.on { stroke: $color-accent; }
.sb-node { position: absolute; transform: translate(-50%, -50%); display: flex; align-items: center; gap: 6px; background: $color-surface; border: 1px solid $color-border; border-radius: 10px; padding: 6px 10px; width: $BOX_W - 24px; height: $BOX_H - 8px; cursor: pointer; box-shadow: $shadow-card; transition: all .15s; font-size: 12px; color: $color-text; z-index: 1; }
.sb-node:hover { border-color: $color-accent; }
.sb-node.lit { border-color: rgba(51,143,242,.55); background: #F3F8FE; }
.sb-node.sel { border-color: $color-accent; background: #E4F0FC; }
.sb-node.book .sn-name { font-weight: 700; color: $color-text-link; }
.sb-node.part .sn-name { font-weight: 600; }
.sn-status { display: inline-flex; flex-shrink: 0; }
.sn-ic { color: $color-text-link; display: inline-flex; flex-shrink: 0; }
.sn-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sn-exp { display: inline-flex; color: $color-text-secondary; flex-shrink: 0; }
.sub-legend { display: flex; gap: 16px; padding: 10px 18px; border-top: 1px solid $color-border; font-size: 11.5px; color: $color-text-secondary; }
.lg { display: flex; align-items: center; gap: 5px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #B8D8F5; }
.dot.lit { background: $color-accent; }
.dot.line { background: transparent; border: 1px solid $color-accent; height: 6px; width: 12px; border-radius: 3px; }

/* ── 详情抽屉 ── */
.st-mask { position: fixed; inset: 0; background: rgba(10, 25, 41, 0.35); z-index: 40; }
.st-drawer { position: fixed; top: 0; right: 0; width: 360px; height: 100%; background: $color-surface; box-shadow: -8px 0 30px rgba(0,0,0,.12); transform: translateX(100%); transition: transform .25s; z-index: 41; padding: 22px 22px 30px; overflow-y: auto; }
.st-drawer.open { transform: translateX(0); }
.sd-head { display: flex; align-items: center; justify-content: space-between; }
.sd-badge { font-size: 12px; padding: 3px 10px; border-radius: 999px; }
.sd-badge.on { background: $color-accent-light; color: $color-text-link; }
.sd-badge.off { background: $color-secondary-bg; color: $color-text-secondary; }
.sd-x { border: none; background: none; cursor: pointer; color: $color-text-secondary; display: inline-flex; }
.sd-title-row { display: flex; align-items: center; gap: 8px; margin-top: 14px; }
.sd-ic { color: $color-text-link; display: inline-flex; }
.sd-title { font-family: $font-serif; font-size: 16px; color: $color-text-link; margin: 0; }
.sd-desc { font-size: 12.5px; color: $color-text-secondary; line-height: 1.7; margin: 10px 0 16px; }
.sd-stats { display: flex; gap: 8px; }
.sd-stats .st { flex: 1; background: $color-secondary-bg; border-radius: 10px; padding: 10px 6px; text-align: center; }
.sd-stats .v { display: block; font-size: 17px; font-weight: 700; color: $color-text-link; }
.sd-stats .k { display: block; font-size: 11px; color: $color-text-secondary; margin-top: 3px; }
.sd-prog { margin-top: 18px; }
.sd-prog .lb { display: flex; justify-content: space-between; font-size: 12px; color: $color-text-secondary; }
.sd-prog .pct { color: $color-text-link; font-weight: 700; }
.sd-prog .bar { height: 8px; background: $color-secondary-bg; border-radius: 999px; margin-top: 6px; overflow: hidden; }
.sd-prog .fill { height: 100%; background: linear-gradient(90deg, $color-accent, $color-accent-d10); border-radius: 999px; }
.sd-reason { margin-top: 16px; display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: $color-text-link; background: $color-accent-light; border-radius: 10px; padding: 10px 12px; }
.sd-pending { margin-top: 16px; display: flex; align-items: flex-start; gap: 6px; font-size: 12.5px; color: $color-text-secondary; background: $color-secondary-bg; border-radius: 10px; padding: 10px 12px; line-height: 1.6; }
.sd-learn { margin-top: 18px; width: 100%; display: flex; align-items: center; justify-content: center; gap: 6px; background: $color-primary; color: #fff; border: none; border-radius: 10px; padding: 12px; font-size: 13.5px; cursor: pointer; transition: background .15s; }
.sd-learn:hover { background: $color-primary-light; }

/* ── 掌握度填充 ── */
.sb-node { position: absolute; overflow: hidden; }
.sn-fill {
  position: absolute; left: 0; bottom: 0; height: 4px;
  background: linear-gradient(90deg, #2f6fae, #7a5af8);
  opacity: .85; border-radius: 0 4px 4px 0; pointer-events: none;
}
.sb-node.lit .sn-fill { background: linear-gradient(90deg, #338FF2, #f0cf8a); }
.sn-fill-tag {
  position: absolute; right: 4px; bottom: 3px; font-size: 9px; color: #684dd3;
  font-weight: 700; pointer-events: none; opacity: .9;
}
.sb-node.lit .sn-fill-tag { color: #925700; }
.dot.mid { background: linear-gradient(135deg,#2f6fae,#7a5af8); }
.dot.low { background: rgba(122,90,248,.35); }
.sd-break {
  margin-top: 12px; background:#f4f8fd; border:1px solid #dfe9f5;
  border-radius:10px; padding:10px 12px;
}
.sd-break .br-row { display:flex; align-items:baseline; gap:8px; font-size:12px; color:$color-text-link; margin-top:4px; }
.sd-break .br-row b { margin-left:auto; color:#2f6fae; }
.sd-break .br-row em { color:$color-text-secondary; font-style:normal; }


/* ── 节点=掌握度进度框：藏蓝文字 + 淡金按%填充 ── */
.sb-node { color:$color-text-link; }
.sb-node .sn-name { color:$color-text-link; }
.sn-pct { margin-left:auto; font-size:10px; font-weight:700; color:$color-text-link; padding-left:6px; flex:0 0 auto; }
/* 图例点：不透明区分（无透明度渐变） */
.dot.mid { background:#7a5af8; }
.dot.low { background:#c8d0df; }

</style>
