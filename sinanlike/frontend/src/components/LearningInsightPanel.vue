<template>
  <div class="lip">
    <div class="lip-main">
      <div class="lip-main-head">
        <span class="lip-main-t"><SIcon name="bookcheck" :size="15" />学习情况</span>
        <button class="lip-refresh" :disabled="refreshing || insightLoading" @click="onRefresh">
          <SIcon name="sync" :size="12" />{{ refreshing ? '更新中…' : '更新画像' }}
        </button>
      </div>

      <!-- 学情画像 -->
      <div class="lip-block">
        <div class="lip-block-t"><span>学情画像</span></div>
        <div v-if="persona" class="lip-persona">
          <div class="lip-persona-top">
            <div>
              <div class="lip-label">{{ persona.label }}</div>
              <div class="lip-summary">{{ persona.summary }}</div>
            </div>
            <span v-if="updatedAt" class="lip-updated">更新于 {{ fmt(updatedAt) }}</span>
          </div>
          <div v-if="persona.description" class="lip-desc">{{ persona.description }}</div>
          <div v-if="insight?.persona_analysis" class="rep-h">画像报告</div>
          <p v-if="insight?.persona_analysis" class="lip-talk report">{{ insight.persona_analysis }}</p>
        </div>
        <div v-else class="lip-hint">尚未完成先验学情画像——请在首页完成初试引导。</div>
      </div>

      <!-- 学习盲区：雷达图 + 点端点看分组进度 -->
      <div class="lip-block blind">
        <div class="lip-block-t"><span>学习盲区</span><b class="blind-n">{{ weakList.length }} 组</b></div>
        <div v-if="domains.length" class="lip-radar-wrap">
          <div class="lip-radar-col">
          <svg class="lip-radar" :viewBox="'0 0 300 300'" width="300" height="300">
            <!-- 网格：等边七边形（与端点同形，无外圈圆） -->
            <polygon v-for="lv in [25, 50, 75]" :key="'g' + lv" :points="ringPoints(lv)" class="gridpoly" />
            <!-- 轴线 -->
            <line v-for="(d, i) in domains" :key="'a' + i" :x1="CX" :y1="CY" :x2="axis(i, R).x" :y2="axis(i, R).y" class="axis" />
            <!-- 数值多边形 -->
            <polygon :points="valuePoints" class="area" />
            <!-- 域端点（点击切换） -->
            <g v-for="(d, i) in domains" :key="'p' + i" class="ep" @click="selectDomain(d.id)">
              <line :x1="axis(i, R).x" :y1="axis(i, R).y" :x2="labelPos(i).x" :y2="labelPos(i).y" class="lead" />
              <circle :cx="axis(i, R).x" :cy="axis(i, R).y" :r="selDomain?.id === d.id ? 9 : 6" class="ep-dot" :class="{ on: selDomain?.id === d.id }" />
              <text :x="labelPos(i).x" :y="labelPos(i).y + 4" class="ep-label" text-anchor="middle">{{ shortOf(d.title) }}</text>
            </g>
          </svg>
          <div class="lip-radar-cap" v-if="selDomain">当前查看：{{ selDomain.title }}   综合掌握度 <b>{{ Math.round(selDomain.avg_mastery) }}%</b></div>
          </div>
          <div class="lip-groups">
            <div class="lip-groups-head">
              <span class="lg-title">{{ selDomain?.title || '知识域' }}</span>
              <span class="lg-avg">综合 {{ Math.round(selDomain?.avg_mastery ?? 0) }}%</span>
            </div>
            <div class="lg-list">
              <div v-for="g in selGroups" :key="g.id" class="lg-row">
                <span class="lg-name" :title="g.title">{{ g.title }}</span>
                <span class="lg-bar"><u :style="{ width: g.avg_mastery + '%', background: g.mastered ? '#63AAF1' : undefined }"></u></span>
                <span class="lg-pct">{{ Math.round(g.avg_mastery) }}%</span>
                <span v-if="!g.mastered && g.weak_skills > 0" class="lg-weak">{{ g.weak_skills }} 未点亮</span>
                <span v-else-if="g.mastered" class="lg-ok">已掌握</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="!loading" class="lip-empty-ok">暂无可展示的掌握度数据 🎉</div>
        <div v-if="insight?.blindspot_analysis" class="rep-h gold">盲区报告</div>
        <p v-if="insight?.blindspot_analysis" class="lip-talk report">{{ insight.blindspot_analysis }}</p>
        <div v-if="loading" class="lip-loading">正在生成雷达图…</div>
      </div>

    </div>

    <!-- 学情记录 -->
    <div class="lip-main">
      <div class="lip-main-head"><span class="lip-main-t"><SIcon name="clock" :size="15" />学情记录</span></div>
      <div v-if="!loading && timeline.length === 0" class="lip-hint">暂无记录——完成引导并生成学习路径后会记录在这里。</div>
      <div v-else class="lip-timeline">
        <div v-for="(it, i) in timeline" :key="i" class="lip-rec">
          <span class="lip-rec-dot" :class="it.kind"></span>
          <div class="lip-rec-main">
            <div class="lip-rec-title">{{ it.title }}</div>
            <div class="lip-rec-desc">{{ it.desc }}</div>
          </div>
          <span class="lip-rec-time">{{ fmt(it.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SIcon from '@/components/SIcon.vue'
import { useAppStore } from '@/stores/app'
import {
  generateInsight, getBlindspots, getInsight, getOnboardingRecords, refreshProfile,
} from '@/api/onboarding'
import type { BlindSpot, DomainRadar, InsightText, OnbPersona, RecordsResult } from '@/api/onboarding'

const store = useAppStore()
const loading = ref(true)
const refreshing = ref(false)
const insightLoading = ref(false)
const persona = ref<OnbPersona | null>(null)
const updatedAt = ref('')
const domains = ref<DomainRadar[]>([])
const weakList = ref<BlindSpot[]>([])
const selectedDomainId = ref('')
const records = ref<RecordsResult | null>(null)
const insight = ref<InsightText | null>(null)

const CX = 150
const CY = 150
const R = 96
const ringIdx = [0, 1, 2, 3]

const SHORT: Record<string, string> = {
  '全国导游基础知识': '全国导基',
  '导游业务': '导游业务',
  '政策与法律法规': '政策法规',
  '地方导游基础知识': '地方导基',
  '文化习惯知识': '文化习惯',
  '文化桥': '文化桥',
  '入境游实战能力': '入境实战',
}
const shortOf = (t: string) => SHORT[t] || (t.length > 4 ? t.slice(0, 4) : t)

function axis(i: number, r: number): { x: number; y: number } {
  const a = -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(1, domains.value.length)
  return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a) }
}
function ringPoints(level: number): string {
  return domains.value.map((_, i) => {
    const p = axis(i, (R * level) / 100)
    return `${p.x},${p.y}`
  }).join(' ')
}
const valuePoints = computed(() => domains.value.map((d, i) => {
  const p = axis(i, (R * Math.max(4, Math.min(100, d.avg_mastery))) / 100)
  return `${p.x},${p.y}`
}).join(' '))
function labelPos(i: number): { x: number; y: number } {
  // 标签外置到圆外，与端点拉开距离
  const p = axis(i, R + 30)
  return { x: p.x, y: p.y }
}
const selDomain = computed(() => domains.value.find((d) => d.id === selectedDomainId.value) || domains.value[0] || null)
const selGroups = computed(() => selDomain.value?.groups || [])

const timeline = computed(() => {
  const items: Array<{ kind: string; title: string; desc: string; created_at?: string }> = []
  for (const p of records.value?.profile_snapshots || []) {
    items.push({ kind: 'profile', title: `学情画像   第 ${p.version} 版`, desc: p.persona?.label || p.source, created_at: p.created_at })
  }
  for (const lp of records.value?.learning_paths || []) {
    items.push({ kind: 'path', title: `学习路径   第 ${lp.version} 版`, desc: lp.note || lp.status, created_at: lp.created_at })
  }
  items.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
  return items
})

function fmt(t?: string): string {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}

function selectDomain(id: string) { selectedDomainId.value = id }

async function load() {
  loading.value = true
  try {
    const [bs, rec] = await Promise.all([getBlindspots(store.userId), getOnboardingRecords(store.userId)])
    domains.value = bs.domains || []
    weakList.value = bs.blindspots || []
    records.value = rec
    persona.value = rec.persona || null
    updatedAt.value = rec.updated_at || ''
    if (!selectedDomainId.value && domains.value.length) {
      // 默认选中：平均掌握度最低的知识域（最需要补）
      const lowest = [...domains.value].sort((a, b) => a.avg_mastery - b.avg_mastery)[0]
      selectedDomainId.value = lowest?.id || domains.value[0].id
    }
    try { insight.value = (await getInsight(store.userId)).insight || null } catch { /* ignore */ }
    if (persona.value && !insight.value) {
      insight.value = (await generateInsight(store.userId)).insight || null
    }
  } catch { /* ignore */ } finally {
    loading.value = false
  }
}

async function onRefresh() {
  if (!persona.value) return
  refreshing.value = true
  insightLoading.value = true
  try {
    await refreshProfile(store.userId)
    insight.value = (await generateInsight(store.userId)).insight || null
    await load()
  } catch { /* ignore */ } finally {
    refreshing.value = false
    insightLoading.value = false
  }
}

onMounted(load)
</script>
<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.lip { display: flex; flex-direction: column; gap: 16px; margin-bottom: 16px; }
.lip-main { background: #fff; border: 1px solid $color-border; border-radius: 14px; padding: 14px 16px; }
.lip-main-head { display: flex; align-items: center; margin-bottom: 10px;
  .lip-main-t { display: inline-flex; align-items: center; gap: 7px; color: $color-text-link; font-size: 14px; font-weight: 800; letter-spacing: .5px; }
  .lip-refresh { margin-left: auto; background: $color-primary; color: #fff; border: none; border-radius: 999px; padding: 6px 14px; font-size: 12.5px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; &:disabled { opacity: .6; } } }
.lip-block { border-top: 1px dashed $color-border; padding-top: 12px; margin-top: 4px; }
.lip-block-t { display: flex; align-items: center; font-size: 12px; font-weight: 800; color: $color-accent-d15; letter-spacing: .5px; margin-bottom: 8px;
  span { border-left: 3px solid $color-accent; padding-left: 8px; } }
.lip-persona-top { display: flex; align-items: flex-start; gap: 10px; }
.lip-updated { margin-left: auto; font-size: 11px; color: $color-text-secondary; white-space: nowrap; }
.lip-label { font-size: 17px; font-weight: 800; color: $color-text; }
.lip-summary { font-size: 13px; font-weight: 600; color: $color-accent-d15; margin: 2px 0 4px; }
.lip-desc { font-size: 12.5px; color: $color-text-secondary; line-height: 1.8; }
.lip-hint { font-size: 12.5px; color: $color-text-secondary; }
.lip-loading { font-size: 12.5px; color: $color-text-secondary; margin-top: 8px; }
.lip-empty-ok { color: #26733a; font-size: 13px; padding: 6px 0; }
.blind-n { margin-left: auto; font-size: 11px; color: #256CA7; background: rgba(51,143,242,.18); padding: 2px 8px; border-radius: 999px; }
.rep-h { font-size: 12px; font-weight: 800; color: $color-text-link; letter-spacing: .5px; margin: 12px 0 6px; display: flex; align-items: center; gap: 6px;
  &::before { content: ''; width: 4px; height: 13px; border-radius: 2px; background: $color-primary; display: inline-block; }
  &.gold { color: $color-accent-d15; &::before { background: $color-accent; } } }
.lip-talk { font-size: 13px; line-height: 1.85; color: $color-text; background: $color-secondary-bg; border-radius: 10px; padding: 10px 13px; margin: 6px 0 0; }
.lip-talk.report { background: #fff; border: 1px solid $color-border; border-left: 3px solid $color-accent; white-space: pre-wrap; }
.lip-talk.plan { border-left-color: $color-primary; }

/* 雷达图 */
.lip-block.blind { border: 1px solid rgba(51,143,242,.55); background: #F8FBFF; border-radius: 12px; padding: 10px 12px; margin-top: 10px; }
.lip-radar-wrap { display: flex; gap: 14px; align-items: flex-start; flex-wrap: wrap; }
.lip-radar { flex-shrink: 0; }
.lip-radar { display: block; }
.lip-radar .gridpoly { fill: none; stroke: #DCEAF7; stroke-width: 1.2; }
.lip-radar .axis { stroke: #DCEAF7; stroke-width: 1.2; }
.lip-radar .area { fill: rgba(51,143,242,.13); stroke: #64AAF1; stroke-width: 2.4; }
.lip-radar .ep { cursor: pointer; }
.lip-radar .lead { stroke: #B8D8F5; stroke-width: 1; stroke-dasharray: 2 3; }
.lip-radar .ep-dot { fill: #F0A36A; opacity: .85; transition: all .18s; filter: drop-shadow(0 1px 2px rgba(24,58,99,.25));
  &.on { fill: #E99550; stroke: #fff; stroke-width: 2.5; opacity: 1; }
  &:hover { opacity: 1; } }
.lip-radar .ep-label { font-size: 11.5px; fill: #338FF2; font-weight: 700; }
.lip-radar .c-pct { font-size: 26px; font-weight: 800; fill: #338FF2; }
.lip-radar .c-tag { font-size: 10.5px; fill: #8a7b58; }

.lip-radar-col { display: flex; flex-direction: column; align-items: center; gap: 4px; flex-shrink: 0; }
.lip-radar-cap { font-size: 12px; color: $color-text-secondary; b { color: $color-text-link; } }
.lip-groups { flex: 1; min-width: 240px; border: 1px solid $color-border; border-radius: 10px; background: #fff; padding: 8px 10px; }
.lip-groups-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px;
  .lg-title { font-size: 13px; font-weight: 800; color: $color-text; }
  .lg-avg { margin-left: auto; font-size: 11px; color: $color-accent-d15; font-weight: 700; } }
.lg-list { display: flex; flex-direction: column; gap: 5px; max-height: 218px; overflow-y: auto; }
.lg-row { display: flex; align-items: center; gap: 8px; font-size: 12px;
  .lg-name { flex: 0 0 38%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: $color-text; }
  .lg-bar { flex: 1; height: 6px; border-radius: 999px; background: $color-muted-bg; overflow: hidden; min-width: 60px;
    u { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, $color-accent, $color-accent-d15); } }
  .lg-pct { width: 30px; text-align: right; color: $color-text-secondary; }
  .lg-weak { font-size: 10.5px; color: #a74543; flex-shrink: 0; }
  .lg-ok { font-size: 10.5px; color: #26733a; flex-shrink: 0; } }

.lip-timeline { display: flex; flex-direction: column; gap: 8px; }
.lip-rec { display: flex; align-items: center; gap: 10px;
  .lip-rec-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; &.profile { background: $color-accent; } &.path { background: $color-primary; } }
  .lip-rec-main { flex: 1; .lip-rec-title { font-size: 12.5px; font-weight: 700; color: $color-text; } .lip-rec-desc { font-size: 11.5px; color: $color-text-secondary; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } }
  .lip-rec-time { font-size: 11px; color: $color-text-secondary; flex-shrink: 0; } }
</style>
