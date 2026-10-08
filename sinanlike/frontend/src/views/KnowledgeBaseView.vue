<template>
  <div class="kb-page">
    <div class="kb-inner">
      <!-- 后端状态提示 -->
      <div v-if="!store.backendOnline" class="backend-offline-banner">
        <el-icon><WarningFilled /></el-icon>
        <span>后端服务未连接，无法加载文件资产与知识库</span>
        <el-button size="small" text @click="store.checkHealth()">重试</el-button>
      </div>

      <!-- 页头 -->
      <header class="ph">
        <div class="ph-left"><h2 class="ph-title">定制学习资源</h2></div>
        <div class="ph-right"><span class="pill">{{ assets.length }} 份资料</span></div>
      </header>

      <!-- ══ 文件资产画廊 ══ -->
      <div class="resource-stats">
        <button v-for="item in resourceGroups" :key="item.key" @click="assetCat = item.key"><SIcon :name="item.icon" :size="22" /><span><b>{{ assets.filter(a => a.asset_type === item.key).length }}</b><small>{{ item.label }}</small></span></button>
      </div>
      <section class="kb-section">
        <div class="sec-head">
          <h3 class="sec-title">生成的文件</h3>
          <span class="sec-sub">对话中生成的讲义、计划、报告会自动归集到这里</span>
        </div>

        <div class="kb-cats">
          <button
            v-for="c in assetCats"
            :key="c.key"
            class="cat-btn"
            :class="{ active: assetCat === c.key }"
            @click="assetCat = c.key"
          >{{ c.label }}</button>
        </div>

        <div v-if="filteredAssets.length" class="kb-grid">
          <div v-for="a in filteredAssets" :key="a.asset_id" class="kb-card" @click="openAsset(a)">
            <div class="kb-thumb" :style="thumbStyle(a)">
              <span class="resource-thumb-icon"><SIcon :name="resourceIcon(a.asset_type)" :size="35" /></span>
              <span class="resource-thumb-sketch" aria-hidden="true"><i></i><i></i><i></i></span>
              <span class="badge">{{ typeMeta(a.asset_type).label }}</span>
            </div>
            <div class="kb-card-body">
              <div class="t" :title="a.title">{{ a.title }}</div>
              <div class="kb-foot">
                <span class="src"><SIcon name="sparkle" :size="10" />{{ sourceLabel(a.source_tool) }}</span>
                <span v-if="a.evidence_ids?.length" class="cite" :title="'引用 ' + a.evidence_ids.length + ' 条知识库依据（可溯源）'">
                  <SIcon name="link" :size="10" />{{ a.evidence_ids.length }} 条依据
                </span>
                <span class="time">{{ formatTime(a.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else-if="!assetsLoading" :description="assetEmptyDesc" :image-size="72" />
      </section>

      <!-- ══ 知识检索 ══ -->
      <section class="kb-section">
        <div class="sec-head">
          <h3 class="sec-title">知识检索</h3>
          <span class="sec-sub">7 大领域、3796 个技能点、30944 道题</span>
        </div>

        <div class="kb-search">
          <SIcon name="search" :size="14" />
          <input v-model="searchText" placeholder="搜索技能点，如「一五计划」「园林」「突发事件应急」" />
        </div>

        <!-- 搜索结果 -->
        <div v-if="searching" class="search-body">
          <div v-if="searchHits.length" class="skill-list">
            <div v-for="hit in searchHits" :key="hit.skill_id" class="skill-card" @click="openSkill(hit.skill_id)">
              <div class="skill-card-head">
                <span class="skill-title">{{ hit.title }}</span>
                <span class="diff-badge">★{{ hit.difficulty }}</span>
              </div>
              <p class="skill-source">{{ hit.source }}</p>
              <p class="skill-preview">{{ display(hit.content.slice(0, 90)) }}…</p>
            </div>
          </div>
          <p v-else class="empty-hint">没有找到匹配的技能点，换个关键词试试。</p>
        </div>

        <!-- 技能点详情 -->
        <div v-else-if="detail" class="detail-panel">
          <el-breadcrumb separator="/" class="crumb">
            <el-breadcrumb-item v-for="p in detail.path" :key="p">{{ p }}</el-breadcrumb-item>
          </el-breadcrumb>
          <div class="detail-head">
            <h3 class="detail-title">{{ detail.title }}</h3>
            <div class="detail-tags">
              <span class="tag">难度 {{ detail.difficulty }}</span>
              <span v-for="c in detail.categories" :key="c" class="tag tag-cat">{{ c }}</span>
            </div>
          </div>
          <div class="detail-content">{{ display(detail.content) }}</div>

          <template v-if="detail.keywords.length">
            <div class="detail-section-title">关键词</div>
            <div class="kw-wrap">
              <el-tag v-for="k in detail.keywords.slice(0, 20)" :key="k" size="small" class="kw-tag">{{ k }}</el-tag>
            </div>
          </template>

          <template v-if="detail.questions.length">
            <div class="detail-section-title">关联真题（{{ detail.questions.length }}）</div>
            <div v-for="q in detail.questions" :key="q.question_id" class="q-card">
              <p class="q-prompt">{{ q.prompt }}</p>
              <div class="q-options">
                <p v-for="opt in q.options" :key="opt" class="q-opt">{{ opt }}</p>
              </div>
              <el-button text type="primary" size="small" @click="toggleAnswer(q)">
                {{ shownAnswers.has(q.question_id) ? '收起解析' : '查看答案与解析' }}
              </el-button>
              <div v-if="shownAnswers.has(q.question_id)" class="q-answer">
                <p><b>答案：{{ q.answer }}</b></p>
                <p class="q-expl">{{ q.explanation }}</p>
              </div>
            </div>
          </template>
        </div>

        <div v-else class="detail-empty">
          <el-empty description="输入关键词搜索技能点，点击结果卡片查看完整详情" />
        </div>
      </section>
      <!-- ══ 官方课本（4 本教材 → 章节 → 技能点） ══ -->
      <section class="kb-section">
        <div class="sec-head">
          <h3 class="sec-title">官方课本</h3>
          <span class="sec-sub">4 本官方教材   章节掌握度来自你的答题记录</span>
        </div>

        <div class="kb-search">
          <SIcon name="search" :size="14" />
          <input v-model="chapterSearch" placeholder="搜索章节、技能点…" />
        </div>

        <div v-for="g in groupedChapters" :key="g.bookId" class="bk-group">
          <h4 class="bk-book-title">
            <SIcon name="book" :size="14" color="#256CA7" />
            <span>{{ g.bookTitle }}</span>
            <span class="cnt">{{ g.chapters.length }} 章</span>
          </h4>
          <div class="bk-grid">
            <div v-for="c in g.chapters" :key="c.id" class="bk-card" @click="openChapter(c)">
              <div class="bk-card-head">
                <span class="bk-lv">{{ c.skillCount }} 技能点</span>
                <span class="bk-ct">{{ c.questionCount }} 真题   {{ c.sectionCount }} 节</span>
              </div>
              <div class="bk-title">{{ c.title }}</div>
              <div class="bk-prog">
                <div class="track">
                  <div class="fill" :class="{ gold: c.mastery === 100 }" :style="{ width: c.mastery + '%' }"></div>
                </div>
                <span class="pct">{{ c.mastery }}%</span>
              </div>
              <button class="bk-act" :class="actClass(c.mastery)" @click.stop="openChapter(c)">{{ actLabel(c.mastery) }}</button>
            </div>
          </div>
          <div v-if="!g.chapters.length" class="bk-empty">没有匹配的章节</div>
        </div>
        <el-empty v-if="!booksLoading && !groupedChapters.length" description="暂无课本数据 — 请确认后端服务已连接" :image-size="72" />
      </section>

      <!-- ══ 章节详情弹层 ══ -->
      <div v-if="chapterDetail" class="cd-mask" @click.self="closeChapter">
        <div class="cd-card">
          <div class="cd-hero">
            <div class="grad"></div>
            <span class="hero-book">{{ chapterDetail.bookTitle }}</span>
            <div class="tt">{{ chapterDetail.title }}</div>
            <button class="cd-close" @click="closeChapter"><SIcon name="x" :size="13" /></button>
          </div>
          <div class="cd-body">
            <div class="cd-path">{{ chapterDetail.partTitle ? chapterDetail.bookTitle + '   ' + chapterDetail.partTitle : chapterDetail.bookTitle }}</div>
            <div class="cd-stats">
              <div class="st"><span class="v">{{ chapterDetail.skillCount }}</span><span class="k">技能点</span></div>
              <div class="st"><span class="v">{{ chapterDetail.questionCount }}</span><span class="k">真题</span></div>
              <div class="st"><span class="v">{{ chapterDetail.sectionCount }}</span><span class="k">小节</span></div>
              <div class="st"><span class="v">{{ chapterDetail.mastery }}%</span><span class="k">掌握度</span></div>
            </div>
            <div class="cd-prog">
              <div class="lb"><span>章节掌握度</span><span class="pct">{{ chapterDetail.mastery }}%</span></div>
              <div class="bar"><div class="fill" :style="{ width: chapterDetail.mastery + '%' }"></div></div>
            </div>
            <div class="cd-lessons">
              <div class="lb">技能点清单</div>
              <div v-if="!chapterDetail.sections.length" class="cd-empty-tip">该章节暂无技能点</div>
              <div v-for="sec in chapterDetail.sections" :key="sec.id" class="cd-sec">
                <div class="cd-sec-name">{{ sec.title }}</div>
                <div v-for="sk in sec.skills" :key="sk.id" class="lesson" :class="'t' + skillTier(sk.mastery)" @click="openSkillFromBook(sk)">
                  <span class="li">
                    <SIcon v-if="sk.mastery >= 80" name="check" :size="11" :stroke-width="3.5" color="#fff" />
                    <template v-else>{{ sk.idx }}</template>
                  </span>
                  <span class="lt">{{ sk.title }}</span>
                  <span class="lm">{{ sk.mastery }}%</span>
                </div>
              </div>
            </div>
            <button class="cd-main" @click="cdMainAction">{{ cdMainLabel }}</button>
          </div>
        </div>
      </div>

      <!-- ══ 技能点详情抽屉（课本 → 章节 → 技能点） ══ -->
      <el-drawer v-model="skillDrawerOpen" size="520px" :title="skillDetail?.title || '技能点详情'" destroy-on-close>
        <template v-if="skillDetail">
          <el-breadcrumb separator="/" class="sd-crumb">
            <el-breadcrumb-item v-for="p in skillDetail.path" :key="p">{{ p }}</el-breadcrumb-item>
          </el-breadcrumb>
          <div class="sd-tags">
            <span class="tag">难度 {{ skillDetail.difficulty }}</span>
            <span v-for="cat in skillDetail.categories" :key="cat" class="tag tag-cat">{{ cat }}</span>
          </div>
          <div class="sd-content">{{ display(skillDetail.content) }}</div>
          <div class="sd-actions">
            <el-button text type="primary" size="small" @click="exportSkillMarkdown">
              <SIcon name="filetext" :size="13" /> 导出 Markdown
            </el-button>
          </div>
          <template v-if="skillDetail.keywords.length">
            <div class="sd-sec-title">关键词</div>
            <div class="sd-kw">
              <el-tag v-for="k in skillDetail.keywords.slice(0, 20)" :key="k" size="small" class="kw-tag">{{ k }}</el-tag>
            </div>
          </template>
          <template v-if="skillDetail.questions.length">
            <div class="sd-sec-title">关联真题（{{ skillDetail.questions.length }}）</div>
            <div v-for="q in skillDetail.questions" :key="q.question_id" class="sd-q">
              <p class="q-prompt">{{ q.prompt }}</p>
              <div v-if="q.options?.length">
                <p v-for="opt in q.options" :key="opt" class="q-opt">{{ opt }}</p>
              </div>
              <el-button text type="primary" size="small" @click="toggleQ(q)">
                {{ shownQ.has(q.question_id) ? '收起解析' : '查看答案与解析' }}
              </el-button>
              <div v-if="shownQ.has(q.question_id)" class="q-answer">
                <p><b>答案：{{ q.answer }}</b></p>
                <p class="q-expl">{{ q.explanation }}</p>
              </div>
            </div>
          </template>
        </template>
        <el-empty v-else description="加载中…" />
      </el-drawer>

    </div>

    <!-- ══ 资产预览抽屉 ══ -->
    <div v-if="drawerDoc" class="kbd-mask" :class="{ open: drawerOpen }" @click.self="closeDoc"></div>
    <aside class="kbd-drawer" :class="{ open: drawerOpen }">
      <template v-if="drawerDoc">
        <div class="kbd-head">
          <span class="badge" :style="typeBadgeStyle(drawerDoc.asset_type)">{{ typeMeta(drawerDoc.asset_type).label }}</span>
          <button class="kbd-close" @click="closeDoc"><SIcon name="x" :size="13" /></button>
        </div>
        <h3 class="kbd-title">{{ drawerDoc.title }}</h3>
        <div class="kbd-meta">
          <span><SIcon name="sparkle" :size="11" />{{ sourceLabel(drawerDoc.source_tool) }}</span>
          <span><SIcon name="clock" :size="11" />{{ formatTime(drawerDoc.created_at) }}</span>
        </div>
        <ResourceOverview class="kbd-content" :content="drawerDoc.content || ''" :type="drawerDoc.asset_type" />
        <LearnTranslate v-if="drawerDoc.content && drawerDoc.content.trim()" :text="drawerDoc.content" mode="markdown" render-markdown />
        <div class="kbd-actions">
          <button class="kbd-btn primary" @click="exportAsset(drawerDoc)">
            <SIcon name="filetext" :size="13" color="#fff" /> 导出为 Markdown
          </button>
          <button class="kbd-btn" @click="printAsset(drawerDoc)">
            <SIcon name="filetext" :size="13" /> 打印、存为 PDF
          </button>
          <button class="kbd-btn danger" @click="removeAsset(drawerDoc)">
            <SIcon name="x" :size="13" /> 删除
          </button>
        </div>
      </template>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { cleanDisplayText as display } from '@/utils/displayText'
import { WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SIcon from '@/components/SIcon.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import ResourceOverview from '@/components/ResourceOverview.vue'
import LearnTranslate from '@/components/LearnTranslate.vue'
import { deleteAsset, getAsset, listAssets, ASSET_TYPE_META } from '@/api/assets'
import type { AssetItem } from '@/api/assets'
import { getSkillDetail, searchKnowledge, getBooks, getKnowledgeTree } from '@/api/knowledge'
import type { SearchHit, SkillDetail as SkillDetailT, Question, SkillNode } from '@/api/knowledge'
import { getUserState } from '@/api/profile'
import { classifyError } from '@/api/client'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const resourceGroups = [ { key:'lecture',label:'知识讲义',icon:'book' },{ key:'practice_guide',label:'实操指南',icon:'target' },{ key:'plan',label:'学习计划',icon:'map' },{ key:'report',label:'学习报告',icon:'bookcheck' } ]
function resourceIcon(type:string) { return resourceGroups.find(item => item.key === type)?.icon || (type === 'wrong_book' ? 'shield' : 'filetext') }

// ── 官方课本（学习中心迁移：4 本教材 → 章节 → 技能点） ──
interface SkillRow {
  id: string
  title: string
  idx: number
  questionCount: number
  mastery: number // 0-100
}
interface SectionItem {
  id: string
  title: string
  skills: SkillRow[]
}
interface ChapterItem {
  id: string
  title: string
  bookId: string
  bookTitle: string
  partTitle: string
  sectionCount: number
  skillCount: number
  questionCount: number
  mastery: number // 0-100
  sections: SectionItem[]
}
interface ChapterGroup {
  bookId: string
  bookTitle: string
  chapters: ChapterItem[]
}

const books = ref<SkillNode[]>([])                      // 知识树（顶层 book）
const scores = ref<Record<string, number>>({})          // skill_id → 0~1 掌握度
const booksLoading = ref(false)
const chapterSearch = ref('')
const chapterDetail = ref<ChapterItem | null>(null)
const skillDrawerOpen = ref(false)
const skillDetail = ref<SkillDetailT | null>(null)
const shownQ = ref(new Set<string>())

function skillScore(id: string): number {
  return scores.value[id] ?? 0
}

function buildChapter(book: SkillNode, node: SkillNode, partTitle: string): ChapterItem {
  const sections: SectionItem[] = []
  let skillCount = 0
  let questionCount = 0
  let masterySum = 0

  for (const secNode of node.children ?? []) {
    if (secNode.type !== 'section') continue
    const rows: SkillRow[] = []
    for (const sNode of secNode.children ?? []) {
      if (sNode.type !== 'skill') continue
      const m = Math.round(skillScore(sNode.id) * 100)
      skillCount++
      questionCount += sNode.question_count ?? 0
      masterySum += m
      rows.push({
        id: sNode.id,
        title: sNode.title,
        idx: rows.length + 1,
        questionCount: sNode.question_count ?? 0,
        mastery: m,
      })
    }
    if (rows.length) sections.push({ id: secNode.id, title: secNode.title, skills: rows })
  }

  return {
    id: node.id,
    title: node.title,
    bookId: book.id,
    bookTitle: book.title,
    partTitle,
    sectionCount: sections.length,
    skillCount,
    questionCount,
    mastery: skillCount ? Math.round(masterySum / skillCount) : 0,
    sections,
  }
}

/** 收集一本书下的所有章节（兼容 book→chapter 与 book→part→chapter 两种层级）。 */
function chaptersOfBook(book: SkillNode): ChapterItem[] {
  const out: ChapterItem[] = []
  const walk = (nodes: SkillNode[] | undefined, partTitle: string) => {
    for (const n of nodes ?? []) {
      if (n.type === 'chapter') {
        out.push(buildChapter(book, n, partTitle))
      } else if (n.children) {
        walk(n.children, n.type === 'part' ? n.title : partTitle)
      }
    }
  }
  walk(book.children, '')
  return out
}

const fullChapters = computed<ChapterItem[]>(() => {
  const out: ChapterItem[] = []
  for (const b of books.value) {
    if (b.type === 'book') out.push(...chaptersOfBook(b))
  }
  return out
})

const groupedChapters = computed<ChapterGroup[]>(() => {
  const kw = chapterSearch.value.trim().toLowerCase()
  const groups: ChapterGroup[] = []
  for (const b of books.value) {
    if (b.type !== 'book') continue
    const chapters = chaptersOfBook(b)
    const list = kw
      ? chapters.filter(
          (c) =>
            c.title.toLowerCase().includes(kw) ||
            c.sections.some((sec) => sec.skills.some((sk) => sk.title.toLowerCase().includes(kw))),
        )
      : chapters
    if (list.length) groups.push({ bookId: b.id, bookTitle: b.title, chapters: list })
  }
  return groups
})

function openChapter(c: ChapterItem) {
  chapterDetail.value = c
}
function closeChapter() {
  chapterDetail.value = null
}
function skillTier(m: number): 'high' | 'mid' | 'low' {
  if (m >= 80) return 'high'
  if (m >= 50) return 'mid'
  return 'low'
}
function actClass(m: number): string {
  return m >= 100 ? 'done' : m > 0 ? 'cont' : 'start'
}
function actLabel(m: number): string {
  return m >= 100 ? '已完成' : m > 0 ? '继续学习' : '开始学习'
}
const cdMainLabel = computed(() => {
  if (!chapterDetail.value) return ''
  const m = chapterDetail.value.mastery
  return m >= 100 ? '重新复习' : m > 0 ? '继续学习' : '开始学习'
})
function cdMainAction() {
  closeChapter()
}

async function openSkillFromBook(sk: SkillRow) {
  skillDrawerOpen.value = true
  skillDetail.value = null
  shownQ.value = new Set()
  try {
    skillDetail.value = await getSkillDetail(sk.id)
  } catch (e: any) {
    ElMessage.error('加载技能点失败：' + classifyError(e).message)
  }
}
function toggleQ(q: Question) {
  const s = new Set(shownQ.value)
  s.has(q.question_id) ? s.delete(q.question_id) : s.add(q.question_id)
  shownQ.value = s
}
/** 导出技能点内容为 Markdown。 */
function exportSkillMarkdown() {
  const s = skillDetail.value
  if (!s) return
  const title = (s.title || '技能点').replace(/[\\/:*?"<>|]/g, '_')
  const content = `# ${s.title}\n\n${s.content || ''}`
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${title}.md`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已导出为 Markdown')
}

async function loadBooks() {
  booksLoading.value = true
  try {
    const [{ tree }, userState] = await Promise.all([
      getKnowledgeTree(),
      getUserState(store.userId),
    ])
    books.value = tree ?? []
    scores.value = userState.mastery?.knowledge_point_scores ?? {}
  } catch (e: any) {
    ElMessage.error('加载官方课本失败：' + classifyError(e).message)
  } finally {
    booksLoading.value = false
  }
}

// ── 文件资产 ──
const assets = ref<AssetItem[]>([])
const assetsLoading = ref(false)
const assetCat = ref('')

// 筛选分类：全部 + 主要资产类型（讲义/实操指南/学习计划/学习报告/文档，label 取自 ASSET_TYPE_META）
const ASSET_FILTER_KEYS = ['lecture', 'practice_guide', 'plan', 'report', 'text', 'wrong_book'] as const
const assetCats = computed(() => [
  { key: '', label: '全部' },
  ...ASSET_FILTER_KEYS.map((k) => ({ key: k, label: ASSET_TYPE_META[k]?.label || k })),
])

const filteredAssets = computed(() => {
  if (!assetCat.value) return assets.value
  return assets.value.filter((a) => a.asset_type === assetCat.value)
})

const assetEmptyDesc = computed(() =>
  store.backendOnline ? '在对话中让 AI 生成讲义、计划、报告，它们会自动出现在这里' : '后端未连接，无法加载文件资产',
)

function typeMeta(t: string) {
  return ASSET_TYPE_META[t] || ASSET_TYPE_META.text || { label: t, color: '#888', emoji: '📄' }
}

function sourceLabel(s: string): string {
  const map: Record<string, string> = {
    generate_material: '对话生成',
    generate_plan: '对话制定',
    generate_report: '对话生成',
    training_plan: '工具箱',
    training_report: '工具箱',
  }
  return map[s] || '系统'
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function thumbStyle(a: AssetItem) {
  const meta = typeMeta(a.asset_type)
  return { background: `linear-gradient(135deg, ${meta.color}26, ${meta.color}0d)` }
}

function typeBadgeStyle(t: string) {
  const meta = typeMeta(t)
  return { color: '#1d5e99', background: `${meta.color}1a`, border: `1px solid ${meta.color}33` }
}

async function loadData() {
  assetsLoading.value = true
  try {
    const res = await listAssets(store.userId)
    assets.value = res.assets || []
  } catch (e: any) {
    ElMessage.error('加载文件资产失败：' + classifyError(e).message)
  } finally {
    assetsLoading.value = false
  }
}

// ── 资产预览抽屉 ──
const drawerDoc = ref<AssetItem | null>(null)
const drawerOpen = ref(false)

async function openAsset(a: AssetItem) {
  drawerDoc.value = a
  drawerOpen.value = true
  try {
    const full = await getAsset(a.asset_id)
    if (drawerDoc.value?.asset_id === a.asset_id) {
      drawerDoc.value = { ...a, content: full.content || a.content }
    }
  } catch (e: any) {
    ElMessage.error('加载文件详情失败：' + classifyError(e).message)
  }
}

function closeDoc() {
  drawerOpen.value = false
}

function exportAsset(a: AssetItem) {
  const title = (a.title || '学习文件').replace(/[\\/:*?"<>|]/g, '_')
  const content = `# ${a.title}\n\n${a.content || ''}`
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${title}.md`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已导出为 Markdown')
}

// T17：打印 / 存为 PDF（浏览器打印对话框，可选择"另存为 PDF"）
function printAsset(a: AssetItem) {
  const win = window.open('', '_blank', 'width=800,height=900')
  if (!win) {
    ElMessage.warning('浏览器拦截了弹窗，请允许后重试')
    return
  }
  win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${a.title}</title>
    <style>
      body { font-family: "Microsoft YaHei", sans-serif; max-width: 720px; margin: 32px auto; padding: 0 24px; color: #222; line-height: 1.8; }
      h1 { color: #1d5e99; border-bottom: 2px solid #338FF2; padding-bottom: 8px; }
      .meta { color: #42586e; font-size: 13px; margin-bottom: 24px; }
      pre { background: #f6f6f6; padding: 12px; border-radius: 6px; white-space: pre-wrap; }
      blockquote { border-left: 3px solid #338FF2; margin-left: 0; padding-left: 12px; color: #555; }
      @media print { body { margin: 0; } }
    </style></head><body>
    <h1>${a.title}</h1>
    <div class="meta">旅鸢   ${sourceLabel(a.source_tool)}   ${formatTime(a.created_at)}</div>
    <div>${(a.content || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br/>')}</div>
    <script>window.onload = () => setTimeout(() => window.print(), 300)<\/script>
    </body></html>`)
  win.document.close()
  ElMessage.success('已打开打印窗口，可选择「另存为 PDF」')
}

async function removeAsset(a: AssetItem) {
  try {
    await ElMessageBox.confirm(`确认删除「${a.title}」？删除后不可恢复。`, '删除文件', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  try {
    await deleteAsset(a.asset_id)
    assets.value = assets.value.filter((x) => x.asset_id !== a.asset_id)
    if (drawerDoc.value?.asset_id === a.asset_id) drawerOpen.value = false
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.error('删除失败：' + classifyError(e).message)
  }
}

// ── 知识检索 ──
const searchText = ref('')
const searching = ref(false)
const searchHits = ref<SearchHit[]>([])
const detail = ref<SkillDetailT | null>(null)
const shownAnswers = ref(new Set<string>())

async function openSkill(id: string) {
  searching.value = false
  searchText.value = ''
  try {
    detail.value = await getSkillDetail(id)
  } catch (e: any) {
    ElMessage.error('加载技能点失败：' + classifyError(e).message)
  }
}

function toggleAnswer(q: any) {
  const s = new Set(shownAnswers.value)
  s.has(q.question_id) ? s.delete(q.question_id) : s.add(q.question_id)
  shownAnswers.value = s
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchText, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = val.trim()
  if (q.length < 2) {
    searching.value = false
    searchHits.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    searching.value = true
    detail.value = null
    try {
      const res = await searchKnowledge({ q, top_k: 12 })
      searchHits.value = res.results
    } catch (e: any) {
      ElMessage.error('搜索失败：' + classifyError(e).message)
    }
  }, 350)
})

// ── 快捷键：ESC 关闭弹层/抽屉 ──
function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  if (chapterDetail.value) closeChapter()
  else if (drawerOpen.value) closeDoc()
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  loadBooks()
})
// keep-alive 重新激活时刷新资产（对话中可能生成了新的文件资产）
onActivated(() => loadData())
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.kb-page { height: 100%; overflow-y: auto; }
.kb-inner { max-width: 1180px; margin: 0 auto; padding: 20px 20px 48px; }

/* 离线横幅 */
.backend-offline-banner {
  display: flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: $radius-md;
  background: #fef3e2; border: 1px solid #f5d9a0; color: #8f5813; font-size: 13px; margin-bottom: 16px;
}

/* 页头 */
.ph { display: flex; align-items: center; justify-content: space-between; padding: 4px 0 20px; }
.ph-title { font-family: $font-serif; font-size: 24px; font-weight: 700; color: $color-text-link; }
.pill { font-size: 11.5px; padding: 5px 13px; border-radius: 20px; color: #256CA7;
  background: rgba(51,143,242,.12); border: 1px solid rgba(51,143,242,.3); }

/* 区块头 */
.kb-section { margin-bottom: 28px; }
.sec-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap;
  .sec-title { font-family: $font-serif; font-size: 17px; font-weight: 700; color: $color-text-link; }
  .sec-sub { font-size: 12px; color: $color-text-secondary; } }

/* 分类 pills */
.kb-cats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.cat-btn { font-size: 12px; padding: 7px 16px; border-radius: 20px; cursor: pointer;
  border: 1px solid $color-border; background: rgba(255,255,255,.85); color: $color-text-secondary;
  transition: all .15s; font-family: $font-sans;
  &:hover { border-color: rgba(51,143,242,.5); color: #256CA7; }
  &.active { background: $color-primary; border-color: $color-primary; color: #fff; } }

/* 资产卡片网格 */
.kb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; }
.kb-card { border-radius: 16px; overflow: hidden; cursor: pointer; background: rgba(255,255,255,.88);
  border: 1px solid $color-border; transition: all .2s;
  &:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(24,58,99,.1); border-color: rgba(51,143,242,.4); } }
.kb-thumb { position: relative; height: 120px; display: flex; align-items: center; justify-content: center;
  .thumb-emoji { font-size: 42px; filter: drop-shadow(0 2px 6px rgba(24,58,99,.18)); }
  .badge { position: absolute; top: 8px; left: 8px; font-size: 10px; padding: 2px 9px; border-radius: 20px;
    background: rgba(24,58,99,.78); color: $color-text-link; font-weight: 600; } }
.kb-card-body { padding: 12px 14px;
  .t { font-size: 13.5px; font-weight: 600; color: $color-text; line-height: 1.45;
    overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .kb-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 9px; gap: 8px;
    .src { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; color: $color-text-secondary;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cite { display: inline-flex; align-items: center; gap: 3px; font-size: 10px; color: $color-text-link;
      background: rgba(51, 143, 242, 0.14); padding: 1px 7px; border-radius: 999px; flex-shrink: 0; }
    .time { font-size: 10px; color: $color-text-secondary; flex-shrink: 0; } } }

/* 知识搜索 */
.kb-search { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 12px;
  background: rgba(255,255,255,.88); border: 1px solid $color-border; margin-bottom: 16px;
  input { flex: 1; border: none; outline: none; background: transparent; font-size: 13px;
    font-family: $font-sans; color: $color-text;
    &::placeholder { color: $color-text-secondary; } } }

.search-body { margin-bottom: 8px; }
.skill-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.skill-card { padding: 16px; border-radius: $radius-lg; background: $color-surface;
  border: 1px solid $color-border; cursor: pointer; transition: all .2s;
  &:hover { border-color: $color-primary; box-shadow: $shadow-card; transform: translateY(-2px); }
  .skill-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  .skill-title { font-weight: 600; color: $color-text; }
  .diff-badge { color: $color-accent-d15; font-size: 12px; }
  .skill-source { font-size: 12px; color: $color-text-secondary; margin-bottom: 8px; }
  .skill-preview { font-size: 12px; color: $color-text-secondary; line-height: 1.6; } }
.empty-hint { color: $color-text-secondary; font-size: 13px; padding: 24px 0; }

/* 技能点详情 */
.detail-panel { padding: 24px; border-radius: $radius-lg; background: $color-surface;
  border: 1px solid $color-border; box-shadow: $shadow-card;
  .crumb { margin-bottom: 16px; font-size: 12px; }
  .detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
  .detail-title { font-family: $font-serif; font-size: 22px; font-weight: 700; color: $color-text; }
  .detail-tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag { font-size: 12px; padding: 2px 10px; border-radius: 999px; background: $color-muted-bg; color: $color-text-secondary; }
  .tag-cat { background: $color-accent-light; color: $color-accent-d15; }
  .detail-content { font-size: 14px; line-height: 1.9; color: $color-text; white-space: pre-wrap; margin-bottom: 20px; }
  .detail-section-title { font-weight: 600; color: $color-text-link; margin: 20px 0 10px; font-size: 14px; }
  .kw-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
  .kw-tag { margin-right: 0; }
}
.q-card { border: 1px solid $color-border; border-radius: $radius-md; padding: 14px 16px; margin-bottom: 12px;
  .q-prompt { font-size: 14px; font-weight: 500; color: $color-text; margin-bottom: 8px; }
  .q-options p { font-size: 13px; color: $color-text-secondary; margin: 2px 0; }
  .q-answer { margin-top: 10px; padding: 10px 12px; background: $color-muted-bg; border-radius: $radius-sm; font-size: 13px; color: $color-text; }
  .q-expl { margin-top: 4px; color: $color-text-secondary; } }
.detail-empty { padding: 48px 0; }

/* 资产预览抽屉（队友 kbd-drawer 视觉） */
.kbd-mask { position: fixed; inset: 0; z-index: 290; background: rgba(10,22,42,.4); backdrop-filter: blur(3px);
  opacity: 0; transition: opacity .25s ease; pointer-events: none;
  &.open { opacity: 1; pointer-events: auto; } }
.kbd-drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(440px, 92vw); z-index: 300;
  background: #fff; box-shadow: -16px 0 48px rgba(10,22,42,.22); padding: 22px 26px; overflow-y: auto;
  transform: translateX(105%); transition: transform .3s cubic-bezier(.32,.72,.35,1);
  &.open { transform: translateX(0); } }
.kbd-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
  .badge { font-size: 10px; padding: 3px 10px; border-radius: 20px; font-weight: 600; } }
.kbd-close { width: 30px; height: 30px; border-radius: 50%; border: none; cursor: pointer;
  background: $color-secondary-bg; color: $color-text-secondary; display: flex; align-items: center;
  justify-content: center; transition: all .15s;
  &:hover { background: $color-border; color: $color-text-link; transform: rotate(90deg); } }
.kbd-title { font-family: $font-serif; font-size: 19px; font-weight: 700; color: $color-text-link; line-height: 1.4; }
.kbd-meta { display: flex; gap: 14px; margin-top: 8px; flex-wrap: wrap;
  span { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: $color-text-secondary; } }
.kbd-content { margin-top: 14px;
  padding: 14px 16px; background: rgba(24,58,99,.04); border-radius: 12px; border: 1px solid rgba(24,58,99,.06);
  max-height: 60vh; overflow-y: auto; }
.kbd-actions { display: flex; gap: 10px; margin-top: 18px; }
.kbd-btn { flex: 1; padding: 12px; border-radius: 12px; cursor: pointer; font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; gap: 6px; transition: all .18s; font-family: $font-sans;
  &.primary { border: none; color: #fff; background: linear-gradient(135deg, #338FF2, #26507f);
    &:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(24,58,99,.3); } }
  &.danger { background: #fff; border: 1px solid $color-border; color: #c5193f;
    &:hover { border-color: rgba(225,29,72,.4); color: #c5193f; background: rgba(225,29,72,.04); } } }

@media (max-width: 700px) { .kb-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .kb-grid { grid-template-columns: 1fr; } }

// ── 官方课本（自学习中心迁移） ──
.bk-group { margin-top: 16px; }
.bk-book-title { display: flex; align-items: center; gap: 7px; font-size: 13.5px; font-weight: 700;
  color: $color-text-link; font-family: $font-serif; margin: 0 0 10px;
  .cnt { font-size: 11px; font-weight: 400; color: $color-text-secondary; } }
.bk-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.bk-card { border: 1px solid $color-border; border-radius: $radius-md; padding: 14px 16px; cursor: pointer;
  background: #fff; transition: all .18s;
  &:hover { border-color: rgba(51,143,242,.5); transform: translateY(-2px); box-shadow: 0 4px 14px rgba(24,58,99,.08); } }
.bk-card-head { display: flex; align-items: center; justify-content: space-between; font-size: 10.5px; color: $color-text-secondary; }
.bk-lv { padding: 2px 8px; border-radius: 10px; background: rgba(24,58,99,.06); }
.bk-ct { font-family: Consolas, monospace; }
.bk-title { margin: 9px 0 10px; font-size: 13.5px; font-weight: 600; color: $color-text-link; line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.bk-prog { display: flex; align-items: center; gap: 8px;
  .track { flex: 1; height: 6px; border-radius: 4px; background: rgba(24,58,99,.08); overflow: hidden;
    .fill { display: block; height: 100%; border-radius: 4px; background: linear-gradient(90deg, #338FF2, #A8893C);
      &.gold { background: #2d8a2d; } } }
  .pct { font-size: 11px; font-family: Consolas, monospace; color: #256CA7; } }
.bk-act { margin-top: 10px; width: 100%; padding: 6px 0; border-radius: 9px; border: none; font-size: 12px;
  font-weight: 600; cursor: pointer; transition: all .15s;
  &.start { background: rgba(51,143,242,.14); color: #256CA7; &:hover { background: rgba(51,143,242,.22); } }
  &.cont { background: rgba(24,58,99,.07); color: $color-text-link; &:hover { background: rgba(24,58,99,.12); } }
  &.done { background: rgba(45,138,45,.1); color: #267326; } }
.bk-empty { padding: 18px; text-align: center; font-size: 12.5px; color: $color-text-secondary;
  border: 1px dashed $color-border; border-radius: $radius-md; }

// ── 章节详情弹层 ──
.cd-mask { position: fixed; inset: 0; background: rgba(15,30,50,.45); z-index: 50; display: flex;
  align-items: center; justify-content: center; padding: 24px; }
.cd-card { width: 640px; max-width: 96vw; max-height: 86vh; display: flex; flex-direction: column;
  border-radius: 18px; background: #fff; overflow: hidden; box-shadow: 0 20px 60px rgba(15,30,50,.3); }
.cd-hero { position: relative; padding: 22px 26px 20px; color: #fff;
  background: linear-gradient(135deg, #1C426E, #338FF2 60%, #2E5279);
  .grad { position: absolute; inset: 0; background: radial-gradient(120% 120% at 85% 0%, rgba(51,143,242,.25), transparent 55%); }
  .hero-book { position: relative; font-size: 11px; letter-spacing: 2px; color: #FFFFFF; }
  .tt { position: relative; margin-top: 8px; font-size: 19px; font-weight: 700; font-family: $font-serif; line-height: 1.4; }
  .cd-close { position: absolute; top: 14px; right: 14px; width: 30px; height: 30px; border-radius: 50%;
    border: none; background: rgba(255,255,255,.14); color: #fff; cursor: pointer;
    display: flex; align-items: center; justify-content: center; } }
.cd-body { padding: 20px 26px 26px; overflow-y: auto; }
.cd-path { font-size: 12px; color: $color-text-secondary; }
.cd-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 14px;
  .st { padding: 10px; border-radius: 12px; background: rgba(24,58,99,.04); text-align: center;
    .v { display: block; font-size: 17px; font-weight: 700; color: $color-text-link; font-family: Consolas, monospace; }
    .k { font-size: 10.5px; color: $color-text-secondary; } } }
.cd-prog { margin-top: 16px;
  .lb { display: flex; justify-content: space-between; font-size: 12px; color: $color-text-secondary; margin-bottom: 6px;
    .pct { font-family: Consolas, monospace; color: #256CA7; } }
  .bar { height: 8px; border-radius: 5px; background: rgba(24,58,99,.08); overflow: hidden;
    .fill { height: 100%; border-radius: 5px; background: linear-gradient(90deg, #338FF2, #A8893C); } } }
.cd-lessons { margin-top: 18px;
  .lb { font-size: 12.5px; font-weight: 700; color: $color-text-link; margin-bottom: 8px; } }
.cd-empty-tip { font-size: 12.5px; color: $color-text-secondary; padding: 12px; border: 1px dashed $color-border;
  border-radius: 10px; text-align: center; }
.cd-sec { margin-bottom: 10px; }
.cd-sec-name { font-size: 12px; font-weight: 600; color: #256CA7; margin-bottom: 5px; }
.lesson { display: flex; align-items: center; gap: 9px; padding: 7px 10px; border-radius: 9px; cursor: pointer;
  background: rgba(24,58,99,.03); border: 1px solid transparent; transition: all .15s;
  &:hover { border-color: rgba(51,143,242,.4); }
  &.thigh { background: rgba(45,138,45,.06); }
  &.tmid { background: rgba(51,143,242,.07); }
  &.tlow { background: rgba(24,58,99,.03); }
  .li { width: 19px; height: 19px; border-radius: 50%; background: $color-secondary-bg; color: $color-text-secondary;
    font-size: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    .tmid & { background: rgba(51,143,242,.25); color: #256CA7; }
    .thigh & { background: #2d8a2d; color: #fff; } }
  .lt { flex: 1; font-size: 12.5px; color: $color-text; }
  .lm { font-size: 10.5px; font-family: Consolas, monospace; color: $color-text-secondary; } }
.cd-main { margin-top: 16px; width: 100%; padding: 11px; border: none; border-radius: 12px;
  background: linear-gradient(135deg, #338FF2, #A8893C); color: #fff; font-size: 13.5px; font-weight: 600;
  cursor: pointer; transition: all .2s;
  &:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(51,143,242,.4); } }

// ── 技能点抽屉 ──
.sd-crumb { margin-bottom: 12px; }
.sd-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px;
  .tag { font-size: 11px; padding: 3px 9px; border-radius: 10px; background: rgba(24,58,99,.06); color: $color-text-secondary; }
  .tag-cat { background: rgba(51,143,242,.12); color: #256CA7; } }
.sd-content { font-size: 13.5px; line-height: 1.9; color: $color-text; white-space: pre-wrap; }
.sd-actions { margin: 14px 0; }
.sd-sec-title { font-size: 13px; font-weight: 700; color: $color-text-link; margin: 18px 0 8px; }
.sd-kw { display: flex; flex-wrap: wrap; gap: 6px; }
.sd-q { border: 1px solid $color-border; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
  .q-prompt { font-size: 13.5px; line-height: 1.7; color: $color-text; margin: 0 0 8px; }
  .q-opt { font-size: 12.5px; color: $color-text-secondary; margin: 3px 0; padding-left: 14px; position: relative;
    &::before { content:''; position:absolute; left:2px; top:10px; width:4px; height:4px; border-radius:50%; background:#338FF2; } }
  .q-answer { margin-top: 10px; padding: 10px 12px; border-radius: 10px; background: rgba(47,143,91,.06);
    font-size: 12.5px; line-height: 1.7;
    b { color: #267326; }
    .q-expl { color: $color-text-secondary; margin: 6px 0 0; } } }
.resource-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; margin:0 0 25px; button { display:flex; align-items:center; gap:13px; text-align:left; background:#fff; border:1px solid #dbe8f5; color:$color-text-link; padding:19px; border-radius:16px 5px 16px 5px; cursor:pointer; span { flex:1; } b { display:block; color:#2a587c; font-size:23px; font-weight:600; } small { display:block; color:$color-text-secondary; font-size:12px; margin-top:5px; } } }
.resource-thumb-icon { position:absolute; left:24px; top:28px; display:grid; place-items:center; color:$color-text-link; width:60px; height:60px; background:#ffffffa8; border:1px solid #d5e8f8; border-radius:17px; }
.resource-thumb-sketch { display:flex; flex-direction:column; gap:8px; position:absolute; left:104px; right:26px; top:41px; i { display:block; height:8px; border-radius:3px; background:#8db9dc30; &:nth-child(2) { width:80%; } &:nth-child(3) { width:60%; } } }
@media(max-width:700px) { .resource-stats { grid-template-columns:1fr 1fr; } }
</style>
