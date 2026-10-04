<template>
  <div class="pf-page">
    <div class="page-inner">
      <!-- 后端状态提示 -->
      <div v-if="!store.backendOnline" class="backend-offline-banner">
        <el-icon><WarningFilled /></el-icon>
        <span>后端服务未连接，显示本地缓存数据</span>
        <el-button size="small" text @click="store.checkHealth()">重试</el-button>
      </div>

      <!-- 个人头部卡片 -->
      <div class="profile-header-card">
        <InkMountain class="header-ink" />
        <div class="phc-content">
          <div class="phc-avatar-row">
            <div class="phc-avatar">
              <span class="avatar-text">{{ avatarChar }}</span>
            </div>
            <div class="phc-info">
              <div class="phc-name-row">
                <h2 class="phc-name">{{ displayName }}</h2>
                <span class="phc-badge"><el-icon><StarFilled /></el-icon> {{ levelLabel }}</span>
              </div>
              <div class="phc-meta">
                <span><el-icon><User /></el-icon> ID: {{ shortUserId }}</span>
                <span class="meta-sep">·</span>
                <span><el-icon><Aim /></el-icon> {{ profile.targetRole || '导游资格证' }}</span>
              </div>
              <p class="phc-bio">{{ personaSummary || profile.background || '尚未生成学情画像——请先到首页完成「先验学情画像」（6 道身份题 + 能力自评）。' }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 学情洞察：画像 / 盲区定位 / 学情记录 -->
      <LearningInsightPanel />

      <!-- 掌握度统计 -->
      <div class="pf-stats">
        <div v-for="s in computedStats" :key="s.label" class="pf-stat-card">
          <el-icon :size="20" :color="s.color"><component :is="s.icon" /></el-icon>
          <div class="pf-stat-value">{{ s.value }}</div>
          <div class="pf-stat-label">{{ s.label }}</div>
          <div class="pf-stat-unit">{{ s.unit }}</div>
        </div>
      </div>

      <!-- 学习规划（自学习中心迁移：教材 → 章节 → 技能点 可视化路径） -->
      <div class="pf-section">
        <div class="section-header">
          <div class="section-title-row">
            <el-icon :size="18" color="#338FF2"><Calendar /></el-icon>
            <h3 class="section-title">学习规划</h3>
          </div>
          <el-button text type="primary" size="small" @click="$router.push('/app/knowledge')">去知识库看课本</el-button>
        </div>
        <div v-if="pathBooks.length" class="pp-steps">
          <template v-for="(b, i) in pathBooks" :key="b.bookId">
            <div class="pp-node" :class="{ done: b.avg >= 80, weak: b.avg < 40 }">
              <div class="pp-dot">{{ i + 1 }}</div>
              <div class="pp-name" :title="b.bookTitle">{{ b.bookTitle }}</div>
              <div class="pp-track"><div class="pp-fill" :style="{ width: b.avg + '%' }"></div></div>
              <div class="pp-avg">{{ Math.round(b.avg) }}%</div>
            </div>
            <div v-if="i < pathBooks.length - 1" class="pp-arrow"><SIcon name="right" :size="12" /></div>
          </template>
        </div>
        <div v-if="nextChapter" class="pp-next">
          <SIcon name="sparkle" :size="13" color="#338FF2" />
          <span>建议下一步：<b>{{ nextChapter.bookTitle }} · {{ nextChapter.title }}</b>
            （当前掌握 {{ nextChapter.mastery }}%，先让旅鸢讲一遍再做真题）</span>
          <button class="pp-go" @click="$router.push('/app/knowledge')">去学习</button>
        </div>
        <div v-else class="pp-next all-done">
          <SIcon name="check" :size="13" color="#2d8a2d" />
          <span>所有章节均已掌握（≥60%），可以进入真题闯关与综合模拟冲刺</span>
        </div>
        <div v-if="!loadingPlan && !pathBooks.length" class="pp-empty">暂无学习规划数据 — 请确认后端服务已连接</div>
      </div>

      <!-- 学习历史 -->
      <div class="pf-section">
        <div class="section-header">
          <div class="section-title-row">
            <el-icon :size="18" color="#338FF2"><Clock /></el-icon>
            <h3 class="section-title">最近答题记录</h3>
          </div>
          <el-button text type="primary" size="small" @click="$router.push('/app/training')">查看全部</el-button>
        </div>
        <div v-if="recentProgress.length" class="history-table">
          <div v-for="(item, i) in recentProgress" :key="i" class="history-row" :class="{ even: i % 2 === 1 }">
            <div class="hist-date">{{ item.last_attempted_at ? item.last_attempted_at.slice(5, 10) : '--' }}</div>
            <div class="hist-title">{{ skillTitles[item.knowledge_point_id] || item.knowledge_point_id }}</div>
            <div class="hist-meta">
              <el-icon :size="12"><Clock /></el-icon> {{ item.attempt_count }}次
            </div>
            <div class="hist-score" :class="{ high: item.mastery >= 0.8 }">{{ Math.round(item.mastery * 100) }}分</div>
          </div>
        </div>
        <el-empty v-else description="暂无学习记录" />
      </div>

      <!-- 长期记忆 -->
      <div class="pf-section" v-if="memories.length">
        <div class="section-header">
          <div class="section-title-row">
            <el-icon :size="18" color="#338FF2"><Memo /></el-icon>
            <h3 class="section-title">AI 记住的你</h3>
          </div>
          <span class="memory-hint">对话与画像中沉淀的长期记忆，用于个性化辅导</span>
        </div>
        <div class="memory-grid">
          <div v-for="m in memories" :key="String(m.memory_id)" class="memory-card">
            <el-tag size="small" :type="memoryTagType(String(m.memory_type))" effect="plain">{{ memoryLabels[String(m.memory_type)] || '记忆' }}</el-tag>
            <p class="memory-content">{{ m.content }}</p>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  StarFilled, User, Setting, SwitchButton,
  TrophyBase, Clock, Aim, Reading, WarningFilled, Calendar, Memo, Download, Delete,
} from '@element-plus/icons-vue'
import SIcon from '@/components/SIcon.vue'
import InkMountain from '@/components/InkMountain.vue'
import LearningInsightPanel from '@/components/LearningInsightPanel.vue'
import { getUserState, exportUserData, deleteUserData } from '@/api/profile'
import { getKnowledgeTree } from '@/api/knowledge'
import type { SkillNode } from '@/api/knowledge'
import { classifyError } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { useOnboardingStore } from '@/stores/onboarding'

const store = useAppStore()
const onb = useOnboardingStore()
const personaSummary = computed(() => onb.persona?.summary || '')
const router = useRouter()

// ── 学习规划（自学习中心迁移：教材 → 章节 → 技能点 可视化路径） ──
interface PlanSkillRow { id: string; title: string; idx: number; questionCount: number; mastery: number }
interface PlanSectionItem { id: string; title: string; skills: PlanSkillRow[] }
interface PlanChapterItem {
  id: string; title: string; bookId: string; bookTitle: string; partTitle: string
  sectionCount: number; skillCount: number; questionCount: number; mastery: number
  sections: PlanSectionItem[]
}
interface PlanChapterGroup { bookId: string; bookTitle: string; chapters: PlanChapterItem[] }

const loadingPlan = ref(false)
const books = ref<SkillNode[]>([])
const scores = ref<Record<string, number>>({})

function planSkillScore(id: string): number {
  return scores.value[id] ?? 0
}
function buildPlanChapter(book: SkillNode, node: SkillNode, partTitle: string): PlanChapterItem {
  const sections: PlanSectionItem[] = []
  let skillCount = 0
  let questionCount = 0
  let masterySum = 0
  for (const secNode of node.children ?? []) {
    if (secNode.type !== 'section') continue
    const rows: PlanSkillRow[] = []
    for (const sNode of secNode.children ?? []) {
      if (sNode.type !== 'skill') continue
      const m = Math.round(planSkillScore(sNode.id) * 100)
      skillCount++
      questionCount += sNode.question_count ?? 0
      masterySum += m
      rows.push({ id: sNode.id, title: sNode.title, idx: rows.length + 1, questionCount: sNode.question_count ?? 0, mastery: m })
    }
    if (rows.length) sections.push({ id: secNode.id, title: secNode.title, skills: rows })
  }
  return {
    id: node.id, title: node.title, bookId: book.id, bookTitle: book.title, partTitle,
    sectionCount: sections.length, skillCount, questionCount,
    mastery: skillCount ? Math.round(masterySum / skillCount) : 0, sections,
  }
}
function planChaptersOfBook(book: SkillNode): PlanChapterItem[] {
  const out: PlanChapterItem[] = []
  const walk = (nodes: SkillNode[] | undefined, partTitle: string) => {
    for (const n of nodes ?? []) {
      if (n.type === 'chapter') out.push(buildPlanChapter(book, n, partTitle))
      else if (n.children) walk(n.children, n.type === 'part' ? n.title : partTitle)
    }
  }
  walk(book.children, '')
  return out
}
const planGroups = computed<PlanChapterGroup[]>(() => {
  const groups: PlanChapterGroup[] = []
  for (const b of books.value) {
    if (b.type !== 'book') continue
    const chapters = planChaptersOfBook(b)
    if (chapters.length) groups.push({ bookId: b.id, bookTitle: b.title, chapters })
  }
  return groups
})
const pathBooks = computed(() =>
  planGroups.value.map((g) => ({
    bookId: g.bookId,
    bookTitle: g.bookTitle,
    avg: g.chapters.length ? g.chapters.reduce((s, c) => s + c.mastery, 0) / g.chapters.length : 0,
  })),
)
const nextChapter = computed<PlanChapterItem & { bookTitle: string } | null>(() => {
  for (const g of planGroups.value) {
    for (const c of g.chapters) {
      if (c.mastery < 60) return { ...c, bookTitle: g.bookTitle }
    }
  }
  return null
})

async function loadPlan() {
  loadingPlan.value = true
  try {
    const [{ tree }, userState] = await Promise.all([
      getKnowledgeTree(),
      getUserState(store.userId),
    ])
    books.value = tree ?? []
    scores.value = userState.mastery?.knowledge_point_scores ?? {}
  } catch (e: any) {
    ElMessage.error('学习规划加载失败：' + classifyError(e).message)
  } finally {
    loadingPlan.value = false
  }
}

// ── 显示名称（优先从记忆提取真实姓名） ──
const displayName = ref('学员')
const avatarChar = computed(() => displayName.value.charAt(0))
const shortUserId = computed(() => store.userId.slice(0, 8))
const levelLabel = computed(() => {
  const map: Record<string, string> = { intro: '入门学员', basic: '初级学员', advanced: '高级学员', comprehensive: '综合学员' }
  return map[profile.currentLevel] || '入门学员'
})

// ── 画像 ──
const profile = reactive({
  background: '',
  targetRole: '导游资格证',
  currentLevel: 'intro',
})

// ── 掌握度数据 ──
const masteryScores = ref<Record<string, number>>({})
const recentProgress = ref<any[]>([])
const memories = ref<any[]>([])
const skillTitles = ref<Record<string, string>>({})

const computedStats = computed(() => {
  const scores = Object.values(masteryScores.value) as number[]
  const total = scores.length
  const mastered = scores.filter(s => s >= 0.7).length
  const avgScore = scores.length ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 100) : 0

  return [
    { icon: Reading, label: '覆盖技能点', value: total, unit: '个', color: '#338FF2' },
    { icon: Clock, label: '已掌握', value: mastered, unit: '/' + total, color: '#338FF2' },
    { icon: StarFilled, label: '平均掌握度', value: avgScore, unit: '%', color: '#338FF2' },
    { icon: TrophyBase, label: '答题记录', value: recentProgress.value.reduce((s, r) => s + (r.attempt_count || 0), 0), unit: '次', color: '#338FF2' },
  ]
})

const memoryLabels: Record<string, string> = {
  fact: '学员信息', goal: '学习目标', preference: '学习偏好', background: '背景', progress_note: '学习记录',
}

function memoryTagType(t: string): 'primary' | 'success' | 'warning' | 'info' {
  return t === 'goal' ? 'warning' : t === 'preference' ? 'primary' : t === 'progress_note' ? 'info' : 'success'
}

async function loadSkillTitles() {
  try {
    const { tree } = await getKnowledgeTree()
    const titles: Record<string, string> = {}
    const walk = (nodes: SkillNode[]) => {
      for (const n of nodes) {
        if (n.type === 'skill') titles[n.id] = n.title
        if (n.children) walk(n.children)
      }
    }
    walk(tree)
    skillTitles.value = titles
  } catch { /* ignore */ }
}

async function loadProfileData() {
  try {
    const state = await getUserState(store.userId)
    if (state.profile) {
      const p = state.profile as any
      profile.background = p.background || ''
      profile.targetRole = p.target_role || p.targetRole || '导游资格证'
      profile.currentLevel = p.current_level || p.currentLevel || 'intro'
    }
    if (state.mastery?.knowledge_point_scores) {
      masteryScores.value = state.mastery.knowledge_point_scores as Record<string, number>
    }
    if (state.progress) {
      recentProgress.value = state.progress.slice(-10).reverse()
    }
    memories.value = state.memories || []
    // 从记忆提取姓名
    const nameMem = memories.value.find(m => String(m.memory_type) === 'fact' && String(m.content).includes('名叫'))
    if (nameMem) {
      const match = String(nameMem.content).match(/名叫「(.+?)」/)
      if (match) displayName.value = match[1]
    } else if (profile.background) {
      const bgMatch = profile.background.match(/我(?:叫|是)\s*([一-鿿A-Za-z]{1,8})/)
      displayName.value = bgMatch ? bgMatch[1] : '学员'
    }
  } catch {
    // 后端不可用
  }
}

// ── T10/T12 数据合规：导出 / 重置学习数据（评审 #5：新用户入口干净、数据可控） ──
const complianceBusy = ref(false)

async function handleExportData() {
  complianceBusy.value = true
  try {
    const data = await exportUserData(store.userId)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `旅鸢学习数据_${store.userId.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('学习数据已导出（画像/记忆/进度/资产，已按合规要求不含敏感字段）')
  } catch (e) {
    ElMessage.error('导出失败：' + classifyError(e))
  } finally {
    complianceBusy.value = false
  }
}

async function handleResetData() {
  try {
    await ElMessageBox.confirm(
      '将删除当前账号的全部学习数据：画像、长期记忆、掌握度、学习资产、对话与教学记录。' +
      '删除后系统会像新用户一样重新开始，此操作不可恢复。确定继续吗？',
      '重置学习数据（危险操作）',
      { confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return // 用户取消
  }
  complianceBusy.value = true
  try {
    await deleteUserData(store.userId)
    // 清理本地状态（教学桥接/训练记录），回到全新用户环境
    localStorage.removeItem('boc_pending_teach')
    localStorage.removeItem('boc_teaching')
    ElMessage.success('已重置为全新学习环境，开始新的备考之旅吧')
    router.push('/app/home')
    setTimeout(() => window.location.reload(), 600)
  } catch (e) {
    ElMessage.error('重置失败：' + classifyError(e))
  } finally {
    complianceBusy.value = false
  }
}

onMounted(() => {
  onb.load(store.userId)
  loadSkillTitles()
  loadProfileData()
  loadPlan()  // 学习规划（教材路径 + 建议下一步）
})
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.pf-page {
  height: 100%;
  overflow-y: auto;
}

.page-inner {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.backend-offline-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: $radius-md;
  background: #fef3e2;
  border: 1px solid #f5d9a0;
  color: #a06315;
  font-size: 13px;
}

// ── 报告弹窗 ──
.report-content {
  .report-section {
    margin-bottom: 16px;
    h4 {
      font-size: 14px;
      font-weight: 600;
      color: $color-text;
      margin-bottom: 8px;
    }
    p {
      font-size: 14px;
      color: $color-text-secondary;
      line-height: 1.7;
    }
    .report-tag {
      margin: 2px 4px;
    }
  }
}
.plan-text { white-space: pre-wrap; line-height: 1.8 !important; }

// ── 长期记忆 ──
.memory-hint { font-size: 12px; color: $color-text-secondary; }
.memory-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.memory-card { padding: 14px 16px; border-radius: $radius-md; background: $color-surface; border: 1px solid $color-border; box-shadow: $shadow-card; }
.memory-content { font-size: 13px; color: $color-text; margin-top: 8px; line-height: 1.6; }

// ── 头部卡片 ──
.profile-header-card {
  position: relative;
  border-radius: $radius-xl;
  background: linear-gradient(135deg, $color-primary, $color-primary-light);
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(24, 58, 99, 0.15);

  .header-ink {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 100%;
    opacity: 0.3;
  }
}

.phc-content {
  position: relative;
  padding: 28px 32px;
}

.phc-avatar-row {
  display: flex;
  align-items: flex-start;
  gap: 24px;
}

.phc-avatar {
  width: 88px;
  height: 88px;
  border-radius: $radius-lg;
  background: rgba(51, 143, 242, 0.25);
  border: 2px solid rgba(51, 143, 242, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  .avatar-text {
    font-size: 32px;
    font-weight: 700;
    color: #FFFFFF;
  }
}

.phc-info {
  flex: 1;
}

.phc-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.phc-name {
  font-family: $font-serif;
  font-size: 24px;
  font-weight: 700;
  color: #FFFFFF;
}

.phc-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(51, 143, 242, 0.25);
  color: $color-accent;
  border: 1px solid rgba(51, 143, 242, 0.3);
}

.phc-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 8px;
  flex-wrap: wrap;

  .meta-sep {
    color: rgba(255, 255, 255, 0.3);
  }

  span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
}

.phc-bio {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.6;
}

.phc-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

// ── 统计行 ──
.pf-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.pf-stat-card {
  text-align: center;
  padding: 20px 12px;
  border-radius: $radius-xl;
  background: $color-surface;
  border: 1px solid $color-border;
  box-shadow: $shadow-card;

  .pf-stat-value {
    font-size: 28px;
    font-weight: 700;
    color: $color-primary;
    margin-top: 8px;
  }
  .pf-stat-label {
    font-size: 12px;
    color: $color-text-secondary;
    margin-top: 2px;
  }
  .pf-stat-unit {
    font-size: 11px;
    color: $color-text-secondary;
  }
}

// ── 掌握度雷达图 ──
.radar-hint { font-size: 12px; color: $color-text-secondary; }
.radar-card {
  padding: 20px 20px 16px;
  border-radius: $radius-lg;
  background: $color-surface;
  border: 1px solid $color-border;
  box-shadow: $shadow-card;
}
.radar-weak-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed $color-border;
}
.radar-weak-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: $color-primary;
  margin-right: 2px;
}
.radar-weak-chip {
  border: none;
  cursor: pointer;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 13px;
  border-radius: 999px;
  transition: transform 0.15s, box-shadow 0.15s;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(192, 57, 43, 0.35);
  }
}
.radar-weak-ok {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #2d8a2d;
}

// ── 通用 section ──
.pf-section {
  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .section-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .section-title {
    font-family: $font-serif;
    font-size: 16px;
    font-weight: 600;
    color: $color-primary;
  }
}

// ── 成就/掌握度 ──
.achievement-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.achievement-card {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-radius: $radius-lg;
  background: $color-surface;
  border: 1px solid $color-border;
  box-shadow: $shadow-card;
}

.ach-icon-box {
  width: 52px;
  height: 52px;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ach-info {
  flex: 1;
  min-width: 0;
}

.ach-title {
  font-size: 14px;
  font-weight: 600;
  color: $color-text;
  margin-bottom: 4px;
}

.ach-desc {
  font-size: 12px;
  color: $color-text-secondary;
  margin-bottom: 8px;
}

.ach-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ach-bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: $color-muted-bg;
  overflow: hidden;
}

.ach-fill {
  height: 100%;
  border-radius: 3px;
}

.ach-val {
  font-size: 12px;
  color: $color-text-secondary;
  flex-shrink: 0;
}

// ── 学习历史 ──
.history-table {
  border-radius: $radius-lg;
  overflow: hidden;
  background: $color-surface;
  border: 1px solid $color-border;
  box-shadow: $shadow-card;
}

.history-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid $color-border;
  &:last-child { border-bottom: none; }
  &.even { background: $color-bg; }
  font-size: 14px;
}

.hist-date {
  width: 64px;
  font-size: 12px;
  color: $color-text-secondary;
  text-align: center;
  flex-shrink: 0;
}

.hist-title {
  flex: 1;
  font-weight: 500;
  color: $color-text;
}

.hist-meta {
  font-size: 12px;
  color: $color-text-secondary;
  display: flex;
  align-items: center;
  gap: 4px;
}

.hist-score {
  font-size: 13px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(24, 58, 99, 0.1);
  color: $color-primary;
  &.high {
    background: $color-accent-light;
    color: $color-accent-d10;
  }
}

// ── 快捷操作 ──
.quick-actions-bar {
  position: relative;
  border-radius: $radius-xl;
  background: linear-gradient(135deg, $color-primary-d3, $color-primary, $color-primary-d10);
  overflow: hidden;
  padding: 20px;

  .qa-ink {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 50%;
    opacity: 0.5;
  }
}

.qa-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.qa-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 12px;
  border-radius: $radius-md;
  border: 1px solid rgba(51, 143, 242, 0.2);
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.15);
  }

  span {
    font-size: 13px;
    font-weight: 500;
    color: #FFFFFF;
  }
}

// ── 技能树（星座式放射，v2：管家按进度点亮） ──
.sk-head-right { display: flex; align-items: center; gap: 10px; }
.sk-crown { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 700; padding: 4px 11px;
  border-radius: 20px; color: #fff; background: linear-gradient(135deg, #338FF2, #A8893C); }
.sk-hint { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: $color-text-secondary;
  padding: 5px 12px; border-radius: 20px; background: rgba(51,143,242,.1); border: 1px solid rgba(51,143,242,.25); }
.sk-pending { display: inline-flex; align-items: center; gap: 6px; margin-top: 10px; font-size: 12.5px;
  color: $color-text-secondary; background: #F2F7FC; padding: 8px 12px; border-radius: 10px; }
.sk-card { border-radius: 18px; background: rgba(255,255,255,.88); border: 1px solid $color-border; padding: 16px; }
.sk-canvas { position: relative; height: 460px; border-radius: 14px; overflow: hidden;
  background: radial-gradient(ellipse at 50% 46%, #F5F9FD 0%, #ECF4FC 55%, #DCEAF7 100%);
  border: 1px solid $color-border; }
.sk-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.sk-ln { stroke: rgba(24,58,99,.16); stroke-width: 1.5; vector-effect: non-scaling-stroke;
  &.on { stroke: #338FF2; stroke-width: 2.5; filter: drop-shadow(0 0 3px rgba(51,143,242,.55)); }
  &.can { stroke: rgba(51,143,242,.6); stroke-width: 2; stroke-dasharray: 5 4; } }
.sk-branchname { position: absolute; transform: translate(-50%,-50%); font-size: 11px; font-weight: 700;
  letter-spacing: 3px; color: $color-text-secondary; font-family: $font-serif; pointer-events: none; white-space: nowrap; }
.sk-core { position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%); width: 38px; height: 38px;
  border-radius: 50%; background: radial-gradient(circle at 35% 30%, #26507f, #338FF2 72%);
  display: flex; align-items: center; justify-content: center; z-index: 3; }
.sk-nodec { position: absolute; transform: translate(-50%,-50%); display: flex; flex-direction: column;
  align-items: center; background: none; border: none; cursor: pointer; font-family: $font-sans; z-index: 2; padding: 0;
  .orb { position: relative; width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center;
    justify-content: center; background: rgba(255,255,255,.92); border: 1.5px solid rgba(24,58,99,.22);
    color: $color-text-secondary; transition: all .2s;
    > svg { opacity: .5; transition: opacity .2s; } }
  .lb { position: absolute; left: calc(100% + 6px); top: 50%; transform: translateY(-50%); white-space: nowrap;
    font-size: 9.5px; color: $color-text-secondary; background: rgba(255,255,255,.92); padding: 1px 7px;
    border-radius: 10px; border: 1px solid $color-border; opacity: 0; transition: opacity .18s; pointer-events: none; z-index: 4; }
  .ct { position: absolute; right: calc(100% + 6px); top: 50%; transform: translateY(-50%); white-space: nowrap;
    font-size: 8.5px; font-family: 'Liberation Mono', monospace; color: #B5B0A6; opacity: 0;
    transition: opacity .18s; pointer-events: none; z-index: 4; }
  &:hover .lb, &:hover .ct, &.sel .lb, &.sel .ct { opacity: 1; }
  &:hover, &.sel { z-index: 6; }
  &:hover .orb { transform: scale(1.1); border-color: $color-accent; }
  &.unlocked { .orb { background: #fff; border: 1.5px solid #338FF2; color: #338FF2;
      box-shadow: 0 0 0 3px rgba(51,143,242,.15);
      > svg { opacity: 1; } }
    .lb { color: #256CA7; font-weight: 600; border-color: rgba(51,143,242,.4); } }
  &.can { .orb { border: 1.5px solid $color-accent; color: #256CA7; background: #fff;
      animation: skGlow 1.8s ease infinite;
      > svg { opacity: .85; } }
    .lb { color: #256CA7; font-weight: 600; } }
  &.far { opacity: .45;
    .orb { cursor: not-allowed; } }
  &.sel .orb { box-shadow: 0 0 0 3px rgba(24,58,99,.25); } }
@keyframes skGlow { 0%, 100% { box-shadow: 0 0 0 0 rgba(51,143,242,.25); } 50% { box-shadow: 0 0 0 6px rgba(51,143,242,.1); } }
.sk-lockbadge { position: absolute; right: -3px; bottom: -3px; width: 15px; height: 15px; border-radius: 50%;
  background: #fff; border: 1px solid $color-border; display: flex; align-items: center; justify-content: center;
  color: #B5B0A6; }
.sk-detail { margin-top: 16px; padding: 16px; border-radius: 14px; background: rgba(24,58,99,.04);
  border: 1px solid rgba(24,58,99,.1);
  .sk-dh { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;
    .t { font-size: 14px; font-weight: 700; color: $color-primary; font-family: $font-serif; }
    .st { font-size: 10px; font-weight: 600; padding: 3px 10px; border-radius: 20px;
      &.on { color: #fff; background: linear-gradient(135deg, #338FF2, #A8893C); }
      &.can { color: #256CA7; background: rgba(51,143,242,.12); border: 1px solid rgba(51,143,242,.3); }
      &.off { color: $color-text-secondary; background: $color-secondary-bg; } } }
  p { font-size: 12.5px; line-height: 1.7; color: $color-text-secondary; margin-bottom: 12px; }
  .sk-learn { display: inline-flex; align-items: center; gap: 6px; margin-top: 12px; padding: 9px 18px;
    border: none; border-radius: 12px; background: linear-gradient(135deg, #338FF2, #A8893C); color: #fff;
    font-size: 13px; font-weight: 600; cursor: pointer; transition: all .2s;
    box-shadow: 0 2px 10px rgba(51,143,242,.35);
    &:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(51,143,242,.45); } }
  .sk-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px;
    span { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: $color-text-secondary;
      padding: 4px 10px; border-radius: 8px; background: rgba(255,255,255,.8); border: 1px solid $color-border; } }
  .sk-done { display: flex; align-items: center; gap: 8px; padding: 11px 14px; border-radius: 10px;
    background: rgba(51,143,242,.12); color: #256CA7; font-size: 13px; font-weight: 600; } }
.tb-btn-gold { width: 100%; padding: 12px; border: none; border-radius: 12px; cursor: pointer; font-size: 13px;
  font-weight: 600; color: #fff; background: linear-gradient(135deg, #338FF2, #A8893C); transition: all .18s;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-family: $font-sans;
  &:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(51,143,242,.55); }
  &:disabled { opacity: .5; cursor: not-allowed; } }
.sk-tip { display: flex; align-items: flex-start; gap: 7px; margin-top: 14px; padding: 10px 14px;
  border-radius: 10px; background: rgba(51,143,242,.06); border: 1px dashed rgba(51,143,242,.3);
  font-size: 11px; line-height: 1.6; color: $color-text-secondary; }

@media (max-width: 900px) {
  .sk-canvas { height: 420px; }
}

// ── 学习规划（自学习中心迁移） ──
.pp-steps { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
.pp-node { display: flex; align-items: center; gap: 9px; padding: 10px 14px; border-radius: 12px;
  background: rgba(24,58,99,.04); border: 1px solid rgba(24,58,99,.1);
  &.done { border-color: rgba(45,138,45,.35); background: rgba(45,138,45,.06); }
  &.weak { border-color: rgba(208,90,78,.3); }
  .pp-dot { width: 22px; height: 22px; border-radius: 50%; background: linear-gradient(135deg, #338FF2, #A8893C);
    color: #fff; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
  .pp-name { font-size: 12.5px; font-weight: 600; color: $color-primary; max-width: 150px; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
  .pp-track { width: 70px; height: 5px; border-radius: 3px; background: rgba(24,58,99,.08); overflow: hidden;
    .pp-fill { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, #338FF2, #A8893C); } }
  .pp-avg { font-size: 11px; font-family: Consolas, monospace; color: #256CA7; } }
.pp-arrow { color: #B5B0A6; display: flex; }
.pp-next { display: flex; align-items: flex-start; gap: 8px; margin-top: 14px; padding: 12px 14px;
  border-radius: 12px; background: rgba(51,143,242,.08); border: 1px solid rgba(51,143,242,.25);
  font-size: 12.5px; line-height: 1.7; color: $color-text-secondary;
  b { color: $color-primary; }
  .pp-go { margin-left: auto; flex-shrink: 0; padding: 6px 14px; border: none; border-radius: 9px;
    background: linear-gradient(135deg, #338FF2, #A8893C); color: #fff; font-size: 12px; font-weight: 600;
    cursor: pointer; align-self: center;
    &:hover { box-shadow: 0 3px 10px rgba(51,143,242,.4); } }
  &.all-done { background: rgba(45,138,45,.06); border-color: rgba(45,138,45,.3); color: #2d8a2d; } }
.pp-empty { margin-top: 14px; padding: 18px; text-align: center; font-size: 12.5px; color: $color-text-secondary;
  border: 1px dashed $color-border; border-radius: $radius-md; }
</style>
